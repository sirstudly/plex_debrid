import urllib.request
import urllib.parse
from ui.ui_print import *
import releases
import re

name = "torrentgalaxy"
base_url = "https://torrentgalaxy.to"
session = urllib.request.build_opener()


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def scrape(query, altquery):
    from scraper.services import active
    scraped_releases = []
    if 'torrentgalaxy' in active:
        q = query.replace('.?', '').replace("'", "").replace("’", "").replace('.', ' ').strip(".").strip(" ")
        ui_print("[torrentgalaxy] using extended query: " + q, ui_settings.debug)

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
        url = f'{base_url}/torrents.php?search={urllib.parse.quote(q)}&sort=seeders&order=desc'
        response = None
        try:
            ui_print("[torrentgalaxy] Sending GET request to URL: " + url, ui_settings.debug)
            request = urllib.request.Request(url, headers=headers)
            response = session.open(request)
            status_code = response.getcode()

            if status_code == 200:
                content = response.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')
                torrentList = soup.select('div.tgxtablerow')
                if torrentList:
                    ui_print(f"[torrentgalaxy] Found {len(torrentList)} torrent(s)", ui_settings.debug)
                    for count, torrent in enumerate(torrentList):
                        title_element = torrent.select_one('div.tgxtablecell.clickable-row a.txlight')
                        title = title_element.getText().strip() if title_element else 'Unknown Title'
                        title = re.sub(r'[^\w\s\.\-]', '', title)  # Remove non-alphanumeric characters except for dots, spaces, and hyphens
                        title = title.replace(" ", '.')
                        title = re.sub(r'\.+', ".", title)
                        if re.match(r'(' + altquery.replace('.', '\.').replace("\.*", ".*") + ')', title, re.I):
                            magnet_element = torrent.select_one('a[href^="magnet"]')
                            download = magnet_element['href'] if magnet_element else '#'
                            size_element = torrent.select_one('div.tgxtablecell[style*="right"] span.badge')
                            size = size_element.getText().strip() if size_element else '0 GB'
                            seeders_leechers_element = torrent.select_one('div.tgxtablecell span[title="Seeders/Leechers"]')
                            seeders = int(seeders_leechers_element.getText().strip().replace(',', '').replace('[', '').split('/')[0]) if seeders_leechers_element else 0
                            if regex.search(r'([0-9]*?\.[0-9]+)(?= MB)', size, regex.I):
                                size = regex.search(r'([0-9]*,?[0-9]*?\.[0-9]+)(?= MB)', size, regex.I).group().replace(',', '')
                                size = float(float(size) / 1000)
                            elif regex.search(r'([0-9]*?\.[0-9]+)(?= GB)', size, regex.I):
                                size = regex.search(r'([0-9]*?\.[0-9]+)(?= GB)', size, regex.I).group()
                                size = float(size)
                            else:
                                size = float(size)

                            scraped_releases += [releases.release('[torrentgalaxy]', 'torrent', title, [], size, [download], seeders=seeders)]
                            ui_print(f"[torrentgalaxy] Scraped release: title={title}, size={size:.2f} GB, seeders={seeders}", ui_settings.debug)
                else:
                    ui_print("[torrentgalaxy] No torrents found", ui_settings.debug)
            else:
                ui_print("[torrentgalaxy] Failed to retrieve the page. Status code: " + str(status_code), ui_settings.debug)
        except Exception as e:
            if hasattr(response, "status_code") and not str(response.status_code).startswith("2"):
                ui_print('[torrentgalaxy] error ' + str(response.status_code) + ': torrentgalaxy is temporarily not reachable')
            else:
                ui_print('[torrentgalaxy] error: unknown error')
            ui_print('[torrentgalaxy] error: exception: ' + str(e), ui_settings.debug)
    return scraped_releases
