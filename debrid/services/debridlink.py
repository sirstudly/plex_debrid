#import modules
from base import *
from ui.ui_print import *
import releases
# (required) Name of the Debrid service
name = "Debrid Link"
short = "DL"
# (required) Authentification of the Debrid service, can be oauth aswell. Create a setting for the required variables in the ui.settings_list. For an oauth example check the trakt authentification.
api_key = ""
client_id = "0KLCzpbPTCsWZtQ9Ad0aZA"
# Define Variables
session = requests.Session()

def headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Bearer ' + api_key}

def setup(cls, new=False):
    from debrid.services import setup
    setup(cls,new)

# Error Log
def logerror(response):
    if not response.status_code == 200:
        ui_print("[debridlink] error "+str(response.status_code)+": " + str(response.content), debug=ui_settings.debug)
    if 'error' in str(response.content): 
        try:
            response2 = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
            if not response2.error == 'authorization_pending':
                ui_print("[debridlink] error "+str(response.status_code)+": " + response2.error)
        except:
            if not response.status_code == 200:
                ui_print("[debridlink] error "+str(response.status_code)+": unknown error")
    if response.status_code == 401:
        ui_print("[debridlink] error 401: debridlink api key does not seem to work. check your debridlink settings.")

# Get Function
def get(url):
    try:
        ui_print("[debridlink] (get): " + url, debug=ui_settings.debug)
        response = session.get(url, headers=headers())
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("debridlink error: (json exception): " + str(e), debug=ui_settings.debug)
        response = None
    return response

# Post Function
def post(url, data):
    try:
        ui_print("[debridlink] (post): " + url + " with data " + repr(data), debug=ui_settings.debug)
        response = session.post(url, headers=headers(), data=data)
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("debridlink error: (json exception): " + str(e), debug=ui_settings.debug)
        response = None
    return response

def delete(url):
    try:
        ui_print("[debridlink] (delete): " + url, debug=ui_settings.debug)
        response = session.delete(url, headers=headers())
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("debridlink error: (json exception): " + str(e), debug=ui_settings.debug)
        response = None
    return response

# Oauth Method
def oauth(code=""):
    if code == "":
        response = post('https://debrid-link.fr/api/oauth/device/code',f'client_id={client_id}&scope=get.post.seedbox%20get.post.delete.seedbox')
        return response.device_code, response.user_code
    else:
        response = None
        while response == None:
            response = post('https://debrid-link.fr/api/oauth/token','client_id=' + client_id + '&code=' + code + '&grant_type=http%3A%2F%2Foauth.net%2Fgrant_type%2Fdevice%2F1.0')
            if hasattr(response, 'error'):
                response = None
            time.sleep(1)
        return response.access_token

# (required) Download Function.
def download(element, stream=True, query='', force=False):
    cached = element.Releases
    if query == '':
        query = element.deviation()
    for release in cached[:]:
        # if release matches query
        if regex.match(r'(' + query + ')', release.title,regex.I) or force:
            debrid_uncached = True
            for i, rule in enumerate(element.version.rules):
                if rule[0] == "cache status" and rule[1] in ['requirement', 'preference'] and rule[2] == "cached":
                    debrid_uncached = False
                    break
            if not debrid_uncached:  # Cached Download Method for Debrid-Link
                torrent_id = None
                try:
                    response = add_torrent(release.download[0])
                    if hasattr(response, "success") and response.success:
                        if hasattr(response, "value") and hasattr(response.value, "downloadPercent") and response.value.downloadPercent == 100:
                            ui_print('[debridlink] adding cached release: ' + release.title)
                            return True
                    if hasattr(response, "error"):
                        ui_print(f"[debridlink] {response.error} error adding torrent.")
                    if hasattr(response, "value") and hasattr(response.value, "id"):
                        torrent_id = response.value.id
                    raise Exception(f"{release.title} is not cached.")

                except Exception as e:
                    ui_print(f"[debridlink] {str(e)} Looking for another release.")
                    if torrent_id is not None:
                        response = delete(f"https://debrid-link.fr/api/v2/seedbox/{torrent_id}/remove")
                        if hasattr(response, "success") and not response.success:
                            ui_print(f"[debridlink] failed to delete uncached torrent.")
                            if hasattr(response, "error") and response.error == "access_denied":
                                ui_print(f"[debridlink] insufficient permissions to delete uncached torrent; try to reset your API key.")
            else:
                # Uncached Download Method for debridlink
                try:
                    response = add_torrent(release.download[0])
                    if hasattr(response, "success") and response.success:
                        if hasattr(response, "value") and hasattr(response.value, "downloadPercent") and response.value.downloadPercent == 100:
                            ui_print('[debridlink] adding cached release: ' + release.title)
                        else:
                            ui_print('[debridlink] adding uncached release: ' + release.title)
                        return True
                except Exception as e:
                    ui_print(f"[debridlink] failed to add {release.title}, {str(e)} Looking for another release.")
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
    for release in element.Releases[:]:
        release.wanted_patterns = wanted_patterns
        release.unwanted_patterns = unwanted_patterns
        release.maybe_cached += ['DL']  # we won't know if it's cached until we attempt to download it


def add_torrent(link: str, isasync: bool = False):
    return post('https://debrid-link.fr/api/v2/seedbox/add',
                f'url={requests.utils.quote(link)}&async={str(isasync).lower()}')
