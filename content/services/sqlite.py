from ui.ui_print import *
from content import classes
from store import sqlite_store
import time


name = 'SQLite Database'

class library():

    name = 'SQLite Database'

    class ignore(classes.ignore):

        name = 'SQLite Database Ignore Service'

        @staticmethod
        def _get_table_name(media_type):
            """Determine the database table name based on media type."""
            if media_type == 'movie':
                return 'media_movie'
            elif media_type == 'show':
                return 'media_show'
            elif media_type == 'season':
                return 'media_season'
            elif media_type == 'episode':
                return 'media_episode'
            else:
                ui_print('[sqlite] error: unknown media type: ' + str(media_type), debug=ui_settings.debug)
                return None

        def add(self):
            """Mark a media item as ignored in the database."""
            try:
                ui_print('[sqlite] marking item as ignored in database: ' + self.query())
                
                # Get database connection
                conn = sqlite_store._get_connection()
                
                # Determine which table to update based on media type
                table = library.ignore._get_table_name(self.type)
                if table is None:
                    return
                
                # Update the ignored flag in the database
                conn.execute(
                    f"UPDATE {table} SET ignored = 1, updated_at = datetime('now') WHERE guid = ?",
                    (self.guid,)
                )
                conn.commit()
                
                # Add to in-memory ignored list if not already there
                if not self in classes.ignore.ignored:
                    classes.ignore.ignored += [self]
                    
            except Exception as e:
                ui_print("[sqlite] error: couldnt mark item as ignored: " + str(e), debug=ui_settings.debug)

        def remove(self):
            """Remove ignored status from a media item in the database."""
            try:
                ui_print('[sqlite] removing ignored status from database: ' + self.query())
                
                # Get database connection
                conn = sqlite_store._get_connection()
                
                # Determine which table to update based on media type
                table = library.ignore._get_table_name(self.type)
                if table is None:
                    return
                
                # Update the ignored flag in the database
                conn.execute(
                    f"UPDATE {table} SET ignored = 0, updated_at = datetime('now') WHERE guid = ?",
                    (self.guid,)
                )
                conn.commit()
                
                # Remove from in-memory ignored list if present
                if self in classes.ignore.ignored:
                    classes.ignore.ignored.remove(self)
                    
            except Exception as e:
                ui_print("[sqlite] error: couldnt remove ignored status: " + str(e), debug=ui_settings.debug)

        def check(self):
            """Check if a media item is marked as ignored in the database."""
            try:
                # Get database connection
                conn = sqlite_store._get_connection()
                
                # Determine which table to query based on media type
                table = library.ignore._get_table_name(self.type)
                if table is None:
                    return False
                
                # Query the database for ignored status
                cursor = conn.execute(
                    f"SELECT ignored FROM {table} WHERE guid = ?",
                    (self.guid,)
                )
                result = cursor.fetchone()
                
                if result and result[0] == 1:
                    # Item is marked as ignored in database
                    if not self in classes.ignore.ignored:
                        classes.ignore.ignored += [self]
                    return True
                
                return False
                
            except Exception as e:
                ui_print("[sqlite] error: couldnt check ignore status: " + str(e), debug=ui_settings.debug)
                return False

        def sync_from_database():
            """Sync the in-memory ignored list with the database."""
            try:
                ui_print('[sqlite] syncing ignored items from database...', debug=ui_settings.debug)
                
                # Get database connection
                conn = sqlite_store._get_connection()
                
                # Clear current in-memory list
                classes.ignore.ignored = []
                
                # Query all ignored items from all tables
                tables = ['media_movie', 'media_show', 'media_season', 'media_episode']
                
                for table in tables:
                    cursor = conn.execute(
                        f"SELECT guid FROM {table} WHERE ignored = 1"
                    )
                    results = cursor.fetchall()
                    
                    for (guid,) in results:
                        # Create a minimal media object for the ignored list
                        # This is a simplified approach - in practice, you might want to
                        # load the full media object from the database
                        ignored_item = type('MediaItem', (), {
                            'guid': guid,
                            'type': table.replace('media_', ''),
                            'query': lambda: f"{table.replace('media_', '')}:{guid}"
                        })()
                        
                        if not ignored_item in classes.ignore.ignored:
                            classes.ignore.ignored += [ignored_item]
                
                ui_print(f'[sqlite] synced {len(classes.ignore.ignored)} ignored items from database', debug=ui_settings.debug)
                
            except Exception as e:
                ui_print("[sqlite] error: couldnt sync from database: " + str(e), debug=ui_settings.debug)


class watchlist(classes.watchlist):
    """Local SQLite-based watchlist for user-requested releases."""
    
    def __init__(self):
        self.data = []
        self._load_local_requests()
    
    def _load_local_requests(self):
        """Load locally requested items from the database."""
        try:
            ui_print('[sqlite] loading local requests from database...', debug=ui_settings.debug)
            
            # Get database connection
            conn = sqlite_store._get_connection()
            
            # Query all local requests that are pending
            cursor = conn.execute("""
                SELECT mr.guid, mr.hash, mr.title, mr.requested_at,
                       m.title as media_title, m.year, m.imdb, m.tmdb, m.tvdb
                FROM media_release mr
                LEFT JOIN media_movie m ON mr.guid = m.guid
                WHERE mr.status = 'pending' AND mr.requested_at IS NOT NULL
                ORDER BY mr.requested_at DESC
            """)
            
            results = cursor.fetchall()
            
            for row in results:
                guid, release_hash, release_title, requested_at, media_title, year, imdb, tmdb, tvdb = row
                
                # Create a media object for the local request
                media_obj = type('LocalRequest', (), {
                    'guid': guid,
                    'type': 'movie',  # We'll need to determine this from the media tables
                    'title': media_title or release_title,
                    'year': year,
                    'watchlistedAt': time.mktime(time.strptime(requested_at, '%Y-%m-%d %H:%M:%S')) if requested_at else time.time(),
                    'user': [['Local User', 'local']],  # Local user identifier
                    'query': lambda: f"movie:{media_title or release_title} ({year})" if media_title and year else f"movie:{release_title}",
                    'EID': [],
                    'local_request_hash': release_hash,
                    'local_request_title': release_title
                })()
                
                # Add EID if available
                if imdb:
                    media_obj.EID.append(f'imdb://{imdb}')
                if tmdb:
                    media_obj.EID.append(f'tmdb://{tmdb}')
                if tvdb:
                    media_obj.EID.append(f'tvdb://{tvdb}')
                
                self.data.append(media_obj)
            
            ui_print(f'[sqlite] loaded {len(self.data)} local requests from database', debug=ui_settings.debug)
            
        except Exception as e:
            ui_print("[sqlite] error: couldnt load local requests: " + str(e), debug=ui_settings.debug)
    
    def update(self):
        """Check for new local requests in the database."""
        try:
            # Get database connection
            conn = sqlite_store._get_connection()
            
            # Query for new local requests
            cursor = conn.execute("""
                SELECT mr.guid, mr.hash, mr.title, mr.requested_at,
                       m.title as media_title, m.year, m.imdb, m.tmdb, m.tvdb
                FROM media_release mr
                LEFT JOIN media_movie m ON mr.guid = m.guid
                WHERE mr.status = 'pending' AND mr.requested_at IS NOT NULL
                ORDER BY mr.requested_at DESC
            """)
            
            results = cursor.fetchall()
            new_requests = []
            
            for row in results:
                guid, release_hash, release_title, requested_at, media_title, year, imdb, tmdb, tvdb = row
                
                # Check if this request is already in our data
                existing = next((item for item in self.data if item.guid == guid and getattr(item, 'local_request_hash', None) == release_hash), None)
                
                if not existing:
                    # Create a media object for the new local request
                    media_obj = type('LocalRequest', (), {
                        'guid': guid,
                        'type': 'movie',  # We'll need to determine this from the media tables
                        'title': media_title or release_title,
                        'year': year,
                        'watchlistedAt': time.mktime(time.strptime(requested_at, '%Y-%m-%d %H:%M:%S')) if requested_at else time.time(),
                        'user': [['Local User', 'local']],  # Local user identifier
                        'query': lambda: f"movie:{media_title or release_title} ({year})" if media_title and year else f"movie:{release_title}",
                        'EID': [],
                        'local_request_hash': release_hash,
                        'local_request_title': release_title
                    })()
                    
                    # Add EID if available
                    if imdb:
                        media_obj.EID.append(f'imdb://{imdb}')
                    if tmdb:
                        media_obj.EID.append(f'tmdb://{tmdb}')
                    if tvdb:
                        media_obj.EID.append(f'tvdb://{tvdb}')
                    
                    new_requests.append(media_obj)
                    ui_print(f'[sqlite] found new local request: {media_obj.query()}')
            
            # Add new requests to data
            self.data.extend(new_requests)
            
            # Remove processed requests
            self.data = [item for item in self.data if not self._is_request_processed(item)]
            
            return len(new_requests) > 0
            
        except Exception as e:
            ui_print("[sqlite] error: couldnt update local requests: " + str(e), debug=ui_settings.debug)
            return False
    
    def _is_request_processed(self, item):
        """Check if a local request has been processed."""
        try:
            conn = sqlite_store._get_connection()
            cursor = conn.execute(
                "SELECT status FROM media_release WHERE guid = ? AND hash = ?",
                (item.guid, getattr(item, 'local_request_hash', ''))
            )
            result = cursor.fetchone()
            return result and result[0] != 'pending'
        except:
            return False

def match(self):
    return None
