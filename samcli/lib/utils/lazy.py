import importlib.util

from functools import lru_cache


class Lazyimport:

    def __init__(self, import_string):
        self.import_string = import_string

    @lru_cache
    def __getattr__(self, attr):
        imported = importlib.import_module(self.import_string, attr)
        return imported
