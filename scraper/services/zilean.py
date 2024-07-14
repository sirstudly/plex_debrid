# import modules
from base import *
from ui.ui_print import *
import releases

search_url = "http://localhost:8181/dmm/search"
name = "zilean"
timeout_sec = 10
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
        print()
        indices = []
        for setting in settings:
            if setting.name == "Zilean Search URL":
                setting.setup()
                if not cls.name in active:
                    active += [cls.name]


def scrape(query, altquery):
    from scraper.services import active
    global search_url
    scraped_releases = []
    if 'zilean' in active:
        if search_url.endswith('/'):
            search_url = search_url[:-1]
        try:
            ui_print("[zilean] searching for: " + query)
            response = session.post(search_url, headers={'Content-type': "application/json"}, data=json.dumps({'queryText': query}), timeout=timeout_sec)

            if not response.status_code == 200:
                ui_print('[zilean] error ' + str(
                    response.status_code) + ': failed response from zilean. ' + response.content)
                return []

        except requests.exceptions.Timeout:
            ui_print('[zilean] error: zilean request timed out.')
            return []
        except:
            ui_print('[zilean] error: zilean couldn\'t be reached. Make sure your zilean search url [' + search_url + '] is correctly formatted.')
            return []

        try:
            response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
        except:
            ui_print('[zilean] error: unable to parse response:' + response.content)
            return []

        for result in response[:]:
            if regex.match(r'(' + altquery.replace('.', '\.').replace("\.*", ".*") + ')', result.filename,regex.I):
                links = ['magnet:?xt=urn:btih:' + result.infoHash + '&dn=&tr=']
                seeders = 0  # not available
                scraped_releases += [releases.release(
                    '[zilean]', 'torrent', result.filename, [], float(result.filesize) / 1000000000, links, seeders)]

    return scraped_releases
