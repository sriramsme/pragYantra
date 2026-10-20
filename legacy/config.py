import os

class Config:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.verbose = os.environ.get('VERBOSE', 'false').lower() == 'true'
        return cls._instance

    @classmethod
    def set_verbose(cls, verbose):
        cls().verbose = verbose

    @classmethod
    def is_verbose(cls):
        return cls().verbose