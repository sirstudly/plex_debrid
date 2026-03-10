# import modules
from ui.ui_print import *
import releases
import json
name = "debridio"

# Default base URL when derived from manifest (Debridio Stremio addon)
base_url = "https://debridio.com"
request_timeout_sec = "60"
rate_limit_sec = "10"
manifest_json_url = ""  # required: user's Debridio manifest URL from configure/copy link


def request(func, *args):
    try:
        response = func(*args)
        if hasattr(response, "status_code") and response.status_code != 200:
            ui_print(f'[debridio] error {str(response.status_code)}: failed response from debridio. {response.content.decode("utf-8")}')
            return []

    except requests.exceptions.Timeout:
        ui_print('[debridio] error: request timed out.')
        return []
    except Exception as e:
        ui_print('[debridio] error: ' + str(e))
        return []

    try:
        if not hasattr(response, "content") or len(response.content) == 0:
            return []
        json_response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print('[debridio] error: unable to parse response:' + response.content.decode("utf-8") + " " + str(e))
        return []
    return json_response


def get(session: requests.Session, url: str) -> requests.Response:
    ui_print(f"[debridio] GET url: {url} ...", ui_settings.debug)
    response = session.get(url, timeout=int(request_timeout_sec))
    ui_print("done", ui_settings.debug)
    return response


def setup(cls, new=False):
    from settings import settings_list
    from scraper.services import active
    settings = []
    for category, allsettings in settings_list:
        for setting in allsettings:
            if setting.cls == cls:
                settings += [setting]
    if settings == []:
        if not cls.name in active:
            active += [cls.name]
    back = False
    if not new:
        while not back:
            print("0) Back")
            indices = []
            for index, setting in enumerate(settings):
                print(str(index + 1) + ') ' + setting.name)
                indices += [str(index + 1)]
            print()
            if settings == []:
                print("Nothing to edit!")
                print()
                time.sleep(3)
                return
            choice = input("Choose an action: ")
            if choice in indices:
                settings[int(choice) - 1].input()
                if not cls.name in active:
                    active += [cls.name]
                back = True
            elif choice == '0':
                back = True
    else:
        for setting in settings:
            if setting.name == "Debridio Scraper Parameters":
                setting.setup()
        if cls.name not in active:
            active += [cls.name]


def scrape(query, altquery):
    from scraper.services import active
    if 'debridio' not in active:
        return []

    if not manifest_json_url or not manifest_json_url.strip().endswith("manifest.json"):
        ui_print("[debridio] error: Debridio Scraper Parameters (manifest URL) must be set. Get your manifest URL from https://debridio.com after configuring your addon.")
        return []

    manifest_stripped = manifest_json_url.strip().rstrip("/")
    if not manifest_stripped.endswith("/manifest.json"):
        ui_print("[debridio] error: manifest URL must end with /manifest.json")
        return []
    parts = manifest_stripped.rsplit("/", 2)
    if len(parts) != 3:
        ui_print("[debridio] error: could not parse base URL and config token from manifest URL.")
        return []
    base = parts[0]
    config_token = parts[1]
    if base.endswith("/"):
        base = base[:-1]

    if altquery == "(.*)":
        altquery = query
    type = ("show" if regex.search(
        r'(S[0-9]|complete|S\?[0-9])', altquery, regex.I) else "movie")

    if type == "show":
        s = (regex.search(r'(?<=S)([0-9]+)', altquery, regex.I).group()
             if regex.search(r'(?<=S)([0-9]+)', altquery, regex.I) else None)
        e = (regex.search(r'(?<=E)([0-9]+)', altquery, regex.I).group()
             if regex.search(r'(?<=E)([0-9]+)', altquery, regex.I) else None)
        if s is None or int(s) == 0:
            s = 1
        if e is None or int(e) == 0:
            e = 1

    if not regex.search(r'(tt[0-9]+)', altquery, regex.I):
        ui_print('[debridio] error: search missing IMDB ID for query: ' + query)
        return []
    imdb_id = regex.search(r'(tt[0-9]+)', altquery, regex.I).group()

    ui_print(f'[debridio]: searching for {type}s with ID={imdb_id}', ui_settings.debug)
    session = custom_session(get_rate_limit=float(rate_limit_sec), post_rate_limit=float(rate_limit_sec))
    if type == 'movie':
        return scrape_imdb_movie(session, base, config_token, imdb_id)
    return scrape_imdb_series(session, base, config_token, imdb_id, s, e)


def scrape_imdb_movie(session: requests.Session, base_url: str, config_token: str, imdb_id: str) -> list:
    url = f'{base_url}/{config_token}/stream/movie/{imdb_id}.json'
    return collate_releases_from_response(request(get, session, url))


def scrape_imdb_series(session: requests.Session, base_url: str, config_token: str, imdb_id: str, season: int = 1, episode: int = 1) -> list:
    url = f'{base_url}/{config_token}/stream/series/{imdb_id}:{str(season)}:{str(episode)}.json'
    return collate_releases_from_response(request(get, session, url))


def _extract_info_hash(result) -> str | None:
    """Extract 40-char hex info_hash from Debridio stream result. Infohash is in the play URL path (segment before filename)."""
    if hasattr(result, "infoHash") and result.infoHash:
        h = getattr(result, "infoHash", "").strip()
        if regex.match(r"^[a-fA-F0-9]{40}$", h):
            return h.lower()
    if hasattr(result, "url") and result.url:
        u = result.url.strip()
        path = u.split("?")[0].rstrip("/")
        segments = path.split("/")
        # Debridio: .../play/movie|serie/.../TOKEN/INFOHASH/filename -> infohash is second-to-last segment
        if len(segments) >= 2:
            candidate = segments[-2]
            if len(candidate) == 40 and regex.match(r"^[a-fA-F0-9]{40}$", candidate):
                return candidate.lower()
        # Fallbacks
        if "?info_hash=" in u:
            h = u.split("?info_hash=")[1].split("&")[0].strip()
            if regex.match(r"^[a-fA-F0-9]{40}$", h):
                return h.lower()
        btih = regex.search(r"urn:btih:([a-fA-F0-9]{40})", u)
        if btih:
            return btih.group(1).lower()
    return None


def collate_releases_from_response(response) -> list:
    scraped_releases = []
    if not hasattr(response, "streams"):
        if response is not None:
            ui_print('[debridio] error: ' + repr(response))
        return scraped_releases

    ui_print(f"[debridio] found {str(len(response.streams))} streams", ui_settings.debug)
    for result in response.streams:
        # Debridio uses "title" (not "description") for the long text with size/source
        long_text = getattr(result, "title", None) or getattr(result, "description", None) or ""
        if long_text and ("Invalid " in long_text or "First search for this media" in long_text):
            continue

        info_hash = _extract_info_hash(result)
        if not info_hash:
            continue

        try:
            release_title = ""
            if hasattr(result, "behaviorHints") and hasattr(result.behaviorHints, "filename"):
                release_title = (getattr(result.behaviorHints, "filename", "") or "").strip()
            if not release_title and long_text:
                release_title = long_text.split("\n")[0].strip()
            if not release_title:
                release_title = "Unknown"

            size = 0
            size_m = regex.search(r"([0-9.]+)\s*GB(?:\s|$|\u2699)", long_text)
            size_mb = regex.search(r"([0-9.]+)\s*MB(?:\s|$|\u2699)", long_text)
            if size_m:
                size = float(size_m.group(1))
            elif size_mb:
                size = float(size_mb.group(1)) / 1000.0

            links = ['magnet:?xt=urn:btih:' + info_hash + '&dn=&tr=']

            seeds = 0
            # Debridio shows seeds as 👤 (U+1F464) followed by number or "undefined"
            seeds_m = regex.search(r"\ud83d\udc64\s*(\d+)", long_text)
            if seeds_m:
                try:
                    seeds = int(seeds_m.group(1))
                except (ValueError, IndexError):
                    pass

            source = "unknown"
            # Debridio: tracker name after gear ⚙️ (e.g. "⚙️ YTS"; sometimes "👤 7 ⚙️ ExtremlymTorrents")
            source_matches = regex.findall(r"\u2699\ufe0f\s*([^\n]+)", long_text)
            if source_matches:
                source = source_matches[-1].strip()

            scraped_releases += [releases.release(
                '[debridio: ' + source + ']', 'torrent', release_title, [], size, links, seeds)]
        except Exception as e:
            ui_print('[debridio] stream parsing error: ' + str(e))
            continue
    return scraped_releases
