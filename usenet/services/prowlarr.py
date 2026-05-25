from ui.ui_print import *

name = "Prowlarr"
short = "PR"
session = requests.Session()


def setup(cls, new=False):
    from usenet.services import setup
    setup(cls, new)


def _headers():
    from scraper.services import prowlarr as prowlarr_cfg
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
        'X-Api-Key': prowlarr_cfg.api_key,
        'Content-Type': 'application/json',
    }


def _base_url():
    from scraper.services import prowlarr as prowlarr_cfg
    return prowlarr_cfg.base_url.rstrip('/')


def download(element, stream=True, query='', force=False):
    if len(element.Releases) == 0:
        return False
    release = element.Releases[0]
    if release.type != 'nzb':
        ui_print('[prowlarr-usenet] error: release is not an NZB release.', ui_settings.debug)
        return False
    if not hasattr(release, 'guid') or not release.guid:
        ui_print('[prowlarr-usenet] error: release missing guid for Prowlarr grab.', ui_settings.debug)
        return False
    if not hasattr(release, 'indexer_id') or release.indexer_id is None:
        ui_print('[prowlarr-usenet] error: release missing indexer_id for Prowlarr grab.', ui_settings.debug)
        return False
    if query == '':
        query = element.deviation()
    if not regex.match(query, release.title, regex.I) and not force:
        ui_print('[prowlarr-usenet] error: rejecting release: "' + release.title + '" because it doesnt match the allowed deviation "' + query + '"')
        return False
    url = _base_url() + '/api/v1/search'
    payload = {
        'guid': release.guid,
        'indexerId': release.indexer_id,
    }
    try:
        ui_print('[prowlarr-usenet] grabbing: ' + release.title, ui_settings.debug)
        response = session.post(url, headers=_headers(), json=payload, timeout=60)
    except requests.exceptions.Timeout:
        ui_print('[prowlarr-usenet] error: grab request timed out.')
        return False
    except Exception as e:
        ui_print('[prowlarr-usenet] error: could not reach Prowlarr: ' + str(e))
        return False
    if response.status_code not in [200, 201]:
        ui_print('[prowlarr-usenet] error: grab failed (' + str(response.status_code) + '): ' + str(response.content))
        return False
    ui_print('[prowlarr-usenet] grab submitted: ' + release.title)
    element.usenet_grab = True
    return True
