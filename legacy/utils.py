from config import Config

def verbose_print(*args, **kwargs):
    if Config.is_verbose():
        print(*args, **kwargs)