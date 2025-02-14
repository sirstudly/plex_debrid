import urllib.request
import urllib.parse
import json
from ui.ui_print import *
import releases

name = "magnetDL"
session = urllib.request.build_opener()


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def scrape(query, altquery):
    from scraper.services import active
    scraped_releases = []
    if 'magnetDL' in active:
        ui_print("[magnetDL] using extended query: " + query, ui_settings.debug)

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}

        url = 'https://magnetdl.hair/api.php?url=/q.php?q=' + urllib.parse.quote(query) + '&cat=0'

        response = None
        try:
            ui_print("[magnetDL] Sending GET request to URL: " + url, ui_settings.debug)
            request = urllib.request.Request(url, headers=headers)
            response = session.open(request)
            status_code = response.getcode()

            if status_code == 200:
                content = response.read().decode('utf-8', errors='ignore')
                response_json = json.loads(content)
                torrents = response_json if isinstance(response_json, list) else []

                if torrents and (torrents[0].get('name') == "No results returned" or 'total_found' in torrents[0]):
                    ui_print(f"[magnetDL] No torrents found", ui_settings.debug)
                else:
                    ui_print(f"[magnetDL] Found {len(torrents)} torrent(s)", ui_settings.debug)

                    for torrent in torrents:
                        title = torrent.get('name', 'Unknown Title')
                        title = regex.sub(r'[^\w\s\.\-]', '', title)
                        title = title.replace(" ", '.')
                        title = regex.sub(r'\.+', ".", title)

                        if regex.match(r'(' + altquery.replace('.', r'\.').replace(r"\.*", ".*") + ')', title, regex.I):
                            info_hash = torrent.get('info_hash', '')
                            download = f"magnet:?xt=urn:btih:{info_hash}&dn={urllib.parse.quote(title)}"
                            size_bytes = int(torrent.get('size', 0))
                            size = size_bytes / (1024 * 1024 * 1024)  # Convert to GB
                            seeders = int(torrent.get('seeders', 0))

                            scraped_releases.append(releases.release('[magnetDL]', 'torrent', title, [], size, [download], seeders=seeders))
                            ui_print(f"[magnetDL] Scraped release: title={title}, size={size:.2f} GB, seeders={seeders}", ui_settings.debug)
            else:
                ui_print("[magnetDL] Failed to retrieve the page. Status code: " + str(status_code), ui_settings.debug)
        except Exception as e:
            if hasattr(response, "status_code") and not str(response.status_code).startswith("2"):
                ui_print('[magnetDL] error ' + str(response.status_code) + ': magnetDL is temporarily not reachable')
            else:
                ui_print('[magnetDL] error: unknown error. turn on debug printing for more information.')
            response = None
            ui_print('[magnetDL] error: exception: ' + str(e), ui_settings.debug)

    return scraped_releases