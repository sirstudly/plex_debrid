# import modules
from ui.ui_print import *
import releases
import base64
import json
name = "torrentsdb"

request_timeout_sec = "60"
rate_limit_sec = "2"  # minimum number of seconds between requests
manifest_json_url = ""


def request(func, *args):
    try:
        response = func(*args)
        if hasattr(response, "status_code") and response.status_code != 200:
            ui_print(f'[torrentsdb] error {str(response.status_code)}: failed response from torrentsdb. {response.content.decode("utf-8")}')
            return []

    except requests.exceptions.Timeout:
        ui_print('[torrentsdb] error: request timed out.')
        return []
    except Exception as e:
        ui_print('[torrentsdb] error: ' + str(e))
        return []

    try:
        json_response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        if hasattr(response, "content"):
            ui_print('[torrentsdb] error: unable to parse response:' + response.content.decode("utf-8"))
        else:
            ui_print('[torrentsdb] error: unable to parse response.')
        ui_print('[torrentsdb] ' + str(e), ui_settings.debug)
        return []
    return json_response


def get(session: requests.Session, url: str) -> requests.Response:
    ui_print(f"[torrentsdb] GET url: {url} ...", ui_settings.debug)
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
            if setting.name == "TorrentsDB Scraper Parameters":
                setting.setup()
        if cls.name not in active:
            active += [cls.name]


def scrape(query, altquery):
    from scraper.services import active
    if 'torrentsdb' not in active:
        return []

    url_search = regex.search(r"(stremio:\/\/[^\/]+|https?:\/\/[^\/]+).*manifest.json", manifest_json_url, regex.I)
    if not url_search:
        ui_print('[torrentsdb] error: the scraper parameters URL is not configured correctly: ' + manifest_json_url)
        return []
    base_url = url_search.group(1)
    if base_url.startswith("stremio://"):
        base_url = base_url.replace("stremio://", "https://")

    if altquery == "(.*)":
        altquery = query
    type = ("show" if regex.search(r'(S[0-9]|complete|S\?[0-9])', altquery, regex.I) else "movie")

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
        ui_print('[torrentsdb] error: search missing IMDB ID for query: ' + query)
        return []

    ui_print(f'[torrentsdb]: searching for {type}s with ID={imdb_id}', ui_settings.debug)
    session = custom_session(get_rate_limit=float(rate_limit_sec), post_rate_limit=float(rate_limit_sec))
    if type == 'movie':
        return scrape_imdb_movie(session, base_url, _get_base64_config(), imdb_id)
    return scrape_imdb_series(session, base_url, _get_base64_config(), imdb_id, s, e)


def scrape_imdb_movie(session: requests.Session, base_url: str, base64_config: str, imdb_id: str) -> list:
    return collate_releases_from_response(request(get, session, f'{base_url}/{base64_config}/stream/movie/{imdb_id}.json'))


def scrape_imdb_series(session: requests.Session, base_url: str, base64_config: str, imdb_id: str, season: int = 1, episode: int = 1) -> list:
    return collate_releases_from_response(request(get, session, f'{base_url}/{base64_config}/stream/series/{imdb_id}:{str(season)}:{str(episode)}.json'))


def collate_releases_from_response(response: requests.Response) -> list:
    scraped_releases = []
    if not hasattr(response, "streams"):
        if response is not None:
            ui_print('[torrentsdb] error: ' + repr(response))
        return scraped_releases

    ui_print(f"[torrentsdb] found {str(len(response.streams))} streams", ui_settings.debug)
    for result in response.streams:

        if hasattr(result, "title") and (result.title == "Invalid TorrentsDB config." or regex.search(r'(?<=Invalid )(.*)(?= account)', result.title)):
            ui_print(f'[torrentsdb] error: {result.title}')
            return scraped_releases
        elif not hasattr(result, "title"):
            ui_print(f'[torrentsdb] error: Missing title in result')
            continue
        elif not hasattr(result, "infoHash"):
            ui_print(f'[torrentsdb] error: Missing infoHash in result {result.title}')
            continue

        try:
            # Extract title - everything before the 📅 icon, remove newlines
            title = result.title.split("📅")[0].replace("\n", " ").strip()
            infohash = result.infoHash

            if not infohash:
                ui_print(f'[torrentsdb]: error: infohash not found for title: {title}')
                continue

            # Parse size from title (format: "💾 14.08 GB" or "💾 995.30 MB")
            size = 0
            size_match = regex.search(r'💾 ([0-9.]+) (GB|MB)', result.title)
            if size_match:
                size_value = float(size_match.group(1))
                size_unit = size_match.group(2)
                if size_unit == "GB":
                    size = size_value
                elif size_unit == "MB":
                    size = size_value / 1000

            # Build magnet link with additional trackers from sources if available
            links = ['magnet:?xt=urn:btih:' + infohash + '&dn=&tr=']
            if hasattr(result, "sources") and result.sources:
                # Add tracker URLs from sources
                trackers = []
                for source in result.sources:
                    if source.startswith("tracker:"):
                        trackers.append(source[8:])  # Remove "tracker:" prefix
                if trackers:
                    # Replace the basic magnet link with one that includes trackers
                    links = ['magnet:?xt=urn:btih:' + infohash + '&dn=&tr=' + '&tr='.join(trackers)]
            
            # Parse seeds from title (format: "👤 874")
            seeds = 0
            seeds_match = regex.search(r'👤 ([0-9]+)', result.title)
            if seeds_match:
                seeds = int(seeds_match.group(1))
            
            # Parse source from title (format: "⚙️ knaben")
            source = "unknown"
            source_match = regex.search(r'⚙️ ([^\n]+)', result.title)
            if source_match:
                source = source_match.group(1).strip()
            
            scraped_releases += [releases.release('[torrentsdb: '+source+']', 'torrent', title, [], size, links, seeds)]

        except Exception as e:
            ui_print('[torrentsdb] stream parsing error: ' + str(e))
            continue
    return scraped_releases


# Retrieves the base64 configuration parameters from manifest_json_url
# If it isn't defined, then create a default profile
def _get_base64_config() -> str:

    if manifest_json_url.endswith("manifest.json"):
        return manifest_json_url.split("/")[-2]

    return base64.b64encode(json.dumps({
        "qualityfilter": ["brremux","4k","scr","cam"]
    }).encode("utf-8")).decode("utf-8")
