from ui.ui_print import *
import releases
from functools import lru_cache
import time
import urllib.parse

name = "torbox"
timeout_sec = 30
default_cache_timeout = 120  # TTL cache in seconds when querying torbox
session = requests.Session()


def setup(cls, new=False):
    from settings import settings_list
    from scraper.services import active
    settings = []
    for category, allsettings in settings_list:
        for setting in allsettings:
            if setting.cls == cls:
                settings += [setting]
    if settings == []:
        if cls.name not in active:
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
        print()


def scrape(query, altquery):
    from scraper.services import active
    ui_print("[torbox] searching for " + query + " accepting titles that regex match " + altquery, ui_settings.debug)
    if 'torbox' not in active:
        return []

    matches_regex = altquery
    if altquery == "(.*)":
        matches_regex = query

    # we need the imdb id when searching torrents on torbox
    imdb_ids = (imdb_lookup(query) if not regex.search(r'tt[0-9]+', matches_regex, regex.I)
                else ["imdb:" + regex.search(r'tt[0-9]+', matches_regex, regex.I).group()])

    # store the search request so we can get better results in subsequent iterations (if necessary)
    torbox_request(store_search, query)

    # flatten and remove duplicates
    return remove_duplicates(flatten(scrape_releases(imdb_id, matches_regex, altquery) for imdb_id in imdb_ids))


def scrape_releases(imdb_id, matches_regex, altquery):
    opts = ['metadata=false']
    if regex.search(r'(S[0-9]|complete|S\?[0-9])', matches_regex, regex.I):
        s = (regex.search(r'(?<=S)([0-9]+)', matches_regex, regex.I).group()
             if regex.search(r'(?<=S)([0-9]+)', matches_regex, regex.I) else None)
        e = (regex.search(r'(?<=E)([0-9]+)', matches_regex, regex.I).group()
             if regex.search(r'(?<=E)([0-9]+)', matches_regex, regex.I) else None)
        if s is not None and int(s) != 0:
            opts.append('season=' + str(int(s)))
        if e is not None and int(e) != 0:
            opts.append('episode=' + str(int(e)))

    json_response = torbox_request(search_query, "https://search-api.torbox.app/torrents/" + imdb_id + '?' + '&'.join(opts), get_ttl_hash())
    if not json_response or not hasattr(json_response, "torrents"):
        ui_print('[torbox] No torrents found.', ui_settings.debug)
        return []

    ui_print('[torbox] ' + str(len(json_response.torrents)) + ' results found.', ui_settings.debug)
    scraped_releases = []
    for result in json_response.torrents[:]:
        if regex.match(r'(' + altquery + ')', result.raw_title, regex.I):
            links = [result.magnet]
            seeders = result.last_known_seeders
            source = '[torbox: ' + result.tracker + ']' if result.tracker else '[torbox]'
            ui_print('[torbox] found release ' + result.raw_title, ui_settings.debug)
            scraped_releases += [releases.release(
                source, 'torrent', result.raw_title, [], float(result.size) / 1000000000, links, seeders)]
        else:
            ui_print('[torbox] skipping ' + result.raw_title + ' because it does not match deviation ' + altquery, ui_settings.debug)

    return scraped_releases


# Calls func(param) and returns the parsed JSON response if successful or [] if not
# When searching films, multiple calls may occur with the same IMDB id
# Temporarily Cache result so we don't make multiple identical calls within a short space of time
@lru_cache()
def torbox_request(func, param, ttl_hash=None):
    del ttl_hash  # to emphasize we don't use it and to shut pylint up
    try:
        response = func(param)

        if response.status_code != 200:
            ui_print('[torbox] error ' + str(response.status_code) + ': failed response from torbox. ' + response.content.decode("utf-8"))
            return []

    except requests.exceptions.Timeout:
        ui_print('[torbox] error: torbox request timed out.')
        return []
    except Exception as e:
        ui_print('[torbox] error: ' + str(e))
        return []

    try:
        json_response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print('[torbox] error: unable to parse response:' + response.content.decode("utf-8") + " " + str(e))
        return []

    if not json_response.success:
        ui_print('[torbox] error: response failed:' + response.content.decode("utf-8"))
        return []

    if hasattr(json_response, 'message') and json_response.message:
        ui_print('[torbox] response: ' + json_response.message, ui_settings.debug)
    if hasattr(json_response, 'detail') and json_response.detail:
        ui_print('[torbox] response: ' + json_response.detail, ui_settings.debug)

    return json_response.data


def search_query(url):
    ui_print("[torbox] search URL: " + url + " ...", ui_settings.debug)
    response = session.get(url, timeout=timeout_sec)
    ui_print("done", ui_settings.debug)
    return response


# search metadata by title and return a list of ids (eg. [imdb:tt1234567,imdb:tt7654321])
def imdb_lookup(query):
    return [row.id for row in torbox_request(search_query, "https://search-api.torbox.app/search/" + query, get_ttl_hash())]


def store_search(query):
    # refresh active torrents based on any search criteria for future requests
    url = "https://api.torbox.app/v1/api/torrents/storesearch?query=" + urllib.parse.quote(query)
    ui_print("[torbox] storing search: " + url + " ...", ui_settings.debug)
    response = session.put(url, timeout=timeout_sec)
    ui_print("done", ui_settings.debug)
    return response


def flatten(matrix):
    return [item for row in matrix for item in row]


# this is used for a TTL cache when querying torbox.
# see https://stackoverflow.com/a/55900800
def get_ttl_hash(seconds=default_cache_timeout):
    # Return the same value within `seconds` time period
    return round(time.time() / seconds)


def remove_duplicates(items):
    seen_items = set()
    new_list = []
    for release in items:
        if release.hash not in seen_items:
            seen_items.add(release.hash)
            new_list.append(release)
    return new_list
