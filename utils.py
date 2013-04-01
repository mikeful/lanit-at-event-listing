# coding=utf-8
import requests
import urlparse

from BeautifulSoup import BeautifulSoup

import datetime
from dateutil import parser as date_parser
import time

def validate_url(url=''):
    """
    Check that URL exists and return final resolved URL or False

    >>> validate_url()
    False
    >>> validate_url('')
    False
    >>> validate_url('http://www.google.fi')
    u'http://www.google.fi/'
    >>> validate_url('http://www.google')
    False
    >>> validate_url('http://urly.fi/xD')
    u'http://www.myfacewhen.com/46/'
    """

    # Check that URL is not empty
    if not url:
        return False

    # Parse URL
    parsed_url = urlparse.urlparse(url).geturl()

    # Request URL
    try:
        result = requests.request('GET', parsed_url)

        # Raise exception based on HTTP error code
        result.raise_for_status()
    except:
        return False

    # Return final resolved URL
    return result.url


def generate_secret_key(length=5, allowed_characters=''):
    """
    Copy-paste'd from https://github.com/django-extensions/django-extensions/blob/master/django_extensions/management/commands/generate_secret_key.py
    """
    return ''.join([choice(allowed_characters) for i in range(length)])


def strip_tags(content=''):
    """
    Parse content as HTML and return without tags

    >>> strip_tags('')
    ''
    >>> strip_tags(u'hello')
    u'hello'
    >>> strip_tags(u'he<b>llo</b>')
    u'hello'
    """
    return ''.join(BeautifulSoup(content).findAll(text=True))


def get_current_timestamp():
    """
    Get current time as UNIX-y timestamp
    """
    return datetime_to_seconds(datetime.datetime.now())


def parse_date(date=''):
    """
    Parse string to Python datetime object or False

    >>> parse_date()
    False
    >>> parse_date('')
    False
    >>> parse_date('23.2.1990 23:50')
    datetime.datetime(1990, 2, 23, 23, 50)
    >>> parse_date('23.02.85 23:50')
    datetime.datetime(1985, 2, 23, 23, 50)
    >>> parse_date('3.12.2091')
    datetime.datetime(2091, 12, 3, 0, 0)
    >>> parse_date('03.12.2091')
    datetime.datetime(2091, 12, 3, 0, 0)
    >>> parse_date('23:59').strftime('%H:%M') == '23:59'
    True
    """

    # Check that date string is not empty
    if not date:
        return False

    # Get datetime with dateutil parser
    parsed_date = date_parser.parse(date, dayfirst=True)

    # Return datetime
    return parsed_date


def datetime_to_seconds(time_object=None):
    """
    Converts Python datetime to seconds, expects UTC+2

    >>> datetime_to_seconds(datetime.datetime(1990, 2, 23, 23, 50))
    635809800.0
    >>> datetime_to_seconds(datetime.datetime(2091, 12, 3, 0, 0))
    3847471200.0
    """
    return time.mktime(time_object.timetuple())


def seconds_to_datetime(timestamp=''):
    """
    Converts UNIX timestamp to Python datetime

    >>> seconds_to_datetime(635809800.0)
    datetime.datetime(1990, 2, 23, 23, 50)
    >>> seconds_to_datetime('635809800.0')
    datetime.datetime(1990, 2, 23, 23, 50)
    >>> seconds_to_datetime('635809800')
    datetime.datetime(1990, 2, 23, 23, 50)
    >>> seconds_to_datetime(635809800)
    datetime.datetime(1990, 2, 23, 23, 50)
    """
    return datetime.datetime.fromtimestamp(int(float(timestamp)))


def _test():
    import doctest

    doctest.testmod()


if __name__ == '__main__':
    _test()