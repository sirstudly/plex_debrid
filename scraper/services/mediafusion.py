# import modules
from ui.ui_print import *
import releases
import urllib.parse
name = "mediafusion"

base_url = "https://mediafusion.elfhosted.com"
api_password = ""
request_timeout_sec = "60"
rate_limit_sec = "15"  # minimum number of seconds between requests
manifest_json_url = ""
mediafusion_encrypted_str = ""


def request(func, *args):
    try:
        response = func(*args)
        if hasattr(response, "status_code") and response.status_code != 200:
            ui_print(f'[mediafusion] error {str(response.status_code)}: failed response from mediafusion. {response.content.decode("utf-8")}')
            return []

    except requests.exceptions.Timeout:
        ui_print('[mediafusion] error: request timed out.')
        return []
    except Exception as e:
        ui_print('[mediafusion] error: ' + str(e))
        return []

    try:
        if not hasattr(response, "content") or len(response.content) == 0:
            return []
        json_response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print('[mediafusion] error: unable to parse response:' + response.content.decode("utf-8") + " " + str(e))
        return []
    return json_response


def get(session: requests.Session, url: str) -> requests.Response:
    ui_print(f"[mediafusion] GET url: {url} ...", ui_settings.debug)
    response = session.get(url, timeout=int(request_timeout_sec))
    ui_print("done", ui_settings.debug)
    return response


def post(session: requests.Session, url: str, body: dict) -> requests.Response:
    ui_print(f"[mediafusion] POST url: {url} with {repr(body)} ...", ui_settings.debug)
    response = session.post(url, json=body, timeout=int(request_timeout_sec))
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
        if not cls.name in active:
            active += [cls.name]


def scrape(query, altquery):
    global base_url
    from scraper.services import active
    if 'mediafusion' not in active:
        return []

    # Stream endpoint requires user's manifest URL (with RD/debrid config) to return streams with info_hash
    if not manifest_json_url or not manifest_json_url.strip().endswith("manifest.json"):
        ui_print("[mediafusion] error: MediaFusion Scraper Parameters (manifest URL) must be set. Visit https://mediafusion.elfhosted.com/app/configure and paste your manifest URL.")
        return []

    url_search = regex.search(r"(https?:\/\/[^\/]+)", manifest_json_url.strip(), regex.I)
    effective_base_url = url_search.group(1) if url_search else base_url
    if effective_base_url.endswith('/'):
        effective_base_url = effective_base_url[:-1]

    if base_url.endswith('/'):
        base_url = base_url[:-1]

    manual_search = False
    if altquery == "(.*)":
        altquery = query
        manual_search = True
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

    plain_text = ""
    imdb_ids = []
    session = custom_session(get_rate_limit=float(rate_limit_sec), post_rate_limit=float(rate_limit_sec))
    if regex.search(r'(tt[0-9]+)', altquery, regex.I):
        imdb_ids += [regex.search(r'(tt[0-9]+)', altquery, regex.I).group()]
    elif manual_search:
        plain_text = urllib.parse.quote(query)
        try:
            if type == "show":
                url = f"{effective_base_url}/catalog/series/mediafusion_search_series/search={plain_text}.json"
                meta = request(get, session, url)
            else:
                url = f"{effective_base_url}/catalog/movie/mediafusion_search_movies/search={plain_text}.json"
                meta = request(get, session, url)
            # collate all matched IMDB IDs (tt* required for stream endpoint)
            imdb_ids += [m.id for m in meta.metas if regex.search(r'(tt[0-9]+)', str(m.id), regex.I)]
        except:
            try:
                if type == "movie":
                    type = "show"
                    s = 1
                    e = 1
                    url = f"{effective_base_url}/catalog/series/mediafusion_search_series/search={plain_text}.json"
                    meta = request(get, session, url)
                else:
                    type = "movie"
                    url = f"{effective_base_url}/catalog/movie/mediafusion_search_movies/search={plain_text}.json"
                    meta = request(get, session, url)
                # collate all matched IMDB IDs (tt* required for stream endpoint)
                imdb_ids += [m.id for m in meta.metas if regex.search(r'(tt[0-9]+)', str(m.id), regex.I)]
            except Exception as e:
                ui_print('[mediafusion] error: could not find IMDB ID. ' + str(e))
                return []
    else:
        ui_print('[mediafusion] error: search missing IMDB ID for query: ' + query)
        return []

    global mediafusion_encrypted_str
    if mediafusion_encrypted_str == "":
        try:
            mediafusion_encrypted_str = _get_encrypted_string(session)
        except Exception as e:
            ui_print('[mediafusion] error: Failed to compute encrypted string. ' + str(e))
            return []

    ui_print(f'[mediafusion]: searching for {type}s with IDs [{str(imdb_ids)}]', ui_settings.debug)
    if type == 'movie':
        return flatten_list([scrape_imdb_movie(session, effective_base_url, imdb_id, plain_text) for imdb_id in imdb_ids])
    return flatten_list([scrape_imdb_series(session, effective_base_url, imdb_id, s, e) for imdb_id in imdb_ids])


def scrape_imdb_movie(session: requests.Session, effective_base_url: str, imdb_id: str, query_text: str = None) -> list:
    url = f'{effective_base_url}/{mediafusion_encrypted_str}/stream/movie/{imdb_id}.json'
    response = request(get, session, url)

    # fallback to TV series search if we don't get any results
    if not hasattr(response, "streams") or len(response.streams) == 0:
        if query_text is not None and query_text != "":
            try:
                url = f"{effective_base_url}/catalog/series/mediafusion_search_series/search={query_text}.json"
                meta = request(get, session, url)
                return [scrape_imdb_series(session, effective_base_url, m.id, 1, 1) for m in meta.metas if regex.search(r'(tt[0-9]+)', str(m.id), regex.I)]
            except Exception as e:
                ui_print(f'[mediafusion] error: could not find IMDB ID for {query_text}. ' + str(e))
                return []
    return collate_releases_from_response(response)


def scrape_imdb_series(session: requests.Session, effective_base_url: str, imdb_id: str, season: int = 1, episode: int = 1) -> list:
    try:
        url = f'{effective_base_url}/{mediafusion_encrypted_str}/stream/series/{imdb_id}:{str(season)}:{str(episode)}.json'
        return collate_releases_from_response(request(get, session, url))
    except Exception as e:
        ui_print('[mediafusion] error: ' + str(e))
        return []


def _extract_info_hash(result) -> str | None:
    """Extract 40-char hex info_hash from stream result (Stremio/MediaFusion may use different fields)."""
    # Standard Stremio field
    if hasattr(result, "infoHash") and result.infoHash:
        h = getattr(result, "infoHash", "").strip()
        if regex.match(r"^[a-fA-F0-9]{40}$", h):
            return h.lower()
    # URL: query param (legacy), magnet btih, or MediaFusion playback path (last segment = info_hash)
    if hasattr(result, "url") and result.url:
        u = result.url.strip()
        if "?info_hash=" in u:
            h = u.split("?info_hash=")[1].split("&")[0].strip()
            if regex.match(r"^[a-fA-F0-9]{40}$", h):
                return h.lower()
        # Magnet: ?xt=urn:btih:...
        btih = regex.search(r"urn:btih:([a-fA-F0-9]{40})", u)
        if btih:
            return btih.group(1).lower()
        # MediaFusion/ElfHosted playback URL: .../playback/{token}/{40-char-hex} (last path segment is info_hash)
        if "/playback/" in u:
            path = u.split("?")[0].rstrip("/")
            last_segment = path.split("/")[-1] if "/" in path else ""
            if len(last_segment) == 40 and regex.match(r"^[a-fA-F0-9]{40}$", last_segment):
                return last_segment.lower()
    # Comet-style: behaviorHints.bingeGroup last segment is infohash (e.g. "mediafusion|realdebrid|<40-char>")
    if hasattr(result, "behaviorHints") and hasattr(result.behaviorHints, "bingeGroup"):
        binge_group = getattr(result.behaviorHints, "bingeGroup", "") or ""
        parts = binge_group.split("|")
        if parts:
            h = parts[-1].strip()
            if len(h) == 40 and regex.match(r"^[a-fA-F0-9]{40}$", h):
                return h.lower()
    return None


def collate_releases_from_response(response: requests.Response) -> list:
    scraped_releases = []
    if not hasattr(response, "streams"):
        if response is not None:
            ui_print('[mediafusion] error: ' + repr(response))
        return scraped_releases

    ui_print(f"[mediafusion] found {str(len(response.streams))} streams", ui_settings.debug)
    for result in response.streams:
        # Skip placeholders / invalid config messages
        if hasattr(result, "description") and result.description and (
            "Invalid " in result.description or "First search for this media" in result.description
        ):
            continue

        info_hash = _extract_info_hash(result)
        if not info_hash:
            continue

        try:
            title = ""
            if hasattr(result, "behaviorHints") and hasattr(result.behaviorHints, "filename"):
                title = (getattr(result.behaviorHints, "filename", "") or "").strip()
            if not title and hasattr(result, "description") and result.description:
                title = result.description.split("\n💾")[0].replace("📂 ", "").strip()
            if not title:
                title = "Unknown"

            size = 0
            if hasattr(result, "behaviorHints") and hasattr(result.behaviorHints, "videoSize") and result.behaviorHints.videoSize is not None:
                size = int(result.behaviorHints.videoSize) / 1000000000

            links = ['magnet:?xt=urn:btih:' + info_hash + '&dn=&tr=']

            seeds = 0
            if hasattr(result, "description") and result.description and regex.search(r'(?<=👤 )([0-9]+)', result.description):
                seeds = int(regex.search(r'(?<=👤 )([0-9]+)', result.description).group())

            source = "unknown"
            if hasattr(result, "description") and result.description and regex.search(r'(?<=🔗 )(.*)(?=\n|$)', result.description):
                source = regex.search(r'(?<=🔗 )(.*)(?=\n|$)', result.description).group()

            scraped_releases += [releases.release(
                '[mediafusion: ' + source + ']', 'torrent', title, [], size, links, seeds)]
        except Exception as e:
            ui_print('[mediafusion] stream parsing error: ' + str(e))
            continue
    return scraped_releases


# Gets the config token from the user's manifest URL (required for stream endpoint to return streams with info_hash).
def _get_encrypted_string(session: requests.Session) -> str:
    if manifest_json_url and manifest_json_url.strip().endswith("manifest.json"):
        return manifest_json_url.strip().rstrip("/").split("/")[-2]

    # Default payload for /encrypt-user-data when manifest URL is not set (matches current MediaFusion API)
    _provider = {
        "name": "Provider",
        "service": "realdebrid",
        "token": api_password,
        "enable_watchlist_catalogs": True,
        "qbittorrent_config": None,
        "only_show_cached_streams": False,
        "use_mediaflow": True,
        "sabnzbd_config": None,
        "nzbget_config": None,
        "nzbdav_config": None,
        "easynews_config": None,
        "priority": 0,
        "enabled": True,
    }
    payload = {
        "streaming_providers": [_provider],
        "streaming_provider": _provider,
        "selected_catalogs": [],
        "selected_resolutions": ["1080p", "720p", "576p", "480p", "360p", "240p", None],
        "enable_catalogs": True,
        "enable_imdb_metadata": False,
        "max_size": "inf",
        "min_size": 0,
        "max_streams_per_resolution": 50,
        "nudity_filter": ["Disable"],
        "certification_filter": ["Disable"],
        "language_sorting": [
            "English", "Tamil", "Hindi", "Malayalam", "Kannada", "Telugu", "Chinese",
            "Russian", "Arabic", "Japanese", "Korean", "Taiwanese", "Latino", "French",
            "Spanish", "Portuguese", "Italian", "German", "Ukrainian", "Polish", "Czech",
            "Thai", "Indonesian", "Vietnamese", "Dutch", "Bengali", "Turkish", "Greek",
            "Swedish", "Romanian", "Hungarian", "Finnish", "Norwegian", "Danish", "Hebrew",
            "Lithuanian", "Punjabi", "Marathi", "Gujarati", "Bhojpuri", "Nepali", "Urdu",
            "Tagalog", "Filipino", "Malay", "Mongolian", "Armenian", "Georgian", None,
        ],
        "quality_filter": ["BluRay/UHD", "WEB/HD", "DVD/TV/SAT", "Unknown"],
        "hdr_filter": ["HDR10", "HDR10+", "Dolby Vision", "HLG", "SDR"],
        "live_search_streams": False,
        "enable_usenet_streams": False,
        "prefer_usenet_over_torrent": False,
        "enable_telegram_streams": False,
        "enable_acestream_streams": False,
        "max_streams": 100,
        "stream_type_grouping": "separate",
        "stream_type_order": ["torrent", "telegram", "usenet", "http", "acestream", "youtube"],
        "provider_grouping": "separate",
        "stream_name_filter_mode": "disabled",
        "stream_name_filter_patterns": [],
        "stream_name_filter_use_regex": False,
        "torrent_sorting_priority": [
            {"key": "cached", "direction": "desc"},
            {"key": "resolution", "direction": "desc"},
            {"key": "quality", "direction": "desc"},
            {"key": "language", "direction": "desc"},
            {"key": "size", "direction": "desc"},
            {"key": "seeders", "direction": "desc"},
            {"key": "created_at", "direction": "desc"},
        ],
        "indexer_config": None,
        "telegram_config": None,
    }

    response = request(post,session, f"{base_url}/encrypt-user-data", payload)
    if not hasattr(response, "encrypted_str"):
        raise Exception("[mediafusion] Unable to retrieve encrypted string")
    return response.encrypted_str


def flatten_list(nested_list):
    return [item for sublist in nested_list for item in sublist]