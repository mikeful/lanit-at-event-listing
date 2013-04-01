# coding=utf-8
import re

def is_valid_secret_key(secret_key='', allowed_characters=''):
    """
    Return True if string holds only valid secret key characters
    >>> allowed='abcdefghkpqrstuxyz23456789'
    >>> is_valid_secret_key()
    False
    >>> is_valid_secret_key('', allowed)
    False
    >>> is_valid_secret_key('abc', allowed)
    True
    >>> is_valid_secret_key('123', allowed)
    False
    >>> is_valid_secret_key('234', allowed)
    True
    """
    # Check parameters
    if not secret_key or not allowed_characters:
        return False

    return None != re.match('^[%s]+$' % allowed_characters, secret_key)


def is_valid_short_name(short_name=''):
    """
    Return True if string holds only valid short name characters
    >>> is_valid_short_name()
    False
    >>> is_valid_short_name('')
    False
    >>> is_valid_short_name(' ')
    False
    >>> is_valid_short_name('abc')
    True
    >>> is_valid_short_name('a')
    True
    >>> is_valid_short_name('a_')
    True
    >>> is_valid_short_name('123')
    True
    >>> is_valid_short_name('abc_')
    True
    """
    return None != re.match('^[a-z0-9_]+$', short_name)


def _test():
    import doctest

    doctest.testmod()


if __name__ == '__main__':
    _test()