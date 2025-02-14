import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from ui.ui_print import *
import releases

name = "rarbgv2"
session = urllib.request.build_opener()


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def scrape(query, altquery):
    from scraper.services import active
    scraped_releases = []
    if 'rarbgv2' in active:
        ui_print("[rarbg] using extended query: " + query, ui_settings.debug)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
        url = 'http://therarbg.com/get-posts/keywords:' + urllib.parse.quote(query.replace('.', ' ').replace('?', ''), safe=':/') + '/'
        response = None
        try:
            ui_print("[rarbg] Sending GET request to URL: " + url, ui_settings.debug)
            request = urllib.request.Request(url, headers=headers)
            response = session.open(request)
            status_code = response.getcode()

            if status_code == 200:
                content = response.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')
                torrentList = soup.select('a[href*="/post-detail/"]')
                sizeList = soup.select('td[style*="left"]')
                seederList = soup.select('td[style*="color: green"]')
                if torrentList:
                    ui_print(f"[rarbg] Found {len(torrentList)} torrent(s)", ui_settings.debug)
                    for count, torrent in enumerate(torrentList):
                        title = torrent.getText().strip()
                        title = regex.sub(r'[^\w\s\.\-]', '', title)
                        title = title.replace(" ", '.')
                        title = regex.sub(r'\.+', ".", title)
                        ui_print("[rarbg] Processing torrent: " + title, ui_settings.debug)
                        if regex.match(r'(' + altquery.replace('.', r'\.').replace(r"\.*", ".*") + ')', title, regex.I):
                            link = torrent['href']
                            request = urllib.request.Request(escape_url('http://therarbg.com' + link), headers=headers)
                            response = session.open(request)
                            content = response.read().decode('utf-8', errors='ignore')
                            soup = BeautifulSoup(content, 'html.parser')
                            download = soup.select('a[href^="magnet"]')[0]['href']
                            seeders = seederList[count].contents[0]
                            size = sizeList[count].contents[0].replace('&nbsp;', ' ').replace('\xa0', ' ')
                            size_match = regex.search(r'([0-9]*\.?[0-9]+)\s*(KB|MB|GB)', size, regex.I)

                            if size_match:
                                size_value = float(size_match.group(1))
                                size_unit = size_match.group(2).upper()

                                if size_unit == 'KB':
                                    size = size_value / (1024 * 1024)  # Convert KB to GB
                                elif size_unit == 'MB':
                                    size = size_value / 1024  # Convert MB to GB
                                elif size_unit == 'GB':
                                    size = size_value
                            else:
                                size = float(size_value)

                            scraped_releases += [releases.release('[rarbg]', 'torrent', title, [], size, [download], seeders=int(seeders))]
                            ui_print(f"[rarbg] Scraped release: title={title}, size={size} GB, seeders={seeders}", ui_settings.debug)
                else:
                    ui_print("[rarbg] No torrents found", ui_settings.debug)
            else:
                ui_print("[rarbg] Failed to retrieve the page. Status code: " + str(status_code), ui_settings.debug)

        except Exception as e:
            if hasattr(response, "status_code") and not str(response.status_code).startswith("2"):
                ui_print('[rarbg] error ' + str(response.status_code) + ': rarbg is temporarily not reachable')
            else:
                ui_print('[rarbg] error: unknown error. turn on debug printing for more information.')
            response = None
            ui_print('[rarbg] error: exception: ' + str(e), ui_settings.debug)
    return scraped_releases


# properly escapes any non-ascii characters in url
def escape_url(url):
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path)
    query = urllib.parse.quote(parts.query, safe="=&?")  # Adjust safe characters as needed
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))