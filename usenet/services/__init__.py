from base import *
from usenet.services import prowlarr

active = []


def __subclasses__():
    return [prowlarr]


def setup(cls, new=False):
    from settings import settings_list
    global active
    settings = []
    for category, allsettings in settings_list:
        for setting in allsettings:
            if setting.cls == cls:
                settings += [setting]
    if settings == []:
        if cls.name not in active:
            active += [cls.name]
    back = False
    if not new:
        while not back:
            print()
            print("0) Back")
            indices = []
            for index, setting in enumerate(settings):
                print(str(index + 1) + ') ' + setting.name)
                indices += [str(index + 1)]
            print()
            if settings == []:
                print("Nothing to edit!")
                print()
                time.sleep(3)
                return
            choice = input("Choose an action: ")
            if choice in indices:
                settings[int(choice) - 1].setup()
                if cls.name not in active:
                    active += [cls.name]
                back = True
            elif choice == '0':
                back = True
    else:
        print()
        for setting in settings:
            setting.setup()
            if cls.name not in active:
                active += [cls.name]


def get():
    cls = sys.modules[__name__]
    activeservices = []
    for servicename in active:
        for service in cls.__subclasses__():
            if service.name == servicename:
                activeservices += [service]
    return activeservices
