# import modules
from ui.ui_print import *
import releases
import base64
import json
name = "comet"

# Default config when no manifest URL is set (placeholder RealDebrid API key; searches still work)
_DEFAULT_COMET_CONFIG = {
    "maxResultsPerResolution": 0,
    "maxSize": 0,
    "cachedOnly": False,
    "sortCachedUncachedTogether": False,
    "removeTrash": True,
    "resultFormat": ["all"],
    "debridServices": [
        {
            "service": "realdebrid",
            "apiKey": "REALDEBRIDAPIKEYGOESHEREBUTITSNOTREQUIREDFORSEARCHES"
        }
    ],
    "enableTorrent": False,
    "deduplicateStreams": False,
    "scrapeDebridAccountTorrents": False,
    "debridStreamProxyPassword": "",
    "languages": {
        "required": [],
        "allowed": [],
        "exclude": [],
        "preferred": []
    },
    "resolutions": {
        "r2160p": False,
        "r1440p": False
    },
    "options": {
        "remove_ranks_under": -10000000000,
        "allow_english_in_languages": False,
        "remove_unknown_languages": False
    }
}

request_timeout_sec = "60"
rate_limit_sec = "10"  # minimum number of seconds between requests
manifest_json_url = ""  # optional; if set (valid manifest URL), used for base URL and config; else default config with placeholder API key is used


def request(func, *args):
    try:
        response = func(*args)
        if hasattr(response, "status_code") and response.status_code != 200:
            ui_print(f'[comet] error {str(response.status_code)}: failed response from comet. {response.content.decode("utf-8")}')
            return []

    except requests.exceptions.Timeout:
        ui_print('[comet] error: request timed out.')
        return []
    except Exception as e:
        ui_print('[comet] error: ' + str(e))
        return []

    try:
        json_response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        if hasattr(response, "content"):
            ui_print('[comet] error: unable to parse response:' + response.content.decode("utf-8"))
        else:
            ui_print('[comet] error: unable to parse response.')
        ui_print('[comet] ' + str(e), ui_settings.debug)
        return []
    return json_response


def get(session: requests.Session, url: str) -> requests.Response:
    ui_print(f"[comet] GET url: {url} ...", ui_settings.debug)
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
            if setting.name == "Comet Scraper Parameters":
                setting.setup()
        if cls.name not in active:
            active += [cls.name]


def scrape(query, altquery):
    from scraper.services import active
    if 'comet' not in active:
        return []

    url_search = regex.search(r"(https?:\/\/[^\/]+).*manifest\.json", manifest_json_url or "", regex.I)
    if url_search and manifest_json_url and manifest_json_url.strip().endswith("manifest.json"):
        base_url = url_search.group(1)
    else:
        base_url = "https://comet.elfhosted.com"
    base64_config = _get_base64_config()

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

    if regex.search(r'(tt[0-9]+)', altquery, regex.I):
        imdb_id = regex.search(r'(tt[0-9]+)', altquery, regex.I).group()
    else:
        ui_print('[comet] error: search missing IMDB ID for query: ' + query)
        return []

    ui_print(f'[comet]: searching for {type}s with ID={imdb_id}', ui_settings.debug)
    session = custom_session(get_rate_limit=float(rate_limit_sec), post_rate_limit=float(rate_limit_sec))
    if type == 'movie':
        return scrape_imdb_movie(session, base_url, base64_config, imdb_id)
    return scrape_imdb_series(session, base_url, base64_config, imdb_id, s, e)


def scrape_imdb_movie(session: requests.Session, base_url: str, base64_config: str, imdb_id: str) -> list:
    return collate_releases_from_response(request(get, session, f'{base_url}/{base64_config}/stream/movie/{imdb_id}.json'))


def scrape_imdb_series(session: requests.Session, base_url: str, base64_config: str, imdb_id: str, season: int = 1, episode: int = 1) -> list:
    return collate_releases_from_response(request(get, session, f'{base_url}/{base64_config}/stream/series/{imdb_id}:{str(season)}:{str(episode)}.json'))


def collate_releases_from_response(response: requests.Response) -> list:
    scraped_releases = []
    if not hasattr(response, "streams"):
        if response is not None:
            ui_print('[comet] error: ' + repr(response))
        return scraped_releases

    ui_print(f"[comet] found {str(len(response.streams))} streams", ui_settings.debug)
    for result in response.streams:

        if hasattr(result, "description") and (result.description == "Invalid Comet config." or regex.search(r'(?<=Invalid )(.*)(?= account)', result.description)):
            ui_print(f'[comet] error: {result.description}')
            return scraped_releases

        # Skip loading placeholder (no behaviorHints or "First search for this media...")
        if hasattr(result, "description") and "First search for this media" in result.description:
            continue
        if not hasattr(result, "behaviorHints") or not hasattr(result.behaviorHints, "bingeGroup"):
            continue

        try:
            # Infohash is the last segment of behaviorHints.bingeGroup (e.g. "comet|realdebrid|<40-char-hex>")
            binge_group = getattr(result.behaviorHints, "bingeGroup", "") or ""
            parts = binge_group.split("|")
            infohash = parts[-1].strip() if parts else None
            if not infohash or len(infohash) != 40 or not regex.match(r"^[a-fA-F0-9]{40}$", infohash):
                continue

            title = ""
            if hasattr(result, "description") and result.description:
                title = result.description.split("\n")[0].strip()
            if not title and hasattr(result.behaviorHints, "filename"):
                title = getattr(result.behaviorHints, "filename", "") or ""

            size = 0
            if hasattr(result.behaviorHints, "videoSize") and result.behaviorHints.videoSize is not None:
                size = int(result.behaviorHints.videoSize) / 1000000000

            links = ['magnet:?xt=urn:btih:' + infohash + '&dn=&tr=']
            seeds = 0  # not available
            source = "unknown"
            if hasattr(result, "description") and result.description and regex.search(r'(?<=🔎 )(.*)(?=\n|$)', result.description):
                source = regex.search(r'(?<=🔎 )(.*)(?=\n|$)', result.description).group()
            scraped_releases += [releases.release(
                '[comet: ' + source + ']', 'torrent', title or "Unknown", [], size, links, seeds)]
        except Exception as e:
            ui_print('[comet] stream parsing error: ' + str(e))
            continue
    return scraped_releases


# Retrieves the base64 configuration from manifest_json_url, or returns a default config if none is set.
def _get_base64_config() -> str:
    if manifest_json_url and manifest_json_url.strip().endswith("manifest.json"):
        return manifest_json_url.strip().rstrip("/").split("/")[-2]
    return base64.b64encode(json.dumps(_DEFAULT_COMET_CONFIG).encode("utf-8")).decode("utf-8")
