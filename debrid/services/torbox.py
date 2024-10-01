from ui.ui_print import *
import releases

# (required) Name of the Debrid service
name = "Torbox"
short = "TB"
# (required) Authentification of the Torbox service, can be oauth aswell. Create a setting for the required variables in the ui.settings_list. For an oauth example check the trakt authentification.
api_key = ""
# Define Variables
session = requests.Session()
errors = [
    [202, " action already done"],
    [400, " bad Request (see error message)"],
    [403, " permission denied (infringing torrent or account locked or not premium)"],
    [503, " service unavailable (see error message)"],
    [404, " wrong parameter (invalid file id(s)) / unknown resource (invalid id)"],
]


def setup(cls, new=False):
    from debrid.services import setup
    setup(cls, new)


# Error Log
def logerror(response):
    if response.status_code not in [200, 201, 204]:
        desc = ""
        for error in errors:
            if response.status_code == error[0]:
                desc = error[1]
        ui_print("[torbox] error: (" + str(response.status_code) + desc + ") " + str(response.content))
    if response.status_code == 401:
        ui_print("[torbox] error: (401 unauthorized): torbox api key does not seem to work. check your torbox settings.")
    if response.status_code == 403:
        ui_print("[torbox] error: (403 unauthorized): You may have attempted to add an infringing torrent or your torbox account is locked or you dont have premium.")


# Get Function
def get(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36', 'authorization': 'Bearer ' + api_key}
    response = None
    try:
        ui_print("[torbox] (get): " + url, debug=ui_settings.debug)
        response = session.get(url, headers=headers)
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
        if hasattr(response, "detail"):
            if hasattr(response, "success") and not response.success:
                ui_print("[torbox] failed: " + response.detail)
            else:
                ui_print("[torbox]: " + response.detail, debug=ui_settings.debug)
    except Exception as e:
        ui_print("[torbox] error: (json exception): " + str(e))
        response = None
    return response


# Post Function
def post(url, data=None, json_data=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36', 'authorization': 'Bearer ' + api_key}
    response = None
    try:
        ui_print("[torbox] (post): " + url + " with data " + repr(data if data else json_data), debug=ui_settings.debug)
        response = session.post(url, headers=headers, json=json.dumps(json_data)) if json_data else session.post(url, headers=headers, data=data)
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
        if hasattr(response, "detail"):
            if hasattr(response, "success") and not response.success:
                ui_print("[torbox] failed: " + response.detail)
            else:
                ui_print("[torbox]: " + response.detail, debug=ui_settings.debug)
    except Exception as e:
        if hasattr(response, "status_code"):
            if response.status_code >= 300:
                ui_print("[torbox] error: (json exception): " + str(e))
        else:
            ui_print("[torbox] error: (json exception): " + str(e))
        response = None

    return response


# Object classes
class file:
    def __init__(self, id, name, size, wanted_list, unwanted_list):
        self.id = id
        self.name = name
        self.size = size / 1000000000
        self.match = ''
        wanted = False
        unwanted = False
        for key, wanted_pattern in wanted_list:
            if wanted_pattern.search(self.name):
                wanted = True
                self.match = key
                break

        if not wanted:
            for key, unwanted_pattern in unwanted_list:
                if unwanted_pattern.search(self.name) or self.name.endswith('.exe') or self.name.endswith('.txt'):
                    unwanted = True
                    break

        self.wanted = wanted
        self.unwanted = unwanted

    def __eq__(self, other):
        return self.id == other.id


class version:
    def __init__(self, files):
        self.files = files
        self.needed = 0
        self.wanted = 0
        self.unwanted = 0
        self.size = 0
        for file in self.files:
            self.size += file.size
            if file.wanted:
                self.wanted += 1
            if file.unwanted:
                self.unwanted += 1


# (required) Download Function.
def download(element, stream=True, query='', force=False):
    cached = element.Releases
    if query == '':
        query = element.deviation()
    wanted = [query]
    if not isinstance(element, releases.release):
        wanted = element.files()
    for release in cached[:]:
        # if release matches query
        if regex.match(query, release.title, regex.I) or force:
            if stream:
                release.size = 0
                for version in release.files:
                    if hasattr(version, 'files'):
                        if len(version.files) > 0 and version.wanted > len(wanted) / 2 or force:
                            cached_ids = []
                            for file in version.files:
                                cached_ids += [file.id]
                            try:
                                response = post('https://api.torbox.app/v1/api/torrents/createtorrent', {'magnet': str(release.download[0]), 'seed': 3, 'allow_zip': 'false'})

                                if response is None or not response.success or not hasattr(response, "data") or not hasattr(response.data, "torrent_id"):
                                    ui_print('[torbox] error: could not add magnet for release: ' + release.title)
                                    continue
                                torrent_id = response.data.torrent_id

                            except Exception as e:
                                ui_print('[torbox] error: could not add magnet for release: ' + release.title + ' ' + str(e))
                                continue
                            response = get('https://api.torbox.app/v1/api/torrents/mylist?bypass_cache=true')
                            selected_torrent = [s for s in response.data if s.id == torrent_id]
                            if len(selected_torrent) == 0:
                                ui_print('[torbox] error: unexpected mismatch after adding torrent: ' + release.title)
                                continue
                            selected_torrent = selected_torrent[0]

                            actual_title = ""
                            if len(selected_torrent.files) == len(cached_ids):
                                actual_title = selected_torrent.name
                                release.download = selected_torrent.files
                            else:
                                if hasattr(selected_torrent, "download_state") and selected_torrent.download_state in ["downloading", "paused", "stalled (no seeds)"]:
                                    if hasattr(element, "version"):
                                        debrid_uncached = True
                                        for i, rule in enumerate(element.version.rules):
                                            if (rule[0] == "cache status") and (rule[1] == 'requirement' or rule[1] == 'preference') and (rule[2] == "cached"):
                                                debrid_uncached = False
                                        if debrid_uncached:
                                            import debrid as db
                                            release.files = version.files
                                            db.downloading += [element.query() + ' [' + element.version.name + ']']
                                            ui_print('[torbox] adding uncached release: ' + release.title)
                                            return True
                                else:
                                    ui_print('[torbox] error: queuing this torrent returned an unsupported state. Select a different torrent.')
                                    post('https://api.torbox.app/v1/api/torrents/controltorrent', json_data={'torrent_id': torrent_id, 'operation': 'Delete'})
                                    continue
                            if len(release.download) > 0:
                                release.files = version.files
                                ui_print('[torbox] adding cached release: ' + release.title)
                                if not actual_title == "":
                                    release.title = actual_title
                                return True
                ui_print('[torbox] error: no streamable version could be selected for release: ' + release.title)
                return False
            else:
                response = post('https://api.torbox.app/v1/api/torrents/createtorrent', {'magnet': str(release.download[0]), 'seed': 3, 'allow_zip': 'false'})
                ui_print('[torbox] adding uncached release: ' + release.title + (" with torrent_id=" + str(response.data.torrent_id) if hasattr(response, "data") and hasattr(response.data, "torrent_id") else ""))
                return True
        else:
            ui_print('[torbox] error: rejecting release: "' + release.title + '" because it doesnt match the allowed deviation "' + query + '"')
    return False


# (required) Check Function
def check(element, force=False):
    if force:
        wanted = ['.*']
    else:
        wanted = element.files()
    unwanted = releases.sort.unwanted
    wanted_patterns = list(zip(wanted, [regex.compile(r'(' + key + ')', regex.IGNORECASE) for key in wanted]))
    unwanted_patterns = list(zip(unwanted, [regex.compile(r'(' + key + ')', regex.IGNORECASE) for key in unwanted]))

    hashes = set()
    for release in element.Releases[:]:
        if len(release.hash) == 40:
            hashes.add(release.hash)
        else:
            ui_print("[torbox] error (missing torrent hash): ignoring release '" + release.title + "'")
            element.Releases.remove(release)
    if len(hashes) > 0:
        response = get('https://api.torbox.app/v1/api/torrents/checkcached?format=list&list_files=true&hash=' + ','.join(hashes))
        ui_print("[torbox] checking and sorting all release files ...", ui_settings.debug)
        for release in element.Releases:
            release.files = []
            release_hash = release.hash.lower()
            # for each of the releases, collate file details and cache status
            if hasattr(response, "data") and response.data is not None:
                for t in response.data:
                    if t.hash == release_hash and 'TB' not in release.cached:  # ignore duplicates if t appears more than once
                        version_files = []
                        for file_ in t.files:
                            debrid_file = file(file_, file_.name, file_.size, wanted_patterns, unwanted_patterns)
                            version_files.append(debrid_file)
                        release.files += [version(version_files), ]

                        # select cached version that has the most needed, most wanted, least unwanted files and most files overall
                        release.files.sort(key=lambda x: len(x.files), reverse=True)
                        release.files.sort(key=lambda x: x.wanted, reverse=True)
                        release.files.sort(key=lambda x: x.unwanted, reverse=False)
                        release.wanted = release.files[0].wanted
                        release.unwanted = release.files[0].unwanted
                        release.size = release.files[0].size
                        release.cached += ['TB']

        ui_print("done", ui_settings.debug)
