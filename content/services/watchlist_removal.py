from ui.ui_print import *
from ui import ui_settings
from content import classes


name = 'Watchlist Removal'

class ignore(classes.ignore):
    """Top-level ignore service that removes items from all watchlists."""
    
    name = 'Watchlist Removal Ignore Service'

    def add(self):
        """Fallback method for backwards compatibility."""
        self.add_with_watchlists(self, None, None, None, None)

    def add_with_watchlists(self, item, plex_watchlist=None, trakt_watchlist=None, overseerr_requests=None, sqlite_requests=None):
        """Remove this item from all watchlists instead of storing it persistently."""
        try:
            ui_print('[watchlist removal] removing item from all watchlists: ' + item.query())
            
            # For Plex episodes, don't remove (would remove entire show)
            if item.type == 'episode' and plex_watchlist:
                ui_print('[watchlist removal] skipping Plex episode removal (would remove entire show): ' + item.query())
                # Still remove from other services that support episode-level watchlisting
                item._remove_from_watchlist(item, None, trakt_watchlist, overseerr_requests, sqlite_requests)
            else:
                # Remove movies normally, or episodes from non-Plex services
                item._remove_from_watchlist(item, plex_watchlist, trakt_watchlist, overseerr_requests, sqlite_requests)
            
            # Add to in-memory ignored list to prevent re-processing in same session
            if not item in classes.ignore.ignored:
                classes.ignore.ignored += [item]
                
        except Exception as e:
            ui_print("[watchlist removal] error: couldnt remove item from watchlists: " + str(e), debug=ui_settings.debug)

    def remove(self):
        """No-op: items were already removed from watchlists, user must manually re-add."""
        try:
            ui_print('[watchlist removal] item was already removed from watchlists. User must manually re-add to any watchlist: ' + self.query())
            
            # Remove from in-memory ignored list if present
            if self in classes.ignore.ignored:
                classes.ignore.ignored.remove(self)
                
        except Exception as e:
            ui_print("[watchlist removal] error: couldnt remove from ignored list: " + str(e), debug=ui_settings.debug)

    def check(self):
        """Check if this item is currently in the ignored list."""
        # Check if the item is in the in-memory ignored list
        return self in classes.ignore.ignored


def match(self):
    return None
