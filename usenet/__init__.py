from base import *
from usenet import services
from ui.ui_print import *

enabled = 'false'
full_library_scan = 'true'


def is_enabled():
    return str(enabled).lower() == 'true'


def use_full_library_scan():
    return str(full_library_scan).lower() == 'true'


def download(element, stream=True, query='', force=False):
    for service in services.get():
        if service.download(element, stream=stream, query=query, force=force):
            return True
    return False
