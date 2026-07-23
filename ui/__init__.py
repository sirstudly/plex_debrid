from base import *

import content
import scraper
import releases
import debrid
import usenet
from ui import ui_settings
from ui.ui_print import *
from settings import *
from store import sqlite_store

#import uvicorn

config_dir = ""
service_mode = False

class option:
    def __init__(self, name, cls, key):
        self.name = name
        self.cls = cls
        self.key = key

    def input(self):
        func = getattr(self.cls, self.key)
        func()

def ignored():
    back = False
    while not back:
        ui_cls('Options/Ignored Media/')
        if len(content.classes.ignore.ignored) == 0:
            library = content.classes.library()[0]()
            if len(library) > 0:
                # get entire plex_watchlist
                plex_watchlist = content.services.plex.watchlist()
                # get entire trakt_watchlist
                trakt_watchlist = content.services.trakt.watchlist()
                print('checking new content ...')
                for iterator in itertools.zip_longest(plex_watchlist, trakt_watchlist):
                    for element in iterator:
                        if hasattr(element, 'uncollected') and hasattr(element, 'watched'):
                            element.watched()
                            element.uncollected(library)
            print()
        print('0) Back')
        indices = []
        for index, element in enumerate(content.classes.ignore.ignored):
            print(str(index + 1) + ') ' + element.query())
            indices += [str(index + 1)]
        print()
        choice = input('Choose a media item that you want to remove from the ignored list: ')
        if choice in indices:
            print("Media item: " + content.classes.ignore.ignored[int(choice) - 1].query() + ' removed from ignored list.')
            content.classes.ignore.ignored[int(choice) - 1].unwatch()
            time.sleep(3)
        elif choice == '0':
            back = True
    options()

def web_interface():
    ui_cls('Options/Web Interface/')
    print('Plex Debrid Web Interface')
    print('========================')
    print()
    print('The web interface provides a dashboard to monitor pending media items.')
    print()
    print('To start the web server:')
    print('1. Run: python web_server.py')
    print('2. Open your browser to: http://127.0.0.1:8008/dashboard')
    print()
    print('Available endpoints:')
    print('- Dashboard: http://127.0.0.1:8008/dashboard')
    print('- API Docs: http://127.0.0.1:8008/docs')
    print('- Health Check: http://127.0.0.1:8008/health')
    print()
    print('Press Enter to return to the main menu.')
    input()

def _scraper_sort_releases(scraped_releases, version):
    if version is None:
        return
    sort_version = version
    if scraped_releases and getattr(scraped_releases[0], 'type', '') == 'nzb':
        sort_version = copy.deepcopy(version)
        sort_version.rules = [r for r in sort_version.rules if r[0] != "cache status"]
    releases.sort(scraped_releases, sort_version)


def _scraper_download_release(release, query, obj):
    if getattr(release, 'type', '') == 'nzb':
        obj.Releases = [release]
        return usenet.download(obj, stream=True, query=query, force=True)
    release.Releases = [release]
    release.type = ("show" if regex.search(r'(S[0-9]+|SEASON|E[0-9]+|EPISODE|[0-9]+-[0-9])', release.title, regex.I) else "movie")
    return debrid.download(release, stream=True, query=query, force=True)


def scrape():
    ui_cls('Options/Scraper/')
    print('Press Enter to return to the main menu.')
    print()
    print("Please choose a version to scrape for: ")
    print()
    obj = releases.release('', '', '', [], 0, [])
    indices = []
    for index, version in enumerate(releases.sort.versions):
        print(str(index + 1) + ') ' + version[0] + (' (disabled)' if '\u0336' in version[0] else ''))
        indices += [str(index + 1)]
    print(str(index + 2) + ') Scrape without defining a version')
    indices += [str(index + 2)]
    print()
    choice = input("Choose a version: ")
    if choice in indices and not choice == str(index + 2):
        obj.version = releases.sort.version(releases.sort.versions[int(choice) - 1][0],
                                            releases.sort.versions[int(choice) - 1][1],
                                            releases.sort.versions[int(choice) - 1][2],
                                            releases.sort.versions[int(choice) - 1][3])
    elif choice == str(index + 2):
        obj.version = None
    else:
        return
    while True:
        ui_cls('Options/Scraper/')
        print('Press Enter to return to the main menu.')
        print()
        query = input("Enter a query: ")
        if query == '':
            return
        print()
        if hasattr(obj,"version"):
            if not obj.version == None:
                for trigger, operator, value in obj.version.triggers:
                    if trigger == "scraper sources":
                        if operator in ["==","include"]:
                            if value in scraper.services.active:
                                scraper.services.overwrite += [value]
                        elif operator == "exclude":
                            if value in scraper.services.active:
                                for s in scraper.services.active:
                                    if not s == value:
                                        scraper.services.overwrite += [s]
                    if trigger == "scraping adjustment":
                        if operator == "add text before title":
                            query = value + query
                        elif operator == "add text after title":
                            query = query + value
        scraped_releases = scraper.scrape_with_usenet_fallback(query)
        if len(scraped_releases) > 0:
            obj.Releases = scraped_releases
            if getattr(scraped_releases[0], 'type', '') != 'nzb':
                debrid.check(obj, force=True)
                scraped_releases = obj.Releases
            _scraper_sort_releases(scraped_releases, obj.version)
            usenet_results = getattr(scraped_releases[0], 'type', '') == 'nzb'
            back = False
            while not back:
                ui_cls('Options/Scraper/')
                print("0) Back")
                releases.print_releases(scraped_releases)
                print()
                if usenet_results:
                    print("Type 'auto' to automatically grab the first usenet release.")
                else:
                    print("Type 'auto' to automatically download the first cached release.")
                print()
                choice = input("Choose a release to download: ")
                try:
                    if choice == 'auto':
                        release = scraped_releases[0]
                        if _scraper_download_release(release, query, obj):
                            if not usenet_results:
                                content.classes.media.collect(release)
                            scraped_releases.remove(scraped_releases[0])
                            time.sleep(3)
                        elif usenet_results:
                            print()
                            print("Usenet grab failed. Choose another release?")
                            time.sleep(3)
                        else:
                            print()
                            print("These releases do not seem to be cached on your debrid services. Add uncached torrent?")
                            print()
                            print("0) Back")
                            print("1) Add uncached torrent")
                            print()
                            choice = input("Choose an action: ")
                            if choice == '1':
                                release.Releases = [release]
                                release.type = ("show" if regex.search(r'(S[0-9]+|SEASON|E[0-9]+|EPISODE|[0-9]+-[0-9])', release.title, regex.I) else "movie")
                                if debrid.download(release, stream=False, query=query, force=True):
                                    content.classes.media.collect(release)
                                    scraped_releases.remove(scraped_releases[0])
                                    time.sleep(3)
                    elif int(choice) <= len(scraped_releases) and not int(choice) <= 0:
                        release = scraped_releases[int(choice) - 1]
                        download_query = query if usenet_results else release.title
                        if _scraper_download_release(release, download_query, obj):
                            if not usenet_results:
                                content.classes.media.collect(release)
                            scraped_releases.remove(scraped_releases[int(choice) - 1])
                            time.sleep(3)
                        elif usenet_results:
                            print()
                            print("Usenet grab failed. Choose another release?")
                            time.sleep(3)
                        else:
                            print()
                            print(
                                "This release does not seem to be cached on your debrid services. Add uncached torrent?")
                            print()
                            print("0) Back")
                            print("1) Add uncached torrent")
                            print()
                            choice2 = input("Choose an action: ")
                            if choice2 == '1':
                                release.Releases = [release]
                                release.type = ("show" if regex.search(r'(S[0-9]+|SEASON|E[0-9]+|EPISODE|[0-9]+-[0-9])', release.title, regex.I) else "movie")
                                if debrid.download(release, stream=False, query=query, force=True):
                                    content.classes.media.collect(release)
                                    scraped_releases.remove(scraped_releases[int(choice) - 1])
                                    time.sleep(3)
                                else:
                                    print()
                                    print(
                                        "There was an error adding this uncached torrent to your debrid service. Choose another release?")
                    elif choice == '0':
                        back = True
                except Exception as e:
                    print("error: " + str(e))
                    back = False
        else:
            print("No releases were found!")
            time.sleep(3)

def settings():
    back = False
    while not back:
        list = settings_list
        ui_cls('Options/Settings/')
        print('0) Back')
        indices = []
        for index, category in enumerate(list):
            print(str(index + 1) + ') ' + category[0])
            indices += [str(index + 1)]
        print()
        print('Type "discard" to go back and discard changes.')
        print()
        choice = input('Choose an action: ')
        if choice in indices:
            ui_cls('Options/Settings/' + list[int(choice) - 1][0] + '/')
            settings = []
            for index, setting in enumerate(list[int(choice) - 1][1]):
                if not setting.hidden:
                    settings += [setting]
            if len(settings) > 1:
                print('0) Back')
                for index, setting in enumerate(settings):
                    print(str(index + 1) + ') ' + setting.name)
                print()
                choice2 = input('Choose an action: ')
            elif len(settings) == 1:
                choice2 = '1'
            else:
                choice2 = '0'
            for index, setting in enumerate(settings):
                if choice2 == str(index + 1):
                    ui_cls('Options/Settings/' + list[int(choice) - 1][0] + '/' + setting.name)
                    setting.input()
        elif choice == '0':
            save()
            back = True
        elif choice == 'discard':
            load(doprint=True)
            back = True

def repair_broken_media(non_interactive=False):
    if not non_interactive:
        ui_cls('Options/Repair Broken Media/')
    import content.services.plex as plex
    import debrid.services.realdebrid as realdebrid
    import time
    
    if not plex.users:
        ui_print("Error: No Plex users configured.")
        if not non_interactive:
            ui_print("")
            ui_print('Press Enter to return to the main menu.')
            input()
        return
    
    if not hasattr(plex.library, 'url') or not plex.library.url:
        ui_print("Error: Plex library URL not configured.")
        if not non_interactive:
            ui_print("")
            ui_print('Press Enter to return to the main menu.')
            input()
        return
    
    ui_print('Querying Plex for broken media...')
    ui_print("")
    
    broken_items = []
    
    try:
        # Get library sections
        url = plex.library.url + '/library/sections/?X-Plex-Token=' + plex.users[0][1]
        response = plex.get(plex.session, url)
        
        if not response or not hasattr(response, 'MediaContainer') or not hasattr(response.MediaContainer, 'Directory'):
            ui_print("Error: Could not retrieve library sections from Plex.")
            if not non_interactive:
                ui_print("")
                ui_print('Press Enter to return to the main menu.')
                input()
            return
        
        sections = []
        for Directory in response.MediaContainer.Directory:
            if Directory.type in ["movie", "show"]:
                types = ['1'] if Directory.type == "movie" else ['2', '3', '4']
                sections.append((Directory.key, types, Directory.title))
        
        if not sections:
            ui_print("No library sections found.")
            if not non_interactive:
                ui_print("")
                ui_print('Press Enter to return to the main menu.')
                input()
            return
        
        # Query each section for broken media (trash=1)
        for section_key, types, section_title in sections:
            for type_code in types:
                url = plex.library.url + '/library/sections/' + section_key + '/all?type=' + type_code + '&trash=1&X-Plex-Token=' + plex.users[0][1]
                response = plex.get(plex.session, url)
                
                if response and hasattr(response, 'MediaContainer') and hasattr(response.MediaContainer, 'Metadata'):
                    for element in response.MediaContainer.Metadata:
                        # Get the name
                        if hasattr(element, 'title'):
                            name = element.title
                            if hasattr(element, 'grandparentTitle'):
                                # Episode
                                name = f"{element.grandparentTitle} - {element.parentTitle} - {name}"
                            elif hasattr(element, 'parentTitle'):
                                # Season
                                name = f"{element.parentTitle} - {name}"
                        else:
                            name = "Unknown"
                        
                        # Get the filename(s)
                        filenames = []
                        if hasattr(element, 'Media'):
                            for Media in element.Media:
                                if hasattr(Media, 'Part'):
                                    for Part in Media.Part:
                                        if hasattr(Part, 'file'):
                                            filenames.append(Part.file)
                        
                        if filenames:
                            for filename in filenames:
                                broken_items.append((name, filename))
                        else:
                            broken_items.append((name, "No filename available"))
        
        # Fetch Real-Debrid torrents and sync file cache
        ui_print('Querying Real-Debrid for torrents...')
        ui_print("")
        rd_torrents = []
        
        if not realdebrid.api_key:
            ui_print("Warning: Real-Debrid API key not configured. Skipping Real-Debrid matching.")
            ui_print("")
        else:
            try:
                # Sync torrents database first to ensure we have up-to-date torrent data
                ui_print('Syncing Real-Debrid torrents cache...')
                ui_print("")
                rd_torrents = realdebrid.cache.sync_torrents()
                
                if rd_torrents is None:
                    ui_print("Error: Failed to sync Real-Debrid torrents.")
                    ui_print("")
                else:
                    ui_print(f"Found {len(rd_torrents)} Real-Debrid torrent(s).")
                    ui_print("")
                    
                    # Sync torrent files cache to ensure we have file data for matching
                    # This uses the database torrent cache which is now up-to-date
                    ui_print('Syncing Real-Debrid torrent files cache...')
                    ui_print("")
                    realdebrid.cache.sync_torrent_files()
                    ui_print("")
            except Exception as e:
                ui_print(f"Error querying Real-Debrid: {str(e)}")
                ui_print("")
        
        # Track matched Real-Debrid IDs and hashes
        # Structure: hash -> list of (id, name, filename) tuples
        matched_by_hash = {}  # hash -> [(id, name, filename), ...]
        
        # Display results with Real-Debrid matching
        if broken_items:
            ui_print(f"Found {len(broken_items)} broken media item(s):")
            ui_print("")
            for name, filename in broken_items:
                ui_print(f"Name: {name}")
                ui_print(f"Filename: {filename}")
                
                # Use cache.match_broken_media() for matching
                rd_match, rd_hash, verified = realdebrid.cache.match_broken_media(filename, rd_torrents)
                
                if rd_match:
                    ui_print(f"Real-Debrid ID: {rd_match}")
                    if rd_hash:
                        ui_print(f"Real-Debrid Hash: {rd_hash}")
                        if verified:
                            ui_print("  Verified: Match confirmed by checking cached torrent files")
                            # Track by hash - multiple items can share the same hash
                            if rd_hash not in matched_by_hash:
                                matched_by_hash[rd_hash] = []
                            matched_by_hash[rd_hash].append((rd_match, name, filename))
                        else:
                            ui_print("  Verification failed: Skipping (filename mismatch in cached torrent files)")
                    else:
                        ui_print("Real-Debrid Hash: Not available")
                else:
                    ui_print("Real-Debrid match not found.")
                ui_print("")
        else:
            ui_print("No broken media found.")
            ui_print("")
        
        # Repair: Delete and re-add matched torrents (one hash at a time)
        if matched_by_hash and realdebrid.api_key:
            ui_print("")
            ui_print(f"Repairing {len(matched_by_hash)} unique hash(es)...")
            ui_print("")
            
            added_count = 0
            failed_count = 0
            
            for hash_value, items in matched_by_hash.items():
                ui_print(f"Processing hash: {hash_value}")
                ui_print(f"  Found {len(items)} matched item(s) with this hash")
                
                # Delete all existing Real-Debrid items with this hash
                # Deduplicate torrent IDs since multiple items may point to the same torrent
                unique_torrent_ids = {}
                for item in items:
                    torrent_id, name, filename = item
                    if torrent_id not in unique_torrent_ids:
                        unique_torrent_ids[torrent_id] = name  # Store first name for display
                
                deleted_count = 0
                for torrent_id, name in unique_torrent_ids.items():
                    try:
                        realdebrid.delete(f'https://api.real-debrid.com/rest/1.0/torrents/delete/{torrent_id}')
                        deleted_count += 1
                        ui_print(f"  Deleted Real-Debrid torrent ID: {torrent_id} (Name: {name})")
                        time.sleep(1.0)  # Rate limiting (DELETE not rate-limited by session, so manual delay)
                    except Exception as e:
                        # Check if error is because torrent was already deleted
                        error_msg = str(e)
                        if '404' in error_msg or 'unknown_ressource' in error_msg or 'invalid id' in error_msg.lower():
                            ui_print(f"  Torrent ID {torrent_id} already deleted (skipping)")
                            deleted_count += 1  # Count as success since it's already gone
                        else:
                            ui_print(f"  Error deleting torrent {torrent_id}: {str(e)}")
                
                ui_print(f"  Deleted {deleted_count} unique torrent(s) with hash {hash_value}")
                ui_print("")
                
                # Re-add the hash
                try:
                    # Create magnet link from hash
                    magnet_link = f"magnet:?xt=urn:btih:{hash_value}"
                    
                    # Add magnet to Real-Debrid
                    response = realdebrid.post('https://api.real-debrid.com/rest/1.0/torrents/addMagnet', {'magnet': magnet_link})
                    
                    if hasattr(response, 'error'):
                        ui_print(f"  Error adding hash {hash_value}: {response.error}")
                        failed_count += 1
                    elif hasattr(response, 'id'):
                        torrent_id = str(response.id)
                        # Use the first name from the items list for display
                        _, name, fname = items[0]
                        ui_print(f"  Re-added torrent (Hash: {hash_value}, Name: {name}, Filename: {fname}) - New ID: {torrent_id}")
                        
                        # Wait for magnet conversion
                        time.sleep(1.0)
                        
                        # Get torrent info to select files
                        torrent_info = realdebrid.get(f'https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}')
                        
                        if torrent_info and hasattr(torrent_info, 'status') and torrent_info.status == 'magnet_error':
                            ui_print(f"  Error: Magnet conversion failed for hash {hash_value}")
                            realdebrid.delete(f'https://api.real-debrid.com/rest/1.0/torrents/delete/{torrent_id}')
                            failed_count += 1
                        elif torrent_info and hasattr(torrent_info, 'files') and len(torrent_info.files) > 0:
                            # Filter files by media extensions
                            media_file_ids = []
                            for file_ in torrent_info.files:
                                file_path = getattr(file_, 'path', '')
                                if file_path and file_path.endswith(tuple(realdebrid.media_file_extensions)):
                                    file_id = getattr(file_, 'id', None)
                                    if file_id is not None:
                                        media_file_ids.append(str(file_id))
                            
                            if len(media_file_ids) > 0:
                                # Select only media files
                                select_response = realdebrid.post(
                                    f'https://api.real-debrid.com/rest/1.0/torrents/selectFiles/{torrent_id}',
                                    {'files': ",".join(media_file_ids)}
                                )
                                ui_print(f"  Selected {len(media_file_ids)} media file(s)")
                            else:
                                ui_print(f"  Warning: No media files found in torrent")
                        else:
                            ui_print(f"  Warning: No files found in torrent or torrent info unavailable")
                        
                        added_count += 1
                    else:
                        ui_print(f"  Unexpected response when adding hash {hash_value}")
                        failed_count += 1
                    
                    time.sleep(1.0)  # Rate limiting
                except Exception as e:
                    ui_print(f"  Error re-adding hash {hash_value}: {str(e)}")
                    failed_count += 1
                
                ui_print("")  # Blank line between hash processing
            
            ui_print("")
            ui_print(f"Repair complete: {added_count} torrent(s) re-added, {failed_count} failed.")
            ui_print("")
        
    except Exception as e:
        ui_print(f"Error: {str(e)}")
        ui_print("")
    
    if not non_interactive:
        ui_print('Press Enter to return to the main menu.')
        input()

def _parse_plex_eids(item):
    """Extract imdb/tmdb/tvdb ids from a Plex media item's EID list."""
    ids = {'imdb': None, 'tmdb': None, 'tvdb': None}
    eids = getattr(item, 'EID', None) or []
    for eid in eids:
        try:
            service, value = str(eid).split('://', 1)
        except ValueError:
            continue
        service = service.lower()
        if service in ids and value:
            ids[service] = value
    return ids

def _prompt_choice(label, items, name_attr='name', id_attr='id'):
    """Print a numbered list and return the chosen item, or None if cancelled."""
    if not items:
        ui_print('No ' + label.lower() + ' available.')
        return None
    print()
    print('Select ' + label + ':')
    for index, item in enumerate(items):
        name = getattr(item, name_attr, None) or getattr(item, 'path', str(item))
        print(str(index + 1) + ') ' + str(name))
    print('0) Cancel')
    print()
    while True:
        choice = input('Choose ' + label + ': ').strip()
        if choice == '0':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            return items[int(choice) - 1]
        print('Invalid choice, try again.')

def _ensure_arr_settings(service, service_label, url_setting_name, key_setting_name):
    """
    Ensure Arr base_url + api_key work. Prompt and persist if needed.
    Returns True if connected, False if user cancelled.
    """
    from settings import settings_list

    def _find_setting(name):
        for category, allsettings in settings_list:
            for setting in allsettings:
                if setting.name == name:
                    return setting
        return None

    while not service.probe():
        print()
        if not service.base_url or not service.api_key:
            print(service_label + ' is not configured yet.')
        else:
            print('Could not reach ' + service_label + ' at "' + service.base_url + '" with the current API key.')
        print('Enter settings below, or press Enter on base URL to cancel.')
        print()
        url_setting = _find_setting(url_setting_name)
        key_setting = _find_setting(key_setting_name)
        if url_setting is None or key_setting is None:
            ui_print('Error: ' + service_label + ' settings are missing from settings_list.')
            return False
        print('Current base URL: ' + (service.base_url or '(empty)'))
        new_url = input('Please specify your ' + service_label + ' base URL: ').strip()
        if new_url == '':
            return False
        url_setting.set(new_url)
        print()
        print('Current API key: ' + (('*' * min(8, len(service.api_key))) if service.api_key else '(empty)'))
        new_key = input('Please specify your ' + service_label + ' API Key: ').strip()
        if new_key == '':
            return False
        key_setting.set(new_key)
        save(doprint=False)
        if service.probe():
            print()
            print(service_label + ' connection OK.')
            return True
        print()
        print(service_label + ' still unreachable. Check URL/API key and try again.')
    return True

def import_plex_to_radarr():
    ui_cls('Options/Import Plex library into Radarr/')
    import content.services.plex as plex
    import content.services.radarr as radarr

    if not plex.users:
        ui_print('Error: No Plex users configured. Set up Plex users in Settings first.')
        print()
        input('Press Enter to return to the main menu.')
        return
    if not getattr(plex.library, 'url', None):
        ui_print('Error: Plex server address not configured.')
        print()
        input('Press Enter to return to the main menu.')
        return

    if not _ensure_arr_settings(radarr, 'Radarr', 'Radarr Base URL', 'Radarr API Key'):
        print()
        input('Press Enter to return to the main menu.')
        return

    profiles = radarr.get_quality_profiles()
    folders = radarr.get_root_folders()
    profile = _prompt_choice('Quality Profile', profiles, name_attr='name')
    if profile is None:
        print()
        input('Press Enter to return to the main menu.')
        return
    folder = _prompt_choice('Root Folder', folders, name_attr='path')
    if folder is None:
        print()
        input('Press Enter to return to the main menu.')
        return

    root_path = getattr(folder, 'path', None)
    quality_profile_id = getattr(profile, 'id', None)
    if not root_path or quality_profile_id is None:
        ui_print('Error: invalid quality profile or root folder selection.')
        print()
        input('Press Enter to return to the main menu.')
        return

    print()
    ui_print('Scanning Plex movie library (including unavailable items)...')
    movies = plex.library.list_for_arr_import('movie')
    if not movies:
        ui_print('No movies found to import.')
        print()
        input('Press Enter to return to the main menu.')
        return

    print()
    print('About to import ' + str(len(movies)) + ' movie(s) into Radarr.')
    print('  Quality Profile: ' + str(getattr(profile, 'name', quality_profile_id)))
    print('  Root Folder:     ' + str(root_path))
    print('  Search on add:   yes')
    print('  Each title is processed as soon as its IDs are available.')
    print()
    confirm = input('Continue? [y/N]: ').strip().lower()
    if confirm not in ('y', 'yes'):
        print()
        input('Press Enter to return to the main menu.')
        return

    ui_print('Loading existing Radarr movies for duplicate checks...')
    existing_tmdb, existing_imdb = radarr.get_existing_movies()

    added = 0
    skipped_existing = 0
    skipped_no_id = 0
    failed = 0
    total = len(movies)

    print()
    for index, item in enumerate(movies):
        title = getattr(item, 'title', 'unknown')
        year = getattr(item, 'year', '')
        label = title + ((' (' + str(year) + ')') if year else '')
        prefix = '[' + str(index + 1) + '/' + str(total) + '] '

        item = plex.library.enrich_for_arr_import(item)
        if item is None:
            ui_print(prefix + 'failed (metadata): ' + label)
            failed += 1
            continue

        ids = _parse_plex_eids(item)
        tmdb_id = int(ids['tmdb']) if ids['tmdb'] and str(ids['tmdb']).isdigit() else None
        imdb_id = ids['imdb']

        if not tmdb_id and not imdb_id:
            ui_print(prefix + 'skip (no id): ' + label)
            skipped_no_id += 1
            continue

        if tmdb_id and tmdb_id in existing_tmdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue
        if imdb_id and str(imdb_id).lower() in existing_imdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue

        lookup = radarr.lookup_movie(tmdb_id=tmdb_id, imdb_id=imdb_id)
        if lookup is None:
            ui_print(prefix + 'failed (lookup): ' + label)
            failed += 1
            continue

        lookup_tmdb = getattr(lookup, 'tmdbId', None)
        lookup_imdb = getattr(lookup, 'imdbId', None)
        if lookup_tmdb and int(lookup_tmdb) in existing_tmdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue
        if lookup_imdb and str(lookup_imdb).lower() in existing_imdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue

        ok, error = radarr.add_movie(lookup, quality_profile_id, root_path, search=True)
        if ok:
            ui_print(prefix + 'added: ' + label)
            added += 1
            if lookup_tmdb:
                existing_tmdb.add(int(lookup_tmdb))
            if lookup_imdb:
                existing_imdb.add(str(lookup_imdb).lower())
        else:
            ui_print(prefix + 'failed: ' + label + ' — ' + str(error))
            failed += 1
        time.sleep(0.25)

    print()
    ui_print('Radarr import complete.')
    ui_print('  Added:            ' + str(added))
    ui_print('  Skipped existing: ' + str(skipped_existing))
    ui_print('  Skipped no id:    ' + str(skipped_no_id))
    ui_print('  Failed:           ' + str(failed))
    print()
    input('Press Enter to return to the main menu.')

def import_plex_to_sonarr():
    ui_cls('Options/Import Plex library into Sonarr/')
    import content.services.plex as plex
    import content.services.sonarr as sonarr

    if not plex.users:
        ui_print('Error: No Plex users configured. Set up Plex users in Settings first.')
        print()
        input('Press Enter to return to the main menu.')
        return
    if not getattr(plex.library, 'url', None):
        ui_print('Error: Plex server address not configured.')
        print()
        input('Press Enter to return to the main menu.')
        return

    if not _ensure_arr_settings(sonarr, 'Sonarr', 'Sonarr Base URL', 'Sonarr API Key'):
        print()
        input('Press Enter to return to the main menu.')
        return

    profiles = sonarr.get_quality_profiles()
    folders = sonarr.get_root_folders()
    language_profiles = sonarr.get_language_profiles()

    profile = _prompt_choice('Quality Profile', profiles, name_attr='name')
    if profile is None:
        print()
        input('Press Enter to return to the main menu.')
        return
    folder = _prompt_choice('Root Folder', folders, name_attr='path')
    if folder is None:
        print()
        input('Press Enter to return to the main menu.')
        return

    language_profile_id = None
    if language_profiles:
        language_profile = _prompt_choice('Language Profile', language_profiles, name_attr='name')
        if language_profile is None:
            print()
            input('Press Enter to return to the main menu.')
            return
        language_profile_id = getattr(language_profile, 'id', None)

    root_path = getattr(folder, 'path', None)
    quality_profile_id = getattr(profile, 'id', None)
    if not root_path or quality_profile_id is None:
        ui_print('Error: invalid quality profile or root folder selection.')
        print()
        input('Press Enter to return to the main menu.')
        return

    print()
    ui_print('Scanning Plex TV library (including unavailable items)...')
    shows = plex.library.list_for_arr_import('show')
    if not shows:
        ui_print('No shows found to import.')
        print()
        input('Press Enter to return to the main menu.')
        return

    print()
    print('About to import ' + str(len(shows)) + ' show(s) into Sonarr.')
    print('  Quality Profile: ' + str(getattr(profile, 'name', quality_profile_id)))
    print('  Root Folder:     ' + str(root_path))
    if language_profile_id is not None:
        print('  Language Profile: ' + str(language_profile_id))
    print('  Search on add:   yes')
    print('  Each title is processed as soon as its IDs are available.')
    print()
    confirm = input('Continue? [y/N]: ').strip().lower()
    if confirm not in ('y', 'yes'):
        print()
        input('Press Enter to return to the main menu.')
        return

    ui_print('Loading existing Sonarr series for duplicate checks...')
    existing_tvdb, existing_tmdb, existing_imdb = sonarr.get_existing_series()

    added = 0
    skipped_existing = 0
    skipped_no_id = 0
    failed = 0
    total = len(shows)

    print()
    for index, item in enumerate(shows):
        title = getattr(item, 'title', 'unknown')
        year = getattr(item, 'year', '')
        label = title + ((' (' + str(year) + ')') if year else '')
        prefix = '[' + str(index + 1) + '/' + str(total) + '] '

        item = plex.library.enrich_for_arr_import(item)
        if item is None:
            ui_print(prefix + 'failed (metadata): ' + label)
            failed += 1
            continue

        ids = _parse_plex_eids(item)
        tvdb_id = int(ids['tvdb']) if ids['tvdb'] and str(ids['tvdb']).isdigit() else None
        tmdb_id = int(ids['tmdb']) if ids['tmdb'] and str(ids['tmdb']).isdigit() else None
        imdb_id = ids['imdb']

        if not tvdb_id and not tmdb_id and not imdb_id:
            ui_print(prefix + 'skip (no id): ' + label)
            skipped_no_id += 1
            continue

        if tvdb_id and tvdb_id in existing_tvdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue
        if tmdb_id and tmdb_id in existing_tmdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue
        if imdb_id and str(imdb_id).lower() in existing_imdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue

        lookup = sonarr.lookup_series(tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id)
        if lookup is None:
            ui_print(prefix + 'failed (lookup): ' + label)
            failed += 1
            continue

        lookup_tvdb = getattr(lookup, 'tvdbId', None)
        lookup_tmdb = getattr(lookup, 'tmdbId', None)
        lookup_imdb = getattr(lookup, 'imdbId', None)
        if lookup_tvdb and int(lookup_tvdb) in existing_tvdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue
        if lookup_tmdb and int(lookup_tmdb) in existing_tmdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue
        if lookup_imdb and str(lookup_imdb).lower() in existing_imdb:
            ui_print(prefix + 'skip (exists): ' + label)
            skipped_existing += 1
            continue

        ok, error = sonarr.add_series(
            lookup,
            quality_profile_id,
            root_path,
            language_profile_id=language_profile_id,
            search=True,
        )
        if ok:
            ui_print(prefix + 'added: ' + label)
            added += 1
            if lookup_tvdb:
                existing_tvdb.add(int(lookup_tvdb))
            if lookup_tmdb:
                existing_tmdb.add(int(lookup_tmdb))
            if lookup_imdb:
                existing_imdb.add(str(lookup_imdb).lower())
        else:
            ui_print(prefix + 'failed: ' + label + ' — ' + str(error))
            failed += 1
        time.sleep(0.25)

    print()
    ui_print('Sonarr import complete.')
    ui_print('  Added:            ' + str(added))
    ui_print('  Skipped existing: ' + str(skipped_existing))
    ui_print('  Skipped no id:    ' + str(skipped_no_id))
    ui_print('  Failed:           ' + str(failed))
    print()
    input('Press Enter to return to the main menu.')

def options():
    current_module = sys.modules[__name__]
    list = [
        option('Run', current_module, 'download_script_run'),
        option('Settings', current_module, 'settings'),
        option('Ignored Media', current_module, 'ignored'),
        option('Scraper', current_module, 'scrape'),
        option('Web Interface', current_module, 'web_interface'),
        option('Repair broken media', current_module, 'repair_broken_media'),
        option('Import Plex library into Radarr', current_module, 'import_plex_to_radarr'),
        option('Import Plex library into Sonarr', current_module, 'import_plex_to_sonarr'),
    ]
    ui_cls('Options/',update=update_available())
    for index, option_ in enumerate(list):
        print(str(index + 1) + ') ' + option_.name)
    print()
    print('Type exit to quit.')
    print()
    choice = input('Choose an action: ')
    if choice == 'exit':
        exit()
    for index, option_ in enumerate(list):
        if choice == str(index + 1):
            option_.input()
    options()

def setup():
    if os.path.exists(config_dir + '/settings.json'):
        if os.path.getsize(config_dir + '/settings.json') > 0 and os.path.isfile(config_dir + '/settings.json'):
            with open(config_dir + '/settings.json', 'r') as f:
                settings = json.loads(f.read())
            if settings['Show Menu on Startup'] == "false" or service_mode == True:
                return False
            load()
            return True
    ui_cls('Initial Setup')
    try:
        input('Press Enter to continue: ')
    except:
        print("Error: It seems this terminal is not interactive! Please make sure to allow user input in this terminal. For docker, add the 'interactive' flag ('-ti').")
        time.sleep(10)
        exit()
    for category, settings in settings_list:
        for setting in settings:
            if setting.required:
                ui_cls('Options/Settings/' + category + '/' + setting.name)
                setting.setup()
    ui_cls('Done!')
    input('Press Enter to continue to the main menu: ')
    save()
    return True

def save(doprint=True):
    save_settings = {}
    for category, settings in settings_list:
        for setting in settings:
            save_settings[setting.name] = setting.get()
    try:
        with open(config_dir + '/settings.json', 'w') as f:
            json.dump(save_settings, f, indent=4)
        if doprint:
            print('Current settings saved!')
            time.sleep(2)
    except Exception as e:
        print(str(e))
        print()
        print("Error: It looks like plex_debrid can not write your settings into a config file. Make sure you are running the script with write or administator privilege.")
        print()
        input("Press enter to exit: ")
        exit()

def load(doprint=False, updated=False):
    with open(config_dir + '/settings.json', 'r') as f:
        settings = json.loads(f.read())
    if 'version' not in settings:
        update(settings, ui_settings.version)
        updated = True
    elif not settings['version'][0] == ui_settings.version[0] and not ui_settings.version[2] == []:
        update(settings, ui_settings.version)
        updated = True
    #compatability code for updating from <2.10 
    if 'Library Service' in settings: 
        settings['Library collection service'] = settings['Library Service']
        if settings['Library Service'] == ["Plex Library"]:
            if 'Plex \"movies\" library' in settings and 'Plex \"shows\" library' in settings: 
                settings['Plex library refresh'] = [settings['Plex \"movies\" library'],settings['Plex \"shows\" library']]
            settings['Library update services'] = ["Plex Libraries"]
        elif settings['Library Service'] == ["Trakt Collection"]:
            settings['Library update services'] = ["Trakt Collection"]
            settings['Trakt refresh user'] = settings['Trakt library user']
    #compatability code for updating from <2.20
    if not 'Library ignore services' in settings: 
        if settings['Library collection service'] == ["Plex Library"]:
            settings['Library ignore services'] = ["Plex Discover Watch Status"]
            settings["Plex ignore user"] = settings["Plex users"][0][0]
        elif settings['Library collection service'] == ["Trakt Collection"]:
            settings['Library ignore services'] = ["Trakt Watch Status"]
            settings["Trakt ignore user"] = settings["Trakt users"][0]
    for category, load_settings in settings_list:
        for setting in load_settings:
            if setting.name in settings and not setting.name == 'version' and not setting.name == 'Content Services':
                setting.set(settings[setting.name])
    if doprint:
        print('Last settings loaded!')
        time.sleep(2)
    save(doprint=updated)

def preflight():
    missing = []
    for category, settings in settings_list:
        for setting in settings:
            if setting.preflight:
                if usenet.is_enabled() and setting.name == 'Debrid Services':
                    continue
                if len(setting.get()) == 0:
                    missing += [setting]
    if len(missing) > 0:
        print()
        print('Looks like your current settings didnt pass preflight checks. Please edit the following setting/s: ')
        for setting in missing:
            print(setting.name + ': Please add at least one ' + setting.entry + '.')
        print()
        input('Press Enter to return to the main menu: ')
        return False
    
    
    return True

def run(cdir = "", smode = False):
    global config_dir
    global service_mode
    config_dir = cdir
    service_mode = smode
    set_log_dir(config_dir)
    if setup():
        #uvicorn.run("webui:app", port=8008, reload=True)
        options()
    else:
        load()
        #uvicorn.run("webui:app", port=8008, reload=True)
        download_script_run()
        options()

def update_available():
    try:
        response = requests.get('https://raw.githubusercontent.com/elfhosted/plex_debrid/main/ui/ui_settings.py',timeout=0.25)
        response = response.content.decode()
        match = regex.search(r"(?<=')([0-9]+\.[0-9]+)(?=')", response)
        if match:
            v = match.group()
            # Split the version strings into major and minor parts.
            cur_major, cur_minor = map(int, ui_settings.version[0].split('.'))
            pub_major, pub_minor = map(int, v.split('.'))

            if pub_major > cur_major or (pub_major == cur_major and pub_minor > cur_minor):
                return " | [v"+v+"] available!"
            return ""
        return ""
    except:
        return ""

def update(settings, version):
    ui_cls('/Update ' + version[0] + '/')
    print('There has been an update to plex_debrid, which is not compatible with your current settings:')
    print()
    print(version[1])
    print()
    print('This update will overwrite the following setting/s: ' + str(version[2]))
    print('A backup file (old.json) with your old settings will be created.')
    print()
    input('Press Enter to update your settings:')
    with open(config_dir + "/old.json", "w+") as f:
        json.dump(settings, f, indent=4)
    for category, load_settings in settings_list:
        for setting in load_settings:
            for setting_name in version[2]:
                if setting.name == setting_name:
                    settings[setting.name] = setting.get()
                elif setting.name == 'version':
                    settings[setting.name] = setting.get()

def unique(lst):
    unique_objects = []
    for obj in lst:
        is_unique = True
        for unique_obj in unique_objects:
            if unique_obj == obj:
                is_unique = False
                # If we find a duplicate, merge attributes and preserve watchlist information
                if not hasattr(unique_obj, '_all_watchlists'):
                    # Only add watchlist if the object has one
                    if hasattr(unique_obj, 'watchlist'):
                        unique_obj._all_watchlists = [unique_obj.watchlist]
                    else:
                        unique_obj._all_watchlists = []
                if hasattr(obj, 'watchlist') and obj.watchlist not in unique_obj._all_watchlists:
                    unique_obj._all_watchlists.append(obj.watchlist)
                
                # Merge attributes from the duplicate object
                for attr_name in dir(obj):
                    if not attr_name.startswith('_') and not callable(getattr(obj, attr_name)):
                        if not hasattr(unique_obj, attr_name):
                            # Copy attribute if unique_obj doesn't have it
                            setattr(unique_obj, attr_name, getattr(obj, attr_name))
                        elif attr_name == 'user' and hasattr(obj, 'user') and hasattr(unique_obj, 'user'):
                            # Special handling for user attribute - merge user lists
                            # Ensure both are lists for consistent structure
                            if not isinstance(unique_obj.user, list):
                                unique_obj.user = [unique_obj.user]
                            if not isinstance(obj.user, list):
                                obj.user = [obj.user]
                            
                            # Merge the user lists, but be careful about structure
                            for user in obj.user:
                                # Only add if it's a proper user tuple/list and not already present
                                if (isinstance(user, (list, tuple)) and len(user) >= 2 and 
                                    user not in unique_obj.user):
                                    unique_obj.user.append(user)
                break
        if is_unique:
            # Initialize the _all_watchlists attribute for new unique objects
            if hasattr(obj, 'watchlist'):
                obj._all_watchlists = [obj.watchlist]
            else:
                obj._all_watchlists = []
            unique_objects.append(obj)
    return unique_objects

def cleanup_watchlist_items(plex_watchlist, library):
    """Remove films (released in digital/physical) and ended or fully-collected shows from Plex watchlist after threshold days."""
    try:
        threshold = int(getattr(ui_settings, 'watchlist_cleanup_days', 30))
    except (TypeError, ValueError):
        threshold = 30
    dry_run = str(getattr(ui_settings, 'watchlist_cleanup_dry_run', 'false')).lower() == 'true'
    if threshold <= 0:
        ui_print('[plex cleanup] disabled (threshold <= 0)', debug=ui_settings.debug)
        return
    now = datetime.datetime.utcnow()
    plex_service = content.services.plex.watchlist
    items_to_remove = []
    considered = 0

    def _item_label(it):
        s = getattr(it, 'title', None)
        if s is not None:
            return s
        try:
            return it.query()
        except Exception:
            return getattr(it, 'ratingKey', 'unknown') or 'unknown'

    def _parse_watchlisted_dt(value):
        if isinstance(value, (int, float)):
            return datetime.datetime.utcfromtimestamp(float(value))
        if isinstance(value, str):
            try:
                return datetime.datetime.strptime(value[:10], '%Y-%m-%d')
            except ValueError:
                return datetime.datetime.fromtimestamp(
                    content.services.plex._normalize_watchlisted_at(value),
                    tz=datetime.timezone.utc,
                ).replace(tzinfo=None)
        return None

    def _get_item_plex_token(it):
        user_attr = getattr(it, 'user', None)
        if isinstance(user_attr, list) and len(user_attr) > 0:
            if isinstance(user_attr[0], list) and len(user_attr[0]) > 1:
                return user_attr[0][1]
            if len(user_attr) > 1 and isinstance(user_attr[1], str):
                return user_attr[1]
        users = getattr(content.services.plex, 'users', [])
        return users[0][1] if users else None

    for item in list(plex_watchlist.data):
        if not hasattr(item, 'watchlist') or item.watchlist != plex_service:
            continue
        if not hasattr(item, 'type') or item.type not in ('movie', 'show'):
            continue
        watchlisted_at = getattr(item, 'watchlistedAt', None) or getattr(item, 'addedAt', None)
        if watchlisted_at is None or (isinstance(watchlisted_at, (int, float)) and watchlisted_at <= 0):
            ui_print(f'[plex cleanup] skip "{_item_label(item)}": no watchlistedAt', debug=ui_settings.debug)
            continue
        try:
            added_dt = _parse_watchlisted_dt(watchlisted_at)
            if added_dt is None:
                continue
        except (ValueError, OSError, TypeError):
            ui_print(f'[plex cleanup] skip "{_item_label(item)}": invalid watchlistedAt', debug=ui_settings.debug)
            continue
        stale_days = content.services.plex._watchlist_date_stale_days()
        if (now - added_dt).days > stale_days:
            token = _get_item_plex_token(item)
            refreshed = None
            if token and getattr(item, 'ratingKey', None):
                refreshed = content.services.plex.get_watchlist_activity_added_at(item.ratingKey, token)
            if refreshed is not None:
                item.watchlistedAt = refreshed
                try:
                    added_dt = datetime.datetime.utcfromtimestamp(float(refreshed))
                    ui_print(f'[plex cleanup] refreshed "{_item_label(item)}" watchlist date from activity feed', debug=ui_settings.debug)
                except (ValueError, OSError, TypeError):
                    ui_print(f'[plex cleanup] skip "{_item_label(item)}": invalid activity-feed watchlist date', debug=ui_settings.debug)
                    continue
            if (now - added_dt).days > stale_days:
                ui_print(f'[plex cleanup] skip "{_item_label(item)}": watchlist date too old (>{stale_days}d, likely wrong)', debug=ui_settings.debug)
                continue
        days_in_watchlist = (now - added_dt).days
        if days_in_watchlist < threshold:
            continue
        # Least-intrusive safeguard: before removal decisions, re-check watchlist date from activity feed.
        token = _get_item_plex_token(item)
        if token and getattr(item, 'ratingKey', None):
            refreshed = content.services.plex.get_watchlist_activity_added_at(item.ratingKey, token)
            if refreshed is not None:
                current_ts = content.services.plex._normalize_watchlisted_at(watchlisted_at)
                if refreshed != current_ts:
                    item.watchlistedAt = refreshed
                    try:
                        added_dt = datetime.datetime.utcfromtimestamp(float(refreshed))
                        days_in_watchlist = (now - added_dt).days
                        ui_print(
                            f'[plex cleanup] refreshed "{_item_label(item)}" watchlist date before removal: '
                            f'{current_ts} -> {refreshed} ({days_in_watchlist}d in list)',
                            debug=ui_settings.debug
                        )
                    except (ValueError, OSError, TypeError):
                        ui_print(f'[plex cleanup] skip "{_item_label(item)}": invalid pre-removal activity-feed date', debug=ui_settings.debug)
                        continue
                    if days_in_watchlist < threshold:
                        ui_print(f'[plex cleanup] skip "{_item_label(item)}": refreshed watchlist date now below threshold ({days_in_watchlist}d < {threshold}d)', debug=ui_settings.debug)
                        continue
        considered += 1
        if item.type == 'movie':
            try:
                if hasattr(content.services, 'trakt') and len(getattr(content.services.trakt, 'users', [])) > 0:
                    content.services.trakt.current_user = content.services.trakt.users[0]
                    item.match('content.services.trakt')
                if item.available():
                    in_library = item.collected(library) if hasattr(item, 'collected') and library else False
                    items_to_remove.append((item, 'movie_released'))
                    ui_print(f'[plex cleanup] will remove movie "{_item_label(item)}" ({getattr(item, "year", "")}) (released, in_library={in_library}, {days_in_watchlist}d in list)', debug=ui_settings.debug)
                else:
                    ui_print(f'[plex cleanup] skip movie "{_item_label(item)}": not available (released)', debug=ui_settings.debug)
            except Exception as e:
                ui_print(f'[plex cleanup] skip movie "{_item_label(item)}": {e}', debug=ui_settings.debug)
        elif item.type == 'show':
            try:
                has_ended = item.hasended()
                is_collected = item.collected(library) if hasattr(item, 'collected') and library else False
                inactivity_days = sqlite_store.get_show_inactivity_days(item)
                no_progress_too_long = inactivity_days is not None and inactivity_days >= threshold
                # Remove if show ended AND fully collected, OR if no collection progress for threshold days.
                if (has_ended and is_collected) or no_progress_too_long:
                    reason = 'show_ended_and_collected' if (has_ended and is_collected) else f'show_no_progress_{inactivity_days}d'
                    items_to_remove.append((item, reason))
                    ui_print(
                        f'[plex cleanup] will remove show "{_item_label(item)}" ({getattr(item, "year", "")}) '
                        f'(status={getattr(item, "status", "?")}, isContinuingSeries={getattr(item, "isContinuingSeries", "?")}, '
                        f'hasended={has_ended}, collected={is_collected}, inactivity_days={inactivity_days}, {days_in_watchlist}d in list)',
                        debug=ui_settings.debug
                    )
                else:
                    ui_print(
                        f'[plex cleanup] skip show "{_item_label(item)}": hasended={has_ended} '
                        f'(status={getattr(item, "status", "?")}, isContinuingSeries={getattr(item, "isContinuingSeries", "?")}), '
                        f'collected={is_collected}, inactivity_days={inactivity_days}',
                        debug=ui_settings.debug
                    )
            except Exception as e:
                ui_print(f'[plex cleanup] skip show "{_item_label(item)}": {e}', debug=ui_settings.debug)
    ui_print(f'[plex cleanup] run: threshold={threshold}d, dry_run={dry_run}, {len(plex_watchlist.data)} Plex items, {considered} eligible (>={threshold}d), removing {len(items_to_remove)}')
    ui_print(f'[plex cleanup] considered {considered} items (>={threshold}d), removing {len(items_to_remove)}', debug=ui_settings.debug)
    for item, reason in items_to_remove:
        try:
            if dry_run:
                ui_print(f'[plex cleanup] dry-run: would remove "{_item_label(item)}" ({getattr(item, "year", "")}) from watchlist (reason={reason}, >={threshold}d in list)')
                continue
            plex_watchlist.remove(item)
            ui_print(f'[plex cleanup] removed "{_item_label(item)}" ({getattr(item, "year", "")}) from watchlist (reason={reason}, >={threshold}d in list)')
            # Clear ignore flag so re-adding later gets a fresh download attempt (may be available now)
            try:
                if hasattr(item, 'unwatch'):
                    item.unwatch()
                # For shows, also clear ignore on all episodes so each gets a fresh attempt when re-added
                if getattr(item, 'type', None) == 'show' and hasattr(item, 'Seasons'):
                    for season in item.Seasons or []:
                        for episode in getattr(season, 'Episodes', []) or []:
                            try:
                                if hasattr(episode, 'unwatch'):
                                    episode.unwatch()
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception as e:
            ui_print(f'[plex cleanup] error removing {_item_label(item)}: {e}', debug=ui_settings.debug)

def threaded(stop):
    ui_cls()
    if service_mode == True:
        print("Running in service mode, user input not supported.")
    else:
        print("Type 'exit' to return to the main menu.")
    timeout = 5
    regular_check = int(ui_settings.loop_interval_seconds)
    last_full_run_start = 0  # 0 so first full run can start when condition is first checked
    try:
        cleanup_threshold = int(getattr(ui_settings, 'watchlist_cleanup_days', 30))
    except (TypeError, ValueError):
        cleanup_threshold = 30
    cleanup_dry_run = str(getattr(ui_settings, 'watchlist_cleanup_dry_run', 'false')).lower() == 'true'
    stale_days = content.services.plex._watchlist_date_stale_days()
    first_seen_days = content.services.plex._watchlist_first_seen_activity_check_days()
    ui_print(
        f'[startup] cleanup settings: threshold_days={cleanup_threshold}, dry_run={cleanup_dry_run}, '
        f'stale_days={stale_days}, first_seen_activity_check_days={first_seen_days}'
    )
    library = content.classes.library()[0]()
    # refresh Real-Debrid cache on startup
    if debrid.services.realdebrid.cache.should_refresh():
        ui_print('refreshing Real-Debrid cache...')
        debrid.services.realdebrid.cache.sync_torrents()
    # get entire plex_watchlist
    plex_watchlist = content.services.plex.watchlist()
    # get entire trakt_watchlist
    trakt_watchlist = content.services.trakt.watchlist()
    # get all overseerr request
    overseerr_requests = content.services.overseerr.requests()
    # get local sqlite requests
    sqlite_requests = content.services.sqlite.watchlist()
    # combine all content, sort by newest
    watchlists = plex_watchlist + trakt_watchlist + overseerr_requests + sqlite_requests
    try:
        watchlists.data.sort(key=lambda s: s.watchlistedAt,reverse=True)
    except:
        ui_print("couldnt sort monitored media by newest, using default order.", ui_settings.debug)
    if len(library) > 0:
        ui_print('checking new content ...')
        t0 = time.time()
        for element in unique(watchlists):
            if hasattr(element, 'download'):
                # Skip if media item is blacklisted
                if sqlite_store.is_media_blacklisted(element):
                    ui_print(f"skipping blacklisted item: {element.query()}", ui_settings.debug)
                    continue
                element.download(library=library, plex_watchlist=plex_watchlist, trakt_watchlist=trakt_watchlist, overseerr_requests=overseerr_requests, sqlite_requests=sqlite_requests)
                t1 = time.time()
                #if more than 5 seconds have passed, check for newly watchlisted content
                if t1-t0 >= 5:
                    if plex_watchlist.update() or overseerr_requests.update() or trakt_watchlist.update() or sqlite_requests.update():
                        library = content.classes.library()[0]()
                        if len(library) == 0:
                            continue
                        new_watchlists = plex_watchlist + trakt_watchlist + overseerr_requests + sqlite_requests
                        try:
                            new_watchlists.data.sort(key=lambda s: s.watchlistedAt,reverse=True)
                        except:
                            ui_print("couldnt sort monitored media by newest, using default order.", ui_settings.debug)
                        new_watchlists = unique(new_watchlists)
                        for element in new_watchlists[:]:
                            if element in watchlists:
                                new_watchlists.remove(element)
                        ui_print('checking new content ...')
                        for element in new_watchlists:
                            if hasattr(element, 'download'):
                                # Skip if media item is blacklisted
                                if sqlite_store.is_media_blacklisted(element):
                                    ui_print(f"skipping blacklisted item: {element.query()}", ui_settings.debug)
                                    continue
                                element.download(library=library, plex_watchlist=plex_watchlist, trakt_watchlist=trakt_watchlist, overseerr_requests=overseerr_requests, sqlite_requests=sqlite_requests)
                        ui_print('done')
                    t0 = time.time()
        ui_print('done')
    while not stop():
        if plex_watchlist.update() or overseerr_requests.update() or trakt_watchlist.update() or sqlite_requests.update():
            library = content.classes.library()[0]()
            watchlists = plex_watchlist + trakt_watchlist + overseerr_requests + sqlite_requests
            try:
                watchlists.data.sort(key=lambda s: s.watchlistedAt,reverse=True)
            except:
                ui_print("couldnt sort monitored media by newest, using default order.", ui_settings.debug)
            ui_print('checking new content ...')
            for element in unique(watchlists):
                if hasattr(element, 'download'):
                    # Skip if media item is blacklisted
                    if sqlite_store.is_media_blacklisted(element):
                        ui_print(f"skipping blacklisted item: {element.query()}", ui_settings.debug)
                        continue
                    # Skip items in retry queue so retries run on full runs only (loop_interval apart)
                    if element in content.classes.media.ignore_queue:
                        continue
                    newly_added = True
                    if element.type == "show":
                        if hasattr(element, "Seasons"):
                            for season in element.Seasons:
                                # Skip if season is blacklisted
                                if sqlite_store.is_media_blacklisted(season):
                                    ui_print(f"skipping blacklisted season: {season.query()}", ui_settings.debug)
                                    newly_added = False
                                    break
                                if season in content.classes.media.ignore_queue or not newly_added:
                                    newly_added = False
                                    break
                                for episode in season.Episodes:
                                    # Skip if episode is blacklisted
                                    if sqlite_store.is_media_blacklisted(episode):
                                        ui_print(f"skipping blacklisted episode: {episode.query()}", ui_settings.debug)
                                        newly_added = False
                                        break
                                    if episode in content.classes.media.ignore_queue:
                                        newly_added = False
                                        break
                    if newly_added:
                        element.download(library=library, plex_watchlist=plex_watchlist, trakt_watchlist=trakt_watchlist, overseerr_requests=overseerr_requests, sqlite_requests=sqlite_requests)
            ui_print('done')
        elif (time.time() - last_full_run_start) >= regular_check:
            last_full_run_start = time.time()
            # refresh Real-Debrid cache if needed
            if debrid.services.realdebrid.cache.should_refresh():
                ui_print('refreshing Real-Debrid cache...')
                debrid.services.realdebrid.cache.sync_torrents()
            # get entire plex_watchlist
            plex_watchlist = content.services.plex.watchlist()
            # get entire trakt_watchlist
            trakt_watchlist = content.services.trakt.watchlist()
            # get all overseerr request, match content to plex media type and add to monitored list
            overseerr_requests = content.services.overseerr.requests()
            # get local sqlite requests
            sqlite_requests = content.services.sqlite.watchlist()
            # combine all content; sort so continuing shows are checked first, then by newest
            # Loop interval = minimum time between full-run *starts* (includes run duration).
            # If run takes 5h and interval is 6h, wait 1h after run. If run takes 7h, start next run immediately.
            watchlists = plex_watchlist + trakt_watchlist + overseerr_requests + sqlite_requests
            try:
                def _full_run_sort_key(s):
                    continuing = getattr(s, 'type', None) == 'show' and not getattr(s, 'hasended', lambda: True)()
                    return (0 if continuing else 1, -(getattr(s, 'watchlistedAt', 0) or 0))
                watchlists.data.sort(key=_full_run_sort_key)
            except Exception:
                try:
                    watchlists.data.sort(key=lambda s: s.watchlistedAt, reverse=True)
                except Exception:
                    ui_print("couldnt sort monitored media, using default order.", ui_settings.debug)
            library = content.classes.library()[0]()

            # Auto-cleanup: remove released films and ended shows from Plex watchlist after threshold days
            cleanup_watchlist_items(plex_watchlist, library)
            if str(getattr(ui_settings, 'auto_repair_broken_media_after_cleanup', 'false')).lower() == 'true':
                ui_print('running non-interactive repair broken media ...')
                repair_broken_media(non_interactive=True)
            
            # Update database with current collected status for entire library
            ui_print('updating database status ...')
            try:
                # Update all library items (items that exist in the library)
                library_updated = 0
                for item in library:
                    try:
                        # Library items are considered "collected" by definition
                        # We'll update them with source based on the library service
                        library_source = 'plex'  # Default, could be enhanced to detect actual source
                        if hasattr(library, '__module__'):
                            if 'trakt' in library.__module__:
                                library_source = 'trakt'
                            elif 'jellyfin' in library.__module__:
                                library_source = 'jellyfin'
                        
                        sqlite_store.update_db(item, library, source=library_source)
                        library_updated += 1
                    except Exception as e:
                        ui_print(f"error updating library item {getattr(item, 'title', 'unknown')}: {str(e)}", debug=ui_settings.debug)
                        continue
                
                # Also update watchlisted items (they may not be in library yet)
                watchlist_updated = 0
                for item in unique(watchlists):
                    if hasattr(item, 'download'):
                        # Determine source
                        source = 'plex'  # Default
                        if hasattr(item, 'watchlist') and hasattr(item.watchlist, '__module__'):
                            source = item.watchlist.__module__.split('.')[-1]
                        # Update database with current status
                        sqlite_store.update_db(item, library, source=source)
                        watchlist_updated += 1
                
                ui_print(f'done - updated {library_updated} library items, {watchlist_updated} watchlist items')
            except Exception as e:
                ui_print(f"error updating database status: {str(e)}", debug=ui_settings.debug)
            
            ui_print('checking new content ...')
            t0 = time.time()
            for element in unique(watchlists):
                if hasattr(element, 'download'):
                    # Skip if media item is blacklisted
                    if sqlite_store.is_media_blacklisted(element):
                        ui_print(f"skipping blacklisted item: {element.query()}", ui_settings.debug)
                        continue
                    element.download(library=library, plex_watchlist=plex_watchlist, trakt_watchlist=trakt_watchlist, overseerr_requests=overseerr_requests, sqlite_requests=sqlite_requests)
                    t1 = time.time()
                    #if more than 5 seconds have passed, check for newly watchlisted content
                    if t1-t0 >= 5:
                        if plex_watchlist.update() or overseerr_requests.update() or trakt_watchlist.update() or sqlite_requests.update():
                            library = content.classes.library()[0]()
                            if len(library) == 0:
                                continue
                            new_watchlists = plex_watchlist + trakt_watchlist + overseerr_requests + sqlite_requests
                            try:
                                new_watchlists.data.sort(key=lambda s: s.watchlistedAt,reverse=True)
                            except:
                                ui_print("couldnt sort monitored media by newest, using default order.", ui_settings.debug)
                            new_watchlists = unique(new_watchlists)
                            for element in new_watchlists[:]:
                                if element in watchlists:
                                    new_watchlists.remove(element)
                            ui_print('checking new content ...')
                            for element in new_watchlists:
                                if hasattr(element, 'download'):
                                    # Skip if media item is blacklisted
                                    if sqlite_store.is_media_blacklisted(element):
                                        ui_print(f"skipping blacklisted item: {element.query()}", ui_settings.debug)
                                        continue
                                    element.download(library=library, plex_watchlist=plex_watchlist, trakt_watchlist=trakt_watchlist, overseerr_requests=overseerr_requests, sqlite_requests=sqlite_requests)
                            ui_print('done')
                        t0 = time.time()
            ui_print('done')
        time.sleep(timeout)

def download_script_run():
    if preflight():
        global stop
        stop = False
        t = Thread(target=threaded, args=(lambda: stop,))
        t.start()
        if service_mode == True:
            print("Running in service mode, user input not supported.")
        else:
            while not stop:
                text = input("")
                if text == 'exit':
                    stop = True
                else:
                    print("Type 'exit' to return to the main menu.")
        print("Waiting for the download automation to stop ... ")
        while t.is_alive():
            time.sleep(1)
