import urllib.request
import urllib.parse
from ui.ui_print import *
import releases
import re

name = "thepiratebay"
base_url = "https://apibay.org"
session = urllib.request.build_opener()


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def scrape(query, altquery):
    from scraper.services import active

    scraped_releases = []
    if 'thepiratebay' in active:
        q = query.replace('.?', '').replace("'", "").replace("’", "").replace('.', ' ').strip(".").strip(" ")
        ui_print("[thepiratebay] using extended query: " + q, ui_settings.debug)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
        url = base_url + '/q.php?q=' + urllib.parse.quote(q, safe=':/')
        try:
            ui_print("[thepiratebay] Sending GET request to API URL: " + url, ui_settings.debug)
            request = urllib.request.Request(url, headers=headers)
            response = session.open(request)
            status_code = response.getcode()

            if status_code == 200:
                content = response.read().decode('utf-8')
                response_json = json.loads(content)
                torrents = response_json if isinstance(response_json, list) else []

                # Check for 0 results
                if torrents and (torrents[0].get('name') == "No results returned" or 'total_found' in torrents[0]):
                    ui_print("[thepiratebay] No torrents found", ui_settings.debug)
                else:
                    ui_print(f"[thepiratebay] Found {len(torrents)} torrent(s)", ui_settings.debug)

                    for torrent in torrents:
                        title = torrent.get('name')
                        title = re.sub(r'[^\w\s\.\-]', '', title)
                        download = 'magnet:?xt=urn:btih:' + torrent.get('info_hash')
                        size_bytes = int(torrent.get('size', 0))
                        size = size_bytes / (1024 * 1024 * 1024)
                        seeders = int(torrent.get('seeders', 0))

                        if regex.match(r'(' + altquery.replace('.', '\.').replace("\.*", ".*") + ')', title, regex.I):
                            scraped_releases += [releases.release('[thepiratebay]', 'torrent', title, [], size, [download], seeders=seeders)]
                            ui_print(f"[thepiratebay] Scraped release: title={title}, size={size:.2f} GB, seeders={seeders}", ui_settings.debug)
            else:
                ui_print("[thepiratebay] Failed to retrieve data from API. Status code: " + str(status_code), ui_settings.debug)

        except Exception as e:
            ui_print('[thepiratebay] error: exception: ' + str(e), ui_settings.debug)
    return scraped_releases