from base import *
from ui.ui_print import *
from urllib.parse import quote

name = 'Radarr'
base_url = "http://127.0.0.1:7878"
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
            ui_print("[radarr error]: " + content, debug=ui_settings.debug)
    if response.status_code == 401:
        ui_print("[radarr error]: (401 unauthorized): API key does not seem to work. Check your Radarr settings.")


def get(path, timeout=60):
    try:
        url = base_url.rstrip('/') + path
        response = session.get(url, headers=_headers(), timeout=timeout)
        logerror(response)
        if response.status_code not in [200, 201, 202]:
            return None
        return json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("[radarr error]: (get exception): " + str(e), debug=ui_settings.debug)
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
        ui_print("[radarr error]: (post exception): " + str(e), debug=ui_settings.debug)
        return None, {"message": str(e)}


def probe():
    """Return True if Radarr is reachable with the current base_url and api_key."""
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


def get_root_folders():
    result = get('/api/v3/rootfolder')
    if result is None:
        return []
    return result if isinstance(result, list) else []


def get_existing_movies():
    """Return sets of existing tmdb ids and imdb ids for duplicate checks."""
    tmdb_ids = set()
    imdb_ids = set()
    result = get('/api/v3/movie')
    if result is None:
        return tmdb_ids, imdb_ids
    movies = result if isinstance(result, list) else []
    for movie in movies:
        if hasattr(movie, 'tmdbId') and movie.tmdbId:
            tmdb_ids.add(int(movie.tmdbId))
        if hasattr(movie, 'imdbId') and movie.imdbId:
            imdb_ids.add(str(movie.imdbId).lower())
    return tmdb_ids, imdb_ids


def lookup_movie(tmdb_id=None, imdb_id=None):
    """Lookup a movie in Radarr by tmdb or imdb id. Returns the first match or None."""
    terms = []
    if tmdb_id:
        terms.append('tmdb:' + str(tmdb_id))
    if imdb_id:
        terms.append('imdb:' + str(imdb_id))
    for term in terms:
        result = get('/api/v3/movie/lookup?term=' + quote(term))
        if result is None:
            continue
        matches = result if isinstance(result, list) else []
        if matches:
            return matches[0]
    return None


def add_movie(lookup_result, quality_profile_id, root_folder_path, search=True):
    """
    Add a movie from a lookup result.
    Returns (success: bool, error_message: str|None).
    """
    payload = {
        "title": getattr(lookup_result, 'title', ''),
        "tmdbId": getattr(lookup_result, 'tmdbId', None),
        "qualityProfileId": quality_profile_id,
        "rootFolderPath": root_folder_path,
        "monitored": True,
        "minimumAvailability": getattr(lookup_result, 'minimumAvailability', 'released'),
        "year": getattr(lookup_result, 'year', None),
        "titleSlug": getattr(lookup_result, 'titleSlug', ''),
        "images": [],
        "addOptions": {
            "searchForMovie": search,
        },
    }
    if hasattr(lookup_result, 'imdbId') and lookup_result.imdbId:
        payload["imdbId"] = lookup_result.imdbId
    if hasattr(lookup_result, 'images') and lookup_result.images:
        images = []
        for img in lookup_result.images:
            images.append({
                "coverType": getattr(img, 'coverType', ''),
                "url": getattr(img, 'url', ''),
            })
        payload["images"] = images

    result, error = post('/api/v3/movie', payload)
    if result is not None:
        return True, None
    message = "unknown error"
    if isinstance(error, dict):
        message = error.get('message') or error.get('errorMessage') or str(error)
    elif error:
        message = str(error)
    return False, message
