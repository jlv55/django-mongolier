#!/usr/bin/env python
import warnings
##
# django-mongolier
##
__title__ = 'mongolier'
__version__ = '0.1.2'
__author__ = 'Jason Bartz & Jeremy Bowers'
__license__ = 'MIT'
__author_email__ = ['bartzj@washpost.com', 'bowersj@washpost.com']

try:
    from mongolier.db import MongoConnection, PersistentConnection, Connection
    from mongolier.utils.convert import ConvertDecimal
except ImportError, e:
    warnings.warn(e)
