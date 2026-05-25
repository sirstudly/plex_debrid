#import modules
from base import *
from ui.ui_print import *
import releases
from scraper.services import prowlarr as prowlarr_cfg

name = "prowlarr usenet"
# Internal scraper used by scrape_usenet(); not selectable in Scraper Settings.
session = requests.Session()

MOVIE_CATEGORIES = '2000'
TV_CATEGORIES = '5000'


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def _normalize_title(title):
    title = title.replace(' ', '.')
    title = title.replace(':', '').replace("'", '')
    return regex.sub(r'\.+', ".", title)


def _is_usenet_protocol(protocol):
    if protocol is None:
        return False
    return str(protocol).lower() in ['usenet', 'nzb']


def scrape(query, altquery, media_type='movie'):
    scraped_releases = []
    categories = MOVIE_CATEGORIES if media_type == 'movie' else TV_CATEGORIES
    url = (
        prowlarr_cfg.base_url.rstrip('/')
        + '/api/v1/search?query='
        + requests.utils.quote(query)
        + '&type=search&limit=1000&offset=0&categories='
        + categories
    )
    headers = {'X-Api-Key': prowlarr_cfg.api_key}
    try:
        response = session.get(url, headers=headers, timeout=60)
    except requests.exceptions.Timeout:
        ui_print('[prowlarr-usenet] error: prowlarr request timed out. Reduce the number of prowlarr indexers or make sure they are healthy.')
        return []
    except Exception:
        ui_print('[prowlarr-usenet] error: prowlarr couldnt be reached. Make sure your prowlarr base url is correctly formatted (default: http://prowlarr:9696).')
        return []
    if response.status_code != 200:
        ui_print('[prowlarr-usenet] error: prowlarr returned status ' + str(response.status_code))
        return []
    try:
        results = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception:
        ui_print('[prowlarr-usenet] error: prowlarr didnt return any data.')
        return []
    if not isinstance(results, list):
        return []
    for result in results:
        if not _is_usenet_protocol(getattr(result, 'protocol', None)):
            continue
        result.title = _normalize_title(result.title)
        if not regex.match(r'(' + altquery.replace('.', r'\.').replace(r"\.*", ".*") + ')', result.title, regex.I):
            continue
        indexer = getattr(result, 'indexer', None) or 'unnamed'
        size_gb = float(getattr(result, 'size', 0) or 0) / 1000000000
        if size_gb <= 0:
            size_gb = 1
        rel = releases.release(
            '[prowlarr-usenet: ' + str(indexer) + ']',
            'nzb',
            result.title,
            [],
            size_gb,
            [],
            seeders=0,
        )
        rel.guid = getattr(result, 'guid', '')
        rel.indexer_id = getattr(result, 'indexerId', None)
        if rel.guid and rel.indexer_id is not None:
            scraped_releases += [rel]
    return scraped_releases
