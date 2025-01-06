import urllib.request
import urllib.parse
from ui.ui_print import *
import releases

name = "eztv"
base_url = "https://eztvx.to"  # if host is DNS blocked, add it manually to your /etc/hosts file
session = urllib.request.build_opener()


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def scrape(query, altquery):
    from scraper.services import active
    scraped_releases = []
    if 'eztv' in active:
        ui_print("[eztv] using extended query: " + query.replace('.?', '').replace("'", "").replace("’", "").strip(".").strip(" "), ui_settings.debug)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
        url = base_url + '/search/' + urllib.parse.quote(
            query.replace('.?', '').replace("'", "").replace("’", "").replace('.', ' ').strip(".").strip(" "),
            safe=':/')
        try:
            ui_print("[eztv] Sending GET request to URL: " + url, ui_settings.debug)
            request = urllib.request.Request(url, headers=headers)
            response = session.open(request)
            status_code = response.getcode()
            ui_print("[eztv] Received response for search query with status code: " + str(status_code), ui_settings.debug)

            if status_code == 200:
                content = response.read().decode('utf-8')
                soup = BeautifulSoup(content, 'html.parser')
                torrentList = soup.select('a.epinfo')
                sizeList = soup.select('td.forum_thread_post')[4::4]  # Every 4th element starting from the 4th one
                seederList = soup.select('td.forum_thread_post_end')
                if torrentList:
                    ui_print(f"[eztv] Found {len(torrentList)} torrent(s)", ui_settings.debug)
                    for count, torrent in enumerate(torrentList):
                        title = torrent.getText().strip()
                        title = title.replace(" ", '.')
                        title = regex.sub(r'\.+', ".", title)
                        ui_print("[eztv] Processing torrent: " + title, ui_settings.debug)
                        if regex.match(r'(' + altquery.replace('.', '\.').replace("\.*", ".*") + ')', title, regex.I):
                            link = torrent['href']
                            ui_print("[eztv] Sending GET request for torrent details: " + link, ui_settings.debug)
                            request = urllib.request.Request(base_url + link, headers=headers)
                            response = session.open(request)
                            content = response.read().decode('utf-8')
                            soup = BeautifulSoup(content, 'html.parser')
                            download = soup.select('a[href^="magnet"]')[0]['href']
                            size = sizeList[count].getText().strip()
                            ui_print(f"[eztv] Found size: {size}", ui_settings.debug)
                            seeders = seederList[count].getText().strip().replace('-', '0').replace(',', '')
                            ui_print("[eztv] Found download link: " + download, ui_settings.debug)

                            if regex.search(r'([0-9]*?[0-9])(?= MB)', size, regex.I):
                                size = regex.search(r'([0-9]*?[0-9])(?= MB)', size, regex.I).group()
                                size = float(float(size) / 1000)
                            elif regex.search(r'([0-9]*?\.[0-9]*?)(?= GB)', size, regex.I):
                                size = regex.search(r'([0-9]*?\.[0-9]*?)(?= GB)', size, regex.I).group()
                                size = float(size)
                            else:
                                size = float(size)

                            scraped_releases += [releases.release('[eztv]', 'torrent', title, [], size, [download], seeders=int(seeders))]
                            ui_print(f"[eztv] Scraped release: title={title}, size={size} GB, seeders={seeders}", ui_settings.debug)
                else:
                    ui_print("[eztv] No torrents found", ui_settings.debug)
            else:
                ui_print("[eztv] Failed to retrieve the page. Status code: " + str(status_code), ui_settings.debug)
        except Exception as e:
            ui_print('eztv error: exception: ' + str(e), ui_settings.debug)
    return scraped_releases