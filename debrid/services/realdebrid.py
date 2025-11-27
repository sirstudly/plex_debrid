#import modules
from base import *
from ui.ui_print import *
import releases
import time
import json

# (required) Name of the Debrid service
name = "Real Debrid"
short = "RD"
media_file_extensions = [
    '.yuv', '.wmv', '.webm', '.vob', '.viv', '.svi', '.roq', '.rmvb', '.rm',
    '.ogv', '.ogg', '.nsv', '.mxf', '.mts', '.m2ts', '.ts', '.mpg', '.mpeg',
    '.m2v', '.mp2', '.mpe', '.mpv', '.mp4', '.m4p', '.m4v', '.mov', '.qt',
    '.mng', '.mkv', '.flv', '.drc', '.avi', '.asf', '.amv'
]
# (required) Authentification of the Debrid service, can be oauth aswell. Create a setting for the required variables in the ui.settings_list. For an oauth example check the trakt authentification.
api_key = ""
# Rate-limited session for API calls (250 req/min = ~0.24s between requests)
rate_limited_session = custom_session(get_rate_limit=1, post_rate_limit=1)
errors = [
    [202," action already done"],
    [400," bad Request (see error message)"],
    [403," permission denied (infringing torrent or account locked or not premium)"],
    [503," service unavailable (see error message)"],
    [404," wrong parameter (invalid file id(s)) / unknown ressource (invalid id)"],
    [509," bandwidth limit exceeded"]
    ]
def setup(cls, new=False):
    from debrid.services import setup
    setup(cls,new)

# Error Log
def logerror(response):
    if not response.status_code in [200,201,204]:
        desc = ""
        for error in errors:
            if response.status_code == error[0]:
                desc = error[1]
        ui_print("[realdebrid] error: (" + str(response.status_code) + desc + ") " + str(response.content), debug=ui_settings.debug)
    if response.status_code == 401:
        ui_print("[realdebrid] error: (401 unauthorized): realdebrid api key does not seem to work. check your realdebrid settings.")
    if response.status_code == 403:
        ui_print("[realdebrid] error: (403 unauthorized): You may have attempted to add an infringing torrent or your realdebrid account is locked or you dont have premium.")

# Get Function
def get(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    response = None
    try:
        response = rate_limited_session.get(url, headers=headers)
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("[realdebrid] error: (json exception): " + str(e), debug=ui_settings.debug)
        response = None
    return response

# Post Function
def post(url, data):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    response = None
    try:
        ui_print("[realdebrid] (post): " + url + " with data " + repr(data), debug=ui_settings.debug)
        response = rate_limited_session.post(url, headers=headers, data=data)
        logerror(response)
        ui_print("[realdebrid] response: " + repr(response), debug=ui_settings.debug)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        if hasattr(response,"status_code"):
            if response.status_code >= 300:
                ui_print("[realdebrid] error: (json exception): " + str(e), debug=ui_settings.debug)
        else:
            ui_print("[realdebrid] error: (json exception): " + str(e), debug=ui_settings.debug)
        response = None
    return response

# Delete Function
def delete(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    try:
        ui_print("[realdebrid] (delete): " + url, debug=ui_settings.debug)
        response = rate_limited_session.delete(url, headers=headers)
        logerror(response)

    except Exception as e:
        ui_print("[realdebrid] error: (delete exception): " + str(e), debug=ui_settings.debug)
        None
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
    for release in cached[:]:
        try:  # if release matches query
            if regex.match(query, release.title,regex.I) or force:
                # Check if torrent hash already exists in Real-Debrid
                magnet_hash = cache.extract_hash_from_magnet(release.download[0])
                if magnet_hash and cache.check_hash_exists(magnet_hash):
                    existing_status = cache.get_torrent_status(magnet_hash)
                    ui_print(f'[realdebrid]: torrent {release.title} already exists with status "{existing_status}", skipping.', ui_settings.debug)
                    continue

                response = post('https://api.real-debrid.com/rest/1.0/torrents/addMagnet', {'magnet': release.download[0]})
                if hasattr(response, 'error') and response.error == 'infringing_file':
                    ui_print(f'[realdebrid]: torrent {release.title} marked as infringing... looking for another release.')
                    continue
                elif hasattr(response, 'error') and response.error == 'too_many_active_downloads':
                    ui_print(f'[realdebrid]: unable to add torrent {release.title} due to too many active downloads.')
                    continue
                elif not hasattr(response, "id"):
                    ui_print(f'[realdebrid]: unexpected error when adding torrent {release.title}.')
                    continue
                time.sleep(1.0)
                torrent_id = str(response.id)
                response = get('https://api.real-debrid.com/rest/1.0/torrents/info/' + torrent_id)
                if response.status == 'magnet_error':
                    ui_print( f'[realdebrid]: failed to add torrent {release.title}. Looking for another release.')
                    delete('https://api.real-debrid.com/rest/1.0/torrents/delete/' + torrent_id)
                    continue
                if hasattr(response, "files") and len(response.files) > 0:
                    version_files = []
                    for file_ in response.files:
                        debrid_file = file(file_.id, file_.path, file_.bytes, release.wanted_patterns, release.unwanted_patterns)
                        version_files.append(debrid_file)
                    release.files = [version(version_files)]
                    cached_ids = [vf.id for vf in version_files if vf.wanted and not vf.unwanted and vf.name.endswith(tuple(media_file_extensions))]
                    if len(cached_ids) == 0:
                        ui_print('[realdebrid] no selectable media files.', ui_settings.debug)
                    else:
                        post('https://api.real-debrid.com/rest/1.0/torrents/selectFiles/' + torrent_id, {'files': ",".join(map(str, cached_ids))})
                        ui_print('[realdebrid] selectFiles response ' + repr(response), ui_settings.debug)

                    response = get('https://api.real-debrid.com/rest/1.0/torrents/info/' + torrent_id)
                    actual_title = ""
                    if len(response.links) == len(cached_ids) and len(cached_ids) > 0:
                        actual_title = response.filename
                        release.download = response.links
                    else:
                        if response.status in ["queued", "magnet_conversion", "downloading", "uploading"]:
                            if hasattr(element, "version"):
                                debrid_uncached = True
                                for i, rule in enumerate(element.version.rules):
                                    if (rule[0] == "cache status") and (rule[1] == 'requirement' or rule[1] == 'preference') and (rule[2] == "cached"):
                                        debrid_uncached = False
                                if debrid_uncached:
                                    import debrid as db
                                    db.downloading += [element.query() + ' [' + element.version.name + ']']
                                    ui_print('[realdebrid] added uncached release: ' + release.title)
                                    return True
                                else:
                                    ui_print(f'[realdebrid]: {release.title} is in {response.status} status (not cached). Looking for another release.')
                                    delete('https://api.real-debrid.com/rest/1.0/torrents/delete/' + torrent_id)
                                    continue
                        else:
                            ui_print(f'[realdebrid]: {release.title} is in status [{response.status}] - trying a different release.')
                            delete('https://api.real-debrid.com/rest/1.0/torrents/delete/' + torrent_id)
                            continue
                    if response.status == 'downloaded':
                        ui_print('[realdebrid] added cached release: ' + release.title)
                        if actual_title != "":
                            release.title = actual_title
                        return True

                else:  # no files found after adding torrent
                    if response.status == 'downloading':
                        if hasattr(element, "version"):
                            import debrid as db
                            db.downloading += [element.query() + ' [' + element.version.name + ']']
                        ui_print('[realdebrid] added uncached release: ' + release.title)
                        return True
                    else:
                        ui_print(f'[realdebrid]: no files found for torrent {release.title} in status {response.status}. looking for another release.')
                        delete('https://api.real-debrid.com/rest/1.0/torrents/delete/' + torrent_id)
                        continue

                ui_print('[realdebrid] added uncached release: ' + release.title)
                return True
            else:
                ui_print(f'[realdebrid] error: rejecting release: "{release.title}" because it doesnt match the allowed deviation "{query}"')
                ui_print(f'[realdebrid] if this was a mistake, you can manually add it: "{release.download[0]}"')
        except Exception as e:
            ui_print(f'[realdebrid] unexpected error: ' + str(e))
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
        release.maybe_cached += ['RD']  # we won't know if it's cached until we attempt to download it

# Real-Debrid Cache Class
class cache:
    def __init__(self):
        self.refresh_interval_minutes = 30  # Default value
        self.last_refresh = None

    def should_refresh(self):
        """Check if cache should be refreshed based on configured interval"""
        if self.last_refresh is None:
            return True
        return time.time() - self.last_refresh > (self.refresh_interval_minutes * 60)

    def extract_hash_from_magnet(self, magnet_link):
        """Extract torrent hash from magnet link"""
        match = regex.search(r'btih:([a-fA-F0-9]{40})', magnet_link)
        return match.group(1).lower() if match else None

    def check_hash_exists(self, magnet_hash):
        """Check if torrent hash already exists in Real-Debrid - query database directly"""
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM realdebrid_torrents WHERE hash = ? AND deleted_at IS NULL",
                (magnet_hash,)
            )
            exists = cursor.fetchone()[0] > 0
            return exists
        except Exception as e:
            ui_print(f'[realdebrid_cache] error checking hash existence: {str(e)}', ui_settings.debug)
            return False

    def get_torrent_status(self, magnet_hash):
        """Get status of existing torrent"""
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            cursor = conn.execute(
                "SELECT status FROM realdebrid_torrents WHERE hash = ? AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT 1",
                (magnet_hash,)
            )
            result = cursor.fetchone()
            return result[0] if result else 'unknown'
        except Exception as e:
            ui_print(f'[realdebrid_cache] error getting torrent status: {str(e)}', ui_settings.debug)
            return 'unknown'

    def fetch_all_torrents(self):
        """Fetch all torrents from Real-Debrid API with pagination"""
        if not api_key:
            ui_print('[realdebrid_cache] error: Real-Debrid API key not configured', ui_settings.debug)
            return []

        all_torrents = []
        page = 1  # Real-Debrid API uses 1-based pagination
        limit = 5000  # Maximum allowed by Real-Debrid API

        while True:
            try:
                url = f'https://api.real-debrid.com/rest/1.0/torrents?limit={limit}&page={page}'
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
                    'authorization': 'Bearer ' + api_key
                }
                response = rate_limited_session.get(url, headers=headers)

                if not response or response.status_code != 200:
                    ui_print(f'[realdebrid_cache] error fetching torrents page {page}: HTTP {response.status_code if response else "None"}', ui_settings.debug)
                    break

                data = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))

                if len(data) == 0:
                    break

                all_torrents.extend(data)
                ui_print(f'[realdebrid_cache] fetched {len(data)} torrents from page {page}', ui_settings.debug)

                # If we got fewer records than requested, we've reached the end
                if len(data) < limit:
                    break

                page += 1

            except Exception as e:
                ui_print(f'[realdebrid_cache] error fetching torrents page {page}: {str(e)}', ui_settings.debug)
                break

        ui_print(f'[realdebrid_cache] total torrents fetched: {len(all_torrents)}', ui_settings.debug)
        return all_torrents

    def mark_all_as_stale(self, sync_time):
        """Mark all existing records as potentially stale by clearing their sync_marker.
        Records that get upserted will get the new sync_marker, records that don't will remain NULL.
        """
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            cursor = conn.execute(
                "UPDATE realdebrid_torrents SET sync_marker = NULL WHERE deleted_at IS NULL",
                ()
            )
            conn.commit()
            ui_print(f'[realdebrid_cache] marked {cursor.rowcount} records as stale', ui_settings.debug)
        except Exception as e:
            ui_print(f'[realdebrid_cache] error marking records as stale: {str(e)}', ui_settings.debug)
            raise e

    def upsert_torrent_batch(self, torrents, sync_time):
        """Upsert a batch of torrents into the database"""
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()

            for torrent in torrents:
                conn.execute(
                    """
                    INSERT INTO realdebrid_torrents (
                        id, filename, hash, bytes, progress, status, added, ended, sync_marker
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        filename=excluded.filename,
                        hash=excluded.hash,
                        bytes=excluded.bytes,
                        progress=excluded.progress,
                        status=excluded.status,
                        added=excluded.added,
                        ended=excluded.ended,
                        updated_at=datetime('now'),
                        sync_marker=excluded.sync_marker,
                        deleted_at=NULL
                    """,
                    (
                        getattr(torrent, 'id', None),
                        getattr(torrent, 'filename', None),
                        getattr(torrent, 'hash', None),
                        getattr(torrent, 'bytes', None),
                        getattr(torrent, 'progress', None),
                        getattr(torrent, 'status', None),
                        getattr(torrent, 'added', None),
                        getattr(torrent, 'ended', None),  # This can be None if torrent is still active
                        str(sync_time)
                    )
                )

            conn.commit()
            ui_print(f'[realdebrid_cache] upserted {len(torrents)} torrents', ui_settings.debug)

        except Exception as e:
            ui_print(f'[realdebrid_cache] error upserting torrent batch: {str(e)}', ui_settings.debug)
            raise e

    def mark_deleted_records(self, sync_time):
        """Mark records that weren't updated as deleted.
        Records that were upserted have sync_marker = sync_time.
        Records that weren't found in the API still have sync_marker = NULL.
        """
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            cursor = conn.execute(
                """UPDATE realdebrid_torrents 
                   SET deleted_at = datetime('now') 
                   WHERE (sync_marker IS NULL OR sync_marker != ?) AND deleted_at IS NULL""",
                (str(sync_time),)
            )
            conn.commit()
            ui_print(f'[realdebrid_cache] marked {cursor.rowcount} records as deleted', ui_settings.debug)
        except Exception as e:
            ui_print(f'[realdebrid_cache] error marking deleted records: {str(e)}', ui_settings.debug)
            raise e

    def rollback_stale_marking(self, sync_time):
        """Rollback the stale marking in case of error"""
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            cursor = conn.execute(
                "UPDATE realdebrid_torrents SET sync_marker = NULL WHERE sync_marker = ?",
                (str(sync_time),)
            )
            conn.commit()
            ui_print(f'[realdebrid_cache] rolled back stale marking for {cursor.rowcount} records', ui_settings.debug)
        except Exception as e:
            ui_print(f'[realdebrid_cache] error rolling back stale marking: {str(e)}', ui_settings.debug)

    def sync_torrents(self):
        """Main sync method with error handling
        
        Returns:
            List of torrent objects if successful, None if failed
        """
        sync_start_time = time.time()

        try:
            ui_print('[realdebrid_cache] starting full refresh sync...', ui_settings.debug)

            # Mark all current records as "potentially stale"
            self.mark_all_as_stale(sync_start_time)

            # Fetch all torrents from Real-Debrid
            torrents = self.fetch_all_torrents()

            if not torrents:
                ui_print('[realdebrid_cache] no torrents fetched, aborting sync', ui_settings.debug)
                self.rollback_stale_marking(sync_start_time)
                return None

            # Process torrents in batches for memory efficiency
            batch_size = 2000  # Optimal balance of performance and memory usage
            for i in range(0, len(torrents), batch_size):
                batch = torrents[i:i + batch_size]
                self.upsert_torrent_batch(batch, sync_start_time)

            # Mark truly deleted records
            self.mark_deleted_records(sync_start_time)

            self.last_refresh = time.time()
            ui_print(f'[realdebrid_cache] sync completed successfully in {time.time() - sync_start_time:.2f} seconds', ui_settings.debug)
            return torrents

        except Exception as e:
            ui_print(f'[realdebrid_cache] sync failed: {str(e)}', ui_settings.debug)
            # Rollback the "stale" marking
            self.rollback_stale_marking(sync_start_time)
            return None

    def fetch_torrent_files(self, torrent_id):
        """Fetch file information from Real-Debrid API for a specific torrent"""
        if not api_key:
            ui_print('[realdebrid_cache] error: Real-Debrid API key not configured', ui_settings.debug)
            return []
        
        try:
            url = f'https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}'
            response = get(url)
            
            if not response or not hasattr(response, 'files'):
                ui_print(f'[realdebrid_cache] error: No files found for torrent {torrent_id}', ui_settings.debug)
                return []
            
            files = []
            for file_ in response.files:
                file_data = {
                    'id': getattr(file_, 'id', None),
                    'path': getattr(file_, 'path', ''),
                    'bytes': getattr(file_, 'bytes', 0),
                    'selected': 1 if getattr(file_, 'selected', 0) == 1 else 0
                }
                files.append(file_data)
            
            return files
        except Exception as e:
            ui_print(f'[realdebrid_cache] error fetching files for torrent {torrent_id}: {str(e)}', ui_settings.debug)
            return []

    def upsert_torrent_files_batch(self, torrent_id, files_data, sync_time):
        """Upsert a batch of torrent files into the database.
        
        Note: sync_time parameter kept for compatibility but not used since we removed sync_marker.
        Files are deleted when their parent torrent is deleted.
        """
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            
            # Insert/update the files that exist
            # Files are automatically considered deleted when their parent torrent is deleted
            for file_data in files_data:
                conn.execute(
                    """
                    INSERT INTO realdebrid_torrent_files (
                        torrent_id, file_id, path, bytes, selected
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(torrent_id, file_id) DO UPDATE SET
                        path=excluded.path,
                        bytes=excluded.bytes,
                        selected=excluded.selected,
                        updated_at=datetime('now')
                    """,
                    (
                        torrent_id,
                        file_data.get('id'),
                        file_data.get('path'),
                        file_data.get('bytes'),
                        file_data.get('selected', 0)
                    )
                )
            
            conn.commit()
            ui_print(f'[realdebrid_cache] upserted {len(files_data)} files for torrent {torrent_id}', ui_settings.debug)
            
        except Exception as e:
            ui_print(f'[realdebrid_cache] error upserting files for torrent {torrent_id}: {str(e)}', ui_settings.debug)
            raise e


    def sync_torrent_files(self):
        """Main sync method for torrent files - fetches files for all active torrents"""
        sync_start_time = time.time()
        
        try:
            ui_print('[realdebrid_cache] starting torrent files sync...', ui_settings.debug)
            
            # Get all active torrents with 'downloaded' status from database
            # Only 'downloaded' torrents have files available - others may be in conversion/queued states
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            cursor = conn.execute(
                "SELECT id FROM realdebrid_torrents WHERE deleted_at IS NULL AND status = 'downloaded'"
            )
            active_torrents = cursor.fetchall()
            
            if not active_torrents:
                ui_print('[realdebrid_cache] no active torrents found, skipping file sync', ui_settings.debug)
                return True
            
            ui_print(f'[realdebrid_cache] syncing files for {len(active_torrents)} torrent(s)...', ui_settings.debug)
            
            # Fetch and upsert files for each torrent
            synced_count = 0
            skipped_count = 0
            failed_count = 0
            
            for (torrent_id,) in active_torrents:
                try:
                    # Check if we already have cached files for this torrent
                    # Note: We don't check deleted_at on files since we rely on parent torrent's deleted_at
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM realdebrid_torrent_files WHERE torrent_id = ?",
                        (torrent_id,)
                    )
                    has_cached_files = cursor.fetchone()[0] > 0
                    
                    if has_cached_files:
                        # Files already cached, skip API call
                        skipped_count += 1
                        ui_print(f'[realdebrid_cache] using cached files for torrent {torrent_id}', ui_settings.debug)
                    else:
                        # No cached files, fetch from API
                        files_data = self.fetch_torrent_files(torrent_id)
                        if files_data:
                            self.upsert_torrent_files_batch(torrent_id, files_data, sync_start_time)
                            synced_count += 1
                        else:
                            # No files found - might be in magnet conversion or error state
                            ui_print(f'[realdebrid_cache] no files found for torrent {torrent_id}', ui_settings.debug)
                        time.sleep(0.5)  # Rate limiting between torrents
                except Exception as e:
                    ui_print(f'[realdebrid_cache] error syncing files for torrent {torrent_id}: {str(e)}', ui_settings.debug)
                    failed_count += 1
            
            # Files are automatically considered deleted when their parent torrent is deleted
            # No need to mark them separately - queries JOIN with parent to check deletion status
            
            ui_print(f'[realdebrid_cache] file sync completed: {synced_count} fetched, {skipped_count} cached, {failed_count} failed in {time.time() - sync_start_time:.2f} seconds', ui_settings.debug)
            return True
            
        except Exception as e:
            ui_print(f'[realdebrid_cache] file sync failed: {str(e)}', ui_settings.debug)
            # No rollback needed since we don't use sync_marker for files anymore
            return False

    def get_torrent_files_by_hash(self, hash_value):
        """Query cached files for a given torrent hash. Returns list of file paths.
        
        Files are automatically filtered by parent torrent's deletion status via JOIN.
        """
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            cursor = conn.execute(
                """SELECT rtf.path 
                   FROM realdebrid_torrent_files rtf
                   JOIN realdebrid_torrents rt ON rtf.torrent_id = rt.id
                   WHERE rt.hash = ? AND rt.deleted_at IS NULL
                   ORDER BY rtf.path""",
                (hash_value,)
            )
            results = cursor.fetchall()
            return [row[0] for row in results if row[0]]
        except Exception as e:
            ui_print(f'[realdebrid_cache] error getting files for hash {hash_value}: {str(e)}', ui_settings.debug)
            return []

    def match_broken_media(self, plex_filename, rd_torrents):
        """Match broken Plex media against Real-Debrid torrents using cached file data.
        
        This method queries the database directly for file paths that match the Plex filename,
        avoiding unreliable torrent filename matching. It finds all potential matches and
        returns the best one.
        
        Args:
            plex_filename: The filename from Plex (full path)
            rd_torrents: List of Real-Debrid torrent objects from fetch_all_torrents() (unused, kept for compatibility)
        
        Returns:
            Tuple of (torrent_id, hash, verified) or (None, None, False) if no match
        """
        import os
        
        if not plex_filename or plex_filename == "No filename available":
            return (None, None, False)
        
        # Extract basename from Plex filename
        plex_basename = os.path.basename(plex_filename) if plex_filename else ""
        
        try:
            import store.sqlite_store as sqlite_store
            conn = sqlite_store._get_connection()
            
            # Query database directly for file paths that match the Plex filename
            # This is more accurate than matching against generic torrent filenames
            # We use multiple matching strategies to catch different path formats
            
            # Strategy 1: Exact basename match (most specific)
            # Files are automatically filtered by parent torrent's deletion status via JOIN
            cursor = conn.execute(
                """SELECT DISTINCT rt.id, rt.hash
                   FROM realdebrid_torrent_files rtf
                   JOIN realdebrid_torrents rt ON rtf.torrent_id = rt.id
                   WHERE rt.deleted_at IS NULL
                   AND (
                       rtf.path LIKE ? OR
                       rtf.path LIKE ? OR
                       rtf.path = ? OR
                       ? LIKE '%' || rtf.path || '%' OR
                       rtf.path LIKE '%' || ? || '%'
                   )
                   ORDER BY 
                       CASE 
                           WHEN rtf.path = ? THEN 1
                           WHEN rtf.path LIKE ? THEN 2
                           WHEN rtf.path LIKE ? THEN 3
                           ELSE 4
                       END
                   LIMIT 1""",
                (
                    f'%/{plex_basename}',  # Path ends with basename
                    f'%{plex_basename}%',  # Path contains basename
                    plex_filename,  # Exact match
                    plex_filename,  # Plex filename contains file path
                    plex_basename,  # File path contains basename
                    plex_filename,  # Priority: exact match
                    f'%/{plex_basename}',  # Priority: ends with basename
                    f'%{plex_basename}%',  # Priority: contains basename
                )
            )
            result = cursor.fetchone()
            
            if result:
                torrent_id, hash_value = result
                # Match is verified since we found it in the file paths
                return (torrent_id, hash_value, True)
            
            # Strategy 2: If no match found, try matching just the basename more loosely
            # This handles cases where paths might be structured differently
            cursor = conn.execute(
                """SELECT DISTINCT rt.id, rt.hash
                   FROM realdebrid_torrent_files rtf
                   JOIN realdebrid_torrents rt ON rtf.torrent_id = rt.id
                   WHERE rt.deleted_at IS NULL
                   AND (
                       LOWER(rtf.path) LIKE LOWER(?) OR
                       LOWER(rtf.path) LIKE LOWER(?)
                   )
                   LIMIT 1""",
                (
                    f'%{plex_basename}%',  # Case-insensitive contains
                    f'%/{plex_basename}',  # Case-insensitive ends with
                )
            )
            result = cursor.fetchone()
            
            if result:
                torrent_id, hash_value = result
                return (torrent_id, hash_value, True)
            
            # No match found
            return (None, None, False)
            
        except Exception as e:
            ui_print(f'[realdebrid_cache] error matching broken media: {str(e)}', ui_settings.debug)
            return (None, None, False)

# Create global cache instance
cache = cache()