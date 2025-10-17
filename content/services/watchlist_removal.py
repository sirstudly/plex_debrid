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

    def add_with_watchlists(self, item, plex_watchlist=None, trakt_watchlist=None, overseerr_requests=None, sqlite_requests=None, library=None):
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
            
            # For episodes, check if we should remove the entire show from Plex watchlist
            if item.type == 'episode' and plex_watchlist and library:
                self._check_and_remove_show_if_all_episodes_ignored(item, plex_watchlist, library)
                
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

    def _check_and_remove_show_if_all_episodes_ignored(self, episode, plex_watchlist, library):
        """Check if all uncollected/released episodes of a show are ignored, and if so, remove the show from Plex watchlist."""
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
                ui_print('[watchlist removal] could not find show for episode: ' + episode.query(), debug=ui_settings.debug)
                return
            
            # Get all uncollected/released episodes for this show using the show's uncollected() method
            uncollected_seasons = show.uncollected(library)
            uncollected_episodes = []
            for season in uncollected_seasons:
                uncollected_episodes.extend(season.Episodes)
            
            if not uncollected_episodes:
                ui_print('[watchlist removal] no uncollected episodes found for show: ' + show.title, debug=ui_settings.debug)
                return
            
            # Check if all uncollected episodes are in the ignored list
            ignored_episodes = [ep for ep in uncollected_episodes if ep in classes.ignore.ignored]
            
            if len(ignored_episodes) == len(uncollected_episodes):
                # Only remove completed shows, not continuing series
                if show.hasended():
                    ui_print('[watchlist removal] all uncollected episodes of completed show "' + show.title + '" are ignored. Removing show from Plex watchlist.')
                    
                    # Remove the show from Plex watchlist
                    plex_watchlist.remove(show)
                    
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
                    
                    ui_print('[watchlist removal] removed ' + str(len(episodes_to_remove)) + ' episodes from ignored list for show: ' + show.title)
                else:
                    ui_print('[watchlist removal] all uncollected episodes of continuing series "' + show.title + '" are ignored, but keeping show in watchlist for future episodes.')
            else:
                ui_print('[watchlist removal] ' + str(len(ignored_episodes)) + '/' + str(len(uncollected_episodes)) + ' episodes ignored for show: ' + show.title, debug=ui_settings.debug)
                
        except Exception as e:
            ui_print("[watchlist removal] error checking show removal: " + str(e), debug=ui_settings.debug)


def match(self):
    return None
