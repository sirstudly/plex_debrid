from base import *
from ui.ui_print import *
from urllib.parse import quote

name = 'Sonarr'
base_url = "http://127.0.0.1:8989"
api_key = ""
session = requests.Session()


def _headers():
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def logerror(response):
    if response is None:
        return
    if response.status_code not in [200, 201, 202]:
        content = ""
        try:
            content = str(response.content)
        except:
            pass
        if content:
            ui_print("[sonarr error]: " + content, debug=ui_settings.debug)
    if response.status_code == 401:
        ui_print("[sonarr error]: (401 unauthorized): API key does not seem to work. Check your Sonarr settings.")


def get(path, timeout=60):
    try:
        url = base_url.rstrip('/') + path
        response = session.get(url, headers=_headers(), timeout=timeout)
        logerror(response)
        if response.status_code not in [200, 201, 202]:
            return None
        return json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("[sonarr error]: (get exception): " + str(e), debug=ui_settings.debug)
        return None


def post(path, data, timeout=60):
    try:
        url = base_url.rstrip('/') + path
        response = session.post(url, headers=_headers(), json=data, timeout=timeout)
        logerror(response)
        if response.status_code not in [200, 201, 202]:
            try:
                return None, response.json()
            except:
                return None, {"message": str(response.content)}
        return json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d)), None
    except Exception as e:
        ui_print("[sonarr error]: (post exception): " + str(e), debug=ui_settings.debug)
        return None, {"message": str(e)}


def probe():
    """Return True if Sonarr is reachable with the current base_url and api_key."""
    if not base_url or not api_key:
        return False
    try:
        response = session.get(
            base_url.rstrip('/') + '/api/v3/system/status',
            headers=_headers(),
            timeout=10,
        )
        return response.status_code == 200
    except:
        return False


def get_quality_profiles():
    result = get('/api/v3/qualityprofile')
    if result is None:
        return []
    return result if isinstance(result, list) else []


def get_language_profiles():
    """Sonarr v3 only; returns [] on Sonarr v4 where the endpoint is gone."""
    try:
        url = base_url.rstrip('/') + '/api/v3/languageprofile'
        response = session.get(url, headers=_headers(), timeout=30)
        if response.status_code != 200:
            return []
        result = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
        return result if isinstance(result, list) else []
    except Exception:
        return []


def get_root_folders():
    result = get('/api/v3/rootfolder')
    if result is None:
        return []
    return result if isinstance(result, list) else []


def get_existing_series():
    """Return sets of existing tvdb/tmdb/imdb ids for duplicate checks."""
    tvdb_ids = set()
    tmdb_ids = set()
    imdb_ids = set()
    result = get('/api/v3/series')
    if result is None:
        return tvdb_ids, tmdb_ids, imdb_ids
    series_list = result if isinstance(result, list) else []
    for series in series_list:
        if hasattr(series, 'tvdbId') and series.tvdbId:
            tvdb_ids.add(int(series.tvdbId))
        if hasattr(series, 'tmdbId') and series.tmdbId:
            tmdb_ids.add(int(series.tmdbId))
        if hasattr(series, 'imdbId') and series.imdbId:
            imdb_ids.add(str(series.imdbId).lower())
    return tvdb_ids, tmdb_ids, imdb_ids


def lookup_series(tvdb_id=None, tmdb_id=None, imdb_id=None):
    """Lookup a series in Sonarr by tvdb, tmdb, or imdb id. Returns the first match or None."""
    terms = []
    if tvdb_id:
        terms.append('tvdb:' + str(tvdb_id))
    if tmdb_id:
        terms.append('tmdb:' + str(tmdb_id))
    if imdb_id:
        terms.append('imdb:' + str(imdb_id))
    for term in terms:
        result = get('/api/v3/series/lookup?term=' + quote(term))
        if result is None:
            continue
        matches = result if isinstance(result, list) else []
        if matches:
            return matches[0]
    return None


def add_series(lookup_result, quality_profile_id, root_folder_path, language_profile_id=None, search=True):
    """
    Add a series from a lookup result.
    Returns (success: bool, error_message: str|None).
    """
    seasons = []
    if hasattr(lookup_result, 'seasons') and lookup_result.seasons:
        for season in lookup_result.seasons:
            seasons.append({
                "seasonNumber": getattr(season, 'seasonNumber', 0),
                "monitored": True,
            })

    payload = {
        "title": getattr(lookup_result, 'title', ''),
        "qualityProfileId": quality_profile_id,
        "rootFolderPath": root_folder_path,
        "monitored": True,
        "seasonFolder": True,
        "seasons": seasons,
        "titleSlug": getattr(lookup_result, 'titleSlug', ''),
        "images": [],
        "addOptions": {
            "searchForMissingEpisodes": search,
            "monitor": "all",
        },
    }
    if hasattr(lookup_result, 'tvdbId') and lookup_result.tvdbId:
        payload["tvdbId"] = lookup_result.tvdbId
    if hasattr(lookup_result, 'tmdbId') and lookup_result.tmdbId:
        payload["tmdbId"] = lookup_result.tmdbId
    if hasattr(lookup_result, 'imdbId') and lookup_result.imdbId:
        payload["imdbId"] = lookup_result.imdbId
    if hasattr(lookup_result, 'year') and lookup_result.year:
        payload["year"] = lookup_result.year
    if language_profile_id is not None:
        payload["languageProfileId"] = language_profile_id
    if hasattr(lookup_result, 'images') and lookup_result.images:
        images = []
        for img in lookup_result.images:
            images.append({
                "coverType": getattr(img, 'coverType', ''),
                "url": getattr(img, 'url', ''),
            })
        payload["images"] = images

    result, error = post('/api/v3/series', payload)
    if result is not None:
        return True, None
    message = "unknown error"
    if isinstance(error, dict):
        message = error.get('message') or error.get('errorMessage') or str(error)
    elif error:
        message = str(error)
    return False, message
