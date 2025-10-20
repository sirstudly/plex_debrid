from ui.ui_print import *
from ui import ui_settings
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

        def add(self, plex_watchlist=None, trakt_watchlist=None, overseerr_requests=None, sqlite_requests=None, library_obj=None):
            """Mark a media item as ignored in the database and remove from watchlists."""
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
                
                # Remove from watchlists based on media type
                if self.type == 'movie':
                    # For movies, remove from all watchlists
                    ui_print('[sqlite] removing movie from all watchlists: ' + self.query())
                    self._remove_from_watchlist(self, plex_watchlist, trakt_watchlist, overseerr_requests, sqlite_requests)
                elif self.type == 'episode':
                    # For episodes, remove from non-Plex watchlists only
                    ui_print('[sqlite] removing episode from non-Plex watchlists: ' + self.query())
                    self._remove_from_watchlist(self, None, trakt_watchlist, overseerr_requests, sqlite_requests)
                    
                    # Check if we should remove the entire show from all watchlists
                    if plex_watchlist and library_obj:
                        self._check_and_remove_show_if_all_episodes_ignored(self, plex_watchlist, library_obj, trakt_watchlist, overseerr_requests, sqlite_requests)
                    
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

        def _check_and_remove_show_if_all_episodes_ignored(self, episode, plex_watchlist, library_obj, trakt_watchlist=None, overseerr_requests=None, sqlite_requests=None):
            """Check if all uncollected/released episodes of a show are ignored, and if so, remove the show from all watchlists."""
            try:
                # Find the show that contains this episode
                show = None
                for item in plex_watchlist.data:
                    if item.type == 'show' and hasattr(item, 'Seasons'):
                        for season in item.Seasons:
                            if episode in season.Episodes:
                                show = item
                                break
                        if show:
                            break
                
                if not show:
                    ui_print('[sqlite] could not find show for episode: ' + episode.query(), debug=ui_settings.debug)
                    return
                
                # Get all uncollected/released episodes for this show using the show's uncollected() method
                uncollected_seasons = show.uncollected(library_obj)
                uncollected_episodes = []
                for season in uncollected_seasons:
                    uncollected_episodes.extend(season.Episodes)
                
                if not uncollected_episodes:
                    ui_print('[sqlite] no uncollected episodes found for show: ' + show.title, debug=ui_settings.debug)
                    return
                
                # Check if all uncollected episodes are in the ignored list
                ignored_episodes = [ep for ep in uncollected_episodes if ep in classes.ignore.ignored]
                
                if len(ignored_episodes) == len(uncollected_episodes):
                    # Only remove completed shows, not continuing series
                    if show.hasended():
                        ui_print('[sqlite] all uncollected episodes of completed show "' + show.title + '" are ignored. Removing show from all watchlists.')
                        
                        # Remove the show from all watchlists
                        show._remove_from_watchlist(show, plex_watchlist, trakt_watchlist, overseerr_requests, sqlite_requests)
                        
                        # Clear all episodes of this show from the ignored list
                        episodes_to_remove = []
                        for ignored_item in classes.ignore.ignored:
                            if ignored_item.type == 'episode':
                                # Check if this episode belongs to the show we're removing
                                for season in show.Seasons:
                                    if ignored_item in season.Episodes:
                                        episodes_to_remove.append(ignored_item)
                                        break
                        
                        for ep in episodes_to_remove:
                            classes.ignore.ignored.remove(ep)
                        
                        ui_print('[sqlite] removed ' + str(len(episodes_to_remove)) + ' episodes from ignored list for show: ' + show.title)
                    else:
                        ui_print('[sqlite] all uncollected episodes of continuing series "' + show.title + '" are ignored, but keeping show in watchlist for future episodes.')
                else:
                    ui_print('[sqlite] ' + str(len(ignored_episodes)) + '/' + str(len(uncollected_episodes)) + ' episodes ignored for show: ' + show.title, debug=ui_settings.debug)
                    
            except Exception as e:
                ui_print("[sqlite] error checking show removal: " + str(e), debug=ui_settings.debug)


class watchlist(classes.watchlist):
    """Local SQLite-based watchlist for user-requested releases."""
    autoremove = "none"  # SQLite requests can be both movies and shows
    
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
            
            # Query for new local requests from all media tables
            cursor = conn.execute("""
                SELECT mr.guid, mr.hash, mr.title, mr.requested_at,
                       COALESCE(m.title, s.title, se.title, e.title) as media_title,
                       COALESCE(m.year, s.year, se.year, e.year) as year,
                       COALESCE(m.imdb, s.imdb, se.imdb, e.imdb) as imdb,
                       COALESCE(m.tmdb, s.tmdb, se.tmdb, e.tmdb) as tmdb,
                       COALESCE(m.tvdb, s.tvdb, se.tvdb, e.tvdb) as tvdb,
                       CASE 
                           WHEN m.guid IS NOT NULL THEN 'movie'
                           WHEN s.guid IS NOT NULL THEN 'show'
                           WHEN se.guid IS NOT NULL THEN 'season'
                           WHEN e.guid IS NOT NULL THEN 'episode'
                           ELSE 'movie'  -- Default fallback
                       END as media_type
                FROM media_release mr
                LEFT JOIN media_movie m ON mr.guid = m.guid
                LEFT JOIN media_show s ON mr.guid = s.guid
                LEFT JOIN media_season se ON mr.guid = se.guid
                LEFT JOIN media_episode e ON mr.guid = e.guid
                WHERE mr.status = 'pending' AND mr.requested_at IS NOT NULL
                ORDER BY mr.requested_at DESC
            """)
            
            results = cursor.fetchall()
            new_requests = []
            
            for row in results:
                guid, release_hash, release_title, requested_at, media_title, year, imdb, tmdb, tvdb, media_type = row
                
                # Check if this request is already in our data
                existing = next((item for item in self.data if item.guid == guid and getattr(item, 'local_request_hash', None) == release_hash), None)
                
                if not existing:
                    # Create a media object for the new local request
                    media_obj = type('LocalRequest', (), {
                        'guid': guid,
                        'type': media_type,  # Use the determined media type from the database
                        'title': media_title or release_title,
                        'year': year,
                        'watchlistedAt': time.mktime(time.strptime(requested_at, '%Y-%m-%d %H:%M:%S')) if requested_at else time.time(),
                        'user': [['Local User', 'local']],  # Local user identifier
                        'query': lambda title="": f"{media_type}:{media_title or release_title} ({year})" if media_title and year else f"{media_type}:{release_title}",
                        'EID': [],
                        'local_request_hash': release_hash,
                        'local_request_title': release_title,
                        # Add missing attributes that might be needed for comparison
                        'index': None,  # For seasons
                        'parentIndex': None,  # For episodes
                        'parentGuid': None,  # For seasons/episodes
                        'parentEID': [],  # For seasons/episodes
                        'grandparentGuid': None,  # For episodes
                        'grandparentEID': [],  # For episodes
                        'parentTitle': None,  # For seasons/episodes
                        'grandparentTitle': None  # For episodes
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
    
    def remove(self, item):
        """Remove a local request by setting requested_at to NULL in the database."""
        try:
            # Get database connection
            conn = sqlite_store._get_connection()
            
            # Set requested_at to NULL to effectively "remove" the request
            cursor = conn.execute(
                "UPDATE media_release SET requested_at = NULL WHERE guid = ? AND hash = ?",
                (item.guid, getattr(item, 'local_request_hash', ''))
            )
            
            # Commit the change
            conn.commit()
            
            # Remove from local data
            super().remove(item)
            
            ui_print(f'[sqlite] local request removed: {getattr(item, "title", "Unknown")}')
            return True
            
        except Exception as e:
            ui_print(f"[sqlite] error: couldnt remove local request: {str(e)}", debug=ui_settings.debug)
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
