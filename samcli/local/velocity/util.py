"""Utility functions that can be used in velocity templates."""

from json import loads, dumps
from urllib2 import quote, unquote
from base64 import b64encode, b64decode
from jsonpath_rw import parse


def escape_javascript(unescaped_str):
    return dumps(unescaped_str)


def parse_json(raw_json):
    return loads(raw_json)


def url_encode(url):
    return quote(url)


def url_decode(url):
    return unquote(url)


def base64_encode(val):
    return b64encode(val)


def base64_decode(val):
    return b64decode(val)


def get_json_path(path, data):
    match_result = [match.value for match in parse(path).find(loads(data))]

    if match_result > 0:
        return match_result[0]

    return None
