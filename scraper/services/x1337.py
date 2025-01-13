import urllib.request
import urllib.parse
from ui.ui_print import *
import releases
import re

name = "1337x"
base_url = "https://1337x.to"
session = urllib.request.build_opener()


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def scrape(query, altquery):
    from scraper.services import active

    mediatype = 'TV' if re.search(r'(\bseries\b|\bS\d+\b)', altquery) else 'Movies'
    scraped_releases = []
    if '1337x' in active:
        q = query.replace('.?', '').replace("'", "").replace("’", "").replace('.', ' ').strip(".").strip(" ")
        ui_print("[1337x] using extended query: " + q, ui_settings.debug)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
        url = base_url + '/sort-category-search/' + urllib.parse.quote(q, safe=':/') + '/' + mediatype + '/seeders/desc/1/'
        response = None
        try:
            ui_print("[1337x] Sending GET request to URL: " + url, ui_settings.debug)
            request = urllib.request.Request(url, headers=headers)
            response = session.open(request)
            status_code = response.getcode()

            if status_code == 200:
                content = response.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')
                torrentList = soup.select('a[href*="/torrent/"]')
                sizeList = soup.select('td.coll-4')
                seederList = soup.select('td.coll-2')
                if torrentList:
                    ui_print(f"[1337x] Found {len(torrentList)} torrent(s)", ui_settings.debug)
                    for count, torrent in enumerate(torrentList):
                        title = torrent.getText().strip()
                        title = re.sub(r'[^\w\s\.\-]', '', title)
                        title = title.replace(" ", '.')
                        title = re.sub(r'\.+', ".", title)
                        if re.match(r'(' + altquery.replace('.', '\.').replace("\.*", ".*") + ')', title, re.I):
                            link = torrent['href']
                            request = urllib.request.Request(base_url + link, headers=headers)
                            response = session.open(request)
                            content = response.read().decode('utf-8')
                            soup = BeautifulSoup(content, 'html.parser')
                            download = soup.select('a[href^="magnet"]')[0]['href']
                            size = sizeList[count].contents[0]
                            seeders = seederList[count].contents[0]
                            if re.search(r'([0-9]*?\.[0-9])(?= MB)', size, re.I):
                                size = re.search(r'([0-9]*?\.[0-9])(?= MB)', size, re.I).group()
                                size = float(float(size) / 1000)
                            elif re.search(r'([0-9]*?\.[0-9])(?= GB)', size, re.I):
                                size = re.search(r'([0-9]*?\.[0-9])(?= GB)', size, re.I).group()
                                size = float(size)
                            else:
                                size = float(size)

                            scraped_releases += [releases.release('[1337x]', 'torrent', title, [], size, [download], seeders=int(seeders))]
                            ui_print(f"[1337x] Scraped release: title={title}, size={size} GB, seeders={seeders}", ui_settings.debug)
                else:
                    ui_print("[1337x] No torrents found", ui_settings.debug)
            else:
                ui_print("[1337x] Failed to retrieve the page. Status code: " + str(status_code), ui_settings.debug)
        except Exception as e:
            if hasattr(response, "status_code") and not str(response.status_code).startswith("2"):
                ui_print('[1337x] error ' + str(response.status_code) + ': 1337x is temporarily not reachable')
            else:
                ui_print('[1337x] error: unknown error')
            ui_print('[1337x] error: exception: ' + str(e), ui_settings.debug)
    return scraped_releases