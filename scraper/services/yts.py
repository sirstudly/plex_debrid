from ui.ui_print import *
import urllib.parse
import releases

name = "yts"
session = requests.Session()


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def scrape(query, altquery):
    mediatype = 'TV' if regex.search(r'(\bseries|S\d{2}|complete|season|seasons|nyaa|part\b)', altquery, regex.I) else 'Movies'

    from scraper.services import active
    scraped_releases = []

    match = regex.search(r'\btt(\d+)\b', altquery)
    imdb_id = match.group(1) if match else None
    if imdb_id is None:
        match = regex.search(r'\btt(\d+)\b', query)
        imdb_id = match.group(1) if match else None
    ui_print("[yts] using IMDB ID: " + "tt" + imdb_id if imdb_id else "[yts] No IMDB ID found in query", ui_settings.debug)

    if 'yts' in active and mediatype == "Movies":

        search_term = "tt" + imdb_id if imdb_id is not None else urllib.parse.quote(query.replace(".", " "))
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
        api_url = f'https://yts.mx/api/v2/list_movies.json?query_term={search_term}'
        response = None
        try:
            ui_print("[yts] Sending GET request to YTS API URL: " + api_url, ui_settings.debug)
            response = session.get(api_url, headers=headers)

            if response.status_code == 200:
                movies = response.json().get('data', {}).get('movies', [])

                for movie in movies:
                    title = movie.get('title').replace("'", "").replace("’", "").replace(' - ', '.').replace(': ', '.').replace(' ', '.')
                    # title_long = movie.get('title_long')
                    year = movie.get('year')
                    torrents = movie.get('torrents', [])
                    ui_print(f"[yts] Found {len(torrents)} torrent(s)", ui_settings.debug)

                    for torrent in torrents:
                        quality = torrent.get('quality')
                        torrent_type = torrent.get('type')
                        video_codec = torrent.get('video_codec')
                        bit_depth = torrent.get('bit_depth')
                        audio_channels = torrent.get('audio_channels')
                        torrent_hash = torrent.get('hash')
                        download = 'magnet:?xt=urn:btih:' + torrent_hash
                        size_bytes = int(torrent.get('size_bytes', 0))
                        size = size_bytes / (1024 * 1024 * 1024)
                        seeders = int(torrent.get('seeds', 0))

                        release_title = f"{title}.{year}.{quality}.{torrent_type}.{video_codec}.{bit_depth}bit.AAC.{audio_channels}"

                        scraped_releases += [
                            releases.release('[yts]', 'torrent', release_title, [], size, [download], seeders=int(seeders))]

                        ui_print(f"[yts] Scraped release: title={release_title}, size={size:.2f} GB, seeders={seeders}", ui_settings.debug)
            else:
                ui_print("[yts] Failed to retrieve data from YTS API. Status code: " + str(response.status_code))

        except Exception as e:
            if hasattr(response, "status_code") and not str(response.status_code).startswith("2"):
                ui_print('yts error ' + str(response.status_code) + ': yts is temporarily not reachable')
            else:
                ui_print('yts error: unknown error')
            ui_print('yts error: exception: ' + str(e), ui_settings.debug)

    return scraped_releases