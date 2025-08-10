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


def match(self):
    return None
