from email.utils import parsedate_to_datetime
from ui.ui_print import *
import releases

# (required) Name of the Debrid service
name = "Torbox"
short = "TB"
# (required) Authentification of the Torbox service, can be oauth aswell. Create a setting for the required variables in the ui.settings_list. For an oauth example check the trakt authentification.
api_key = ""
API_BASE = "https://api.torbox.app/v1"
CHECKCACHED_BATCH = 100
MYLIST_LIMIT = 1000
UNCACHED_DOWNLOAD_STATES = ("downloading", "paused", "stalled (no seeds)")
# Define Variables
session = requests.Session()
errors = [
    [202, " action already done"],
    [400, " bad Request (see error message)"],
    [403, " permission denied (infringing torrent or account locked or not premium)"],
    [503, " service unavailable (see error message)"],
    [404, " wrong parameter (invalid file id(s)) / unknown resource (invalid id)"],
]

TRANSIENT_HTTP_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def setup(cls, new=False):
    from debrid.services import setup
    setup(cls, new)


def _headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
        'authorization': 'Bearer ' + api_key,
    }


# Error Log
def logerror(response):
    if response.status_code not in [200, 201, 204]:
        desc = ""
        for error in errors:
            if response.status_code == error[0]:
                desc = error[1]
        ui_print("[torbox] error: (" + str(response.status_code) + desc + ") " + str(response.content))
    if response.status_code == 401:
        ui_print("[torbox] error: (401 unauthorized): torbox api key does not seem to work. check your torbox settings.")
    if response.status_code == 403:
        ui_print("[torbox] error: (403 unauthorized): You may have attempted to add an infringing torrent or your torbox account is locked or you dont have premium.")


def _safe_json_dict(response):
    try:
        return json.loads(response.content)
    except Exception:
        return None


def _parse_json_content(content):
    try:
        return json.loads(content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception:
        return None


def _request_raw(method, url, *, context="torbox", max_attempts=7, retry_base_sleep=5.0, **kwargs):
    """HTTP request with retries on transient transport failures."""
    kwargs.setdefault('headers', _headers())
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return session.request(method, url, **kwargs)
        except TRANSIENT_HTTP_ERRORS as e:
            last_exc = e
            if attempt >= max_attempts:
                break
            sleep_s = min(retry_base_sleep * attempt, 120.0)
            ui_print(
                f"[torbox] {context} {method.upper()} transient failure ({e}); "
                f"retrying in {sleep_s:.1f}s ({attempt}/{max_attempts})",
                debug=ui_settings.debug,
            )
            time.sleep(sleep_s)
    raise last_exc


def _is_rate_limit_response(status, body):
    if status == 429:
        return True
    if isinstance(body, dict):
        err = str(body.get("error") or "").upper()
        if err in ("RATE_LIMIT", "TOO_MANY_REQUESTS"):
            return True
        detail = str(body.get("detail") or body.get("message") or "").lower()
        if "rate limit" in detail or "too many" in detail:
            return True
    return False


def _retry_after_seconds(response, body):
    ra = response.headers.get("Retry-After")
    if ra:
        ra_stripped = ra.strip()
        try:
            sec = float(ra_stripped)
            return sec if sec > 0 else None
        except ValueError:
            try:
                dt = parsedate_to_datetime(ra_stripped)
                if dt is not None:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    delta = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                    return delta if delta > 0 else None
            except (TypeError, ValueError):
                pass
    if isinstance(body, dict):
        for key in ("retry_after", "retryAfter", "wait"):
            if key in body and body[key] is not None:
                try:
                    sec = float(body[key])
                    return sec if sec > 0 else None
                except (TypeError, ValueError):
                    continue
    return None


def _createtorrent_already_on_account(body):
    if not isinstance(body, dict):
        return False
    err = str(body.get("error") or "").upper()
    detail = str(body.get("detail") or "").lower()
    if "already queued" in detail:
        return True
    if "already added" in detail or "already exists" in detail:
        return True
    if err == "DIFF_ISSUE" and (
        "queued" in detail or "duplicate" in detail or "exists" in detail
    ):
        return True
    return False


def _log_api_detail(parsed):
    if parsed is None or not hasattr(parsed, "detail"):
        return
    if hasattr(parsed, "success") and not parsed.success:
        ui_print("[torbox] failed: " + parsed.detail)
    else:
        ui_print("[torbox]: " + parsed.detail, debug=ui_settings.debug)


# Get Function
def get(url):
    response = None
    try:
        ui_print("[torbox] (get): " + url, debug=ui_settings.debug)
        response = _request_raw("GET", url, context="get")
        logerror(response)
        parsed = _parse_json_content(response.content)
        _log_api_detail(parsed)
        return parsed
    except Exception as e:
        ui_print("[torbox] error: (json exception): " + str(e))
        return None


# Post Function
def post(url, data=None, json_data=None):
    response = None
    try:
        ui_print("[torbox] (post): " + url + " with data " + repr(data if data else json_data), debug=ui_settings.debug)
        if json_data is not None:
            response = _request_raw("POST", url, json=json_data, context="post")
        else:
            response = _request_raw("POST", url, data=data, context="post")
        logerror(response)
        parsed = _parse_json_content(response.content)
        _log_api_detail(parsed)
        return parsed
    except Exception as e:
        if response is not None and hasattr(response, "status_code") and response.status_code >= 300:
            ui_print("[torbox] error: (json exception): " + str(e))
        else:
            ui_print("[torbox] error: (json exception): " + str(e))
        return None


def post_checkcached(hashes):
    """POST /torrents/checkcached batch — avoids long GET query strings."""
    url = API_BASE + "/api/torrents/checkcached?format=list&list_files=true"
    try:
        ui_print(
            "[torbox] (post checkcached): " + str(len(hashes)) + " hash(es)",
            debug=ui_settings.debug,
        )
        response = _request_raw(
            "POST",
            url,
            json={"hashes": hashes},
            context="checkcached",
            timeout=120,
        )
        logerror(response)
        parsed = _parse_json_content(response.content)
        _log_api_detail(parsed)
        return parsed
    except Exception as e:
        ui_print("[torbox] error: checkcached batch failed: " + str(e))
        return None


def _requires_cached_only(element):
    if not hasattr(element, "version"):
        return False
    for rule in element.version.rules:
        if (
            rule[0] == "cache status"
            and rule[1] in ("requirement", "preference")
            and rule[2] == "cached"
        ):
            return True
    return False


def _allows_uncached(element):
    return not _requires_cached_only(element)


def create_torrent(magnet, add_only_if_cached=False):
    """POST createtorrent with reactive 429 retry until a definitive API response."""
    url = API_BASE + "/api/torrents/createtorrent"
    payload = {
        "magnet": str(magnet),
        "seed": 3,
        "allow_zip": "false",
    }
    if add_only_if_cached:
        payload["add_only_if_cached"] = "true"

    attempt = 0
    while True:
        attempt += 1
        response = None
        try:
            ui_print("[torbox] (post createtorrent): " + url, debug=ui_settings.debug)
            response = _request_raw("POST", url, data=payload, context="createtorrent", timeout=180)
        except TRANSIENT_HTTP_ERRORS as e:
            ui_print("[torbox] error: createtorrent connection failed: " + str(e))
            return None

        logerror(response)
        body = _safe_json_dict(response)
        parsed = _parse_json_content(response.content)

        if isinstance(body, dict) and body.get("success"):
            return parsed

        if isinstance(body, dict) and _createtorrent_already_on_account(body):
            ui_print(
                "[torbox] createtorrent: already on account — "
                + str(body.get("detail") or ""),
                debug=ui_settings.debug,
            )
            return parsed

        if not _is_rate_limit_response(response.status_code, body):
            if parsed is not None:
                _log_api_detail(parsed)
            elif body is not None:
                ui_print("[torbox] createtorrent failed: " + str(body.get("detail") or body))
            return None

        wait = _retry_after_seconds(response, body)
        if wait is None:
            wait = max(60.0 - (time.monotonic() % 60), 5.0)
        wait = max(float(wait), 5.0)
        ui_print(
            f"[torbox] createtorrent rate limited (HTTP {response.status_code}); "
            f"sleeping {wait:.1f}s before retry (attempt {attempt})"
        )
        time.sleep(wait)


def control_torrent(torrent_id, operation):
    url = API_BASE + "/api/torrents/controltorrent"
    payload = {
        "torrent_id": torrent_id,
        "operation": operation.strip().lower(),
    }
    return post(url, json_data=payload)


def _mylist_data_items(response):
    if response is None or not hasattr(response, "data") or response.data is None:
        return []
    data = response.data
    if isinstance(data, list):
        return data
    return [data]


def get_mylist_torrent(torrent_id=None, info_hash=None):
    if torrent_id is not None:
        url = f"{API_BASE}/api/torrents/mylist?bypass_cache=true&id={torrent_id}"
        response = get(url)
        items = _mylist_data_items(response)
        return items[0] if items else None

    if not info_hash:
        return None

    target = info_hash.lower()
    offset = 0
    while True:
        url = (
            f"{API_BASE}/api/torrents/mylist"
            f"?bypass_cache=true&offset={offset}&limit={MYLIST_LIMIT}"
        )
        response = get(url)
        items = _mylist_data_items(response)
        if not items:
            break
        for item in items:
            item_hash = getattr(item, "hash", None)
            if item_hash and str(item_hash).lower() == target:
                return item
        if len(items) < MYLIST_LIMIT:
            break
        offset += MYLIST_LIMIT
    return None


def _torrent_id_from_create_response(response, release):
    if (
        response is not None
        and hasattr(response, "success")
        and response.success
        and hasattr(response, "data")
        and hasattr(response.data, "torrent_id")
    ):
        return response.data.torrent_id

    if release.hash:
        existing = get_mylist_torrent(info_hash=release.hash)
        if existing is not None and hasattr(existing, "id"):
            return existing.id
    return None


def _apply_cached_release(release, version, selected_torrent, wanted):
    actual_title = ""
    release.download = selected_torrent.files
    if hasattr(selected_torrent, "name") and selected_torrent.name:
        actual_title = selected_torrent.name
    if len(release.download) > 0:
        release.files = version.files
        ui_print("[torbox] adding cached release: " + release.title)
        if actual_title != "":
            release.title = actual_title
        return True
    if version.wanted <= len(wanted) / 2:
        return False
    release.files = version.files
    ui_print("[torbox] adding cached release: " + release.title)
    if actual_title != "":
        release.title = actual_title
    return True


# Object classes
class file:
    def __init__(self, id, name, size, wanted_list, unwanted_list):
        self.id = id
        self.name = name
        self.size = size / 1000000000
        self.match = ''
        wanted = False
        unwanted = False
        for key, wanted_pattern in wanted_list:
            if wanted_pattern.search(self.name):
                wanted = True
                self.match = key
                break

        if not wanted:
            for key, unwanted_pattern in unwanted_list:
                if unwanted_pattern.search(self.name) or self.name.endswith('.exe') or self.name.endswith('.txt'):
                    unwanted = True
                    break

        self.wanted = wanted
        self.unwanted = unwanted

    def __eq__(self, other):
        return self.id == other.id


class version:
    def __init__(self, files):
        self.files = files
        self.needed = 0
        self.wanted = 0
        self.unwanted = 0
        self.size = 0
        for file in self.files:
            self.size += file.size
            if file.wanted:
                self.wanted += 1
            if file.unwanted:
                self.unwanted += 1


# (required) Download Function.
def download(element, stream=True, query='', force=False):
    cached = element.Releases
    if query == '':
        query = element.deviation()
    wanted = [query]
    if not isinstance(element, releases.release):
        wanted = element.files()
    add_only_if_cached = _requires_cached_only(element)

    for release in cached[:]:
        # if release matches query
        if regex.match(query, release.title, regex.I) or force:
            if stream:
                release.size = 0
                for version in release.files:
                    if hasattr(version, 'files'):
                        if len(version.files) > 0 and version.wanted > len(wanted) / 2 or force:
                            cached_ids = []
                            for file in version.files:
                                cached_ids += [file.id]
                            try:
                                response = create_torrent(
                                    release.download[0],
                                    add_only_if_cached=add_only_if_cached,
                                )
                                torrent_id = _torrent_id_from_create_response(response, release)
                                if torrent_id is None:
                                    ui_print('[torbox] error: could not add magnet for release: ' + release.title)
                                    continue
                            except Exception as e:
                                ui_print('[torbox] error: could not add magnet for release: ' + release.title + ' ' + str(e))
                                continue

                            selected_torrent = get_mylist_torrent(torrent_id=torrent_id)
                            if selected_torrent is None:
                                ui_print('[torbox] error: unexpected mismatch after adding torrent: ' + release.title)
                                continue

                            download_state = getattr(selected_torrent, "download_state", "") or ""
                            file_count = len(selected_torrent.files) if hasattr(selected_torrent, "files") and selected_torrent.files else 0

                            if file_count == len(cached_ids):
                                if _apply_cached_release(release, version, selected_torrent, wanted):
                                    return True
                                continue

                            if download_state == "cached":
                                if _apply_cached_release(release, version, selected_torrent, wanted):
                                    return True
                                continue

                            if download_state in UNCACHED_DOWNLOAD_STATES:
                                if _allows_uncached(element):
                                    import debrid as db
                                    release.files = version.files
                                    db.downloading += [element.query() + ' [' + element.version.name + ']']
                                    ui_print('[torbox] adding uncached release: ' + release.title)
                                    return True
                                control_torrent(torrent_id, "delete")
                                continue

                            ui_print('[torbox] error: queuing this torrent returned an unsupported state (' + download_state + '). Select a different torrent.')
                            control_torrent(torrent_id, "delete")
                            continue
                ui_print('[torbox] error: no streamable version could be selected for release: ' + release.title)
                return False
            else:
                response = create_torrent(
                    release.download[0],
                    add_only_if_cached=add_only_if_cached,
                )
                torrent_id = _torrent_id_from_create_response(response, release)
                ui_print(
                    '[torbox] adding uncached release: ' + release.title
                    + (" with torrent_id=" + str(torrent_id) if torrent_id is not None else "")
                )
                return torrent_id is not None
        else:
            ui_print('[torbox] error: rejecting release: "' + release.title + '" because it doesnt match the allowed deviation "' + query + '"')
    return False


# (required) Check Function
def check(element, force=False):
    if force:
        wanted = ['.*']
    else:
        wanted = element.files()
    unwanted = releases.sort.unwanted
    wanted_patterns = list(zip(wanted, [regex.compile(r'(' + key + ')', regex.IGNORECASE) for key in wanted]))
    unwanted_patterns = list(zip(unwanted, [regex.compile(r'(' + key + ')', regex.IGNORECASE) for key in unwanted]))

    hashes = set()
    for release in element.Releases[:]:
        if len(release.hash) == 40:
            hashes.add(release.hash.lower())
        else:
            ui_print("[torbox] error (missing torrent hash): ignoring release '" + release.title + "'")
            element.Releases.remove(release)

    for release in element.Releases:
        release.files = []

    ui_print("[torbox] checking and sorting all release files ...", ui_settings.debug)
    hashes = list(hashes)
    for offset in range(0, len(hashes), CHECKCACHED_BATCH):
        batch = hashes[offset:offset + CHECKCACHED_BATCH]
        response = post_checkcached(batch)
        if response is None:
            continue
        cached_rows = []
        if hasattr(response, "data") and response.data is not None:
            if isinstance(response.data, list):
                cached_rows = response.data
        for release in element.Releases:
            release_hash = release.hash.lower()
            for t in cached_rows:
                if t.hash == release_hash and 'TB' not in release.cached:
                    version_files = []
                    for file_ in t.files:
                        debrid_file = file(file_, file_.name, file_.size, wanted_patterns, unwanted_patterns)
                        version_files.append(debrid_file)
                    release.files += [version(version_files), ]

                    release.files.sort(key=lambda x: len(x.files), reverse=True)
                    release.files.sort(key=lambda x: x.wanted, reverse=True)
                    release.files.sort(key=lambda x: x.unwanted, reverse=False)
                    release.wanted = release.files[0].wanted
                    release.unwanted = release.files[0].unwanted
                    release.size = release.files[0].size
                    release.cached += ['TB']

    ui_print("done", ui_settings.debug)
