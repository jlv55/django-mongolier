"""
db.py

A class for connecting to a MongoDB instance
"""
import time
import pymongo
from pymongo.errors import (AutoReconnect,
                            ConnectionFailure,
                            OperationFailure)
from mongolier.exceptions import InvalidMode, DoesNotExist
from gridfs import GridFS


class BaseConnection(object):
    """
    The base methods used for all connection objects
    """
    def __init__(self,
                host='localhost',
                port=27017,
                db='test',
                collection='test',
                username=None,
                password=None,
                max_retries=2,
                override=False,
                **options):
        """
        Instantiate the Mongo class

        This can take optional arguments, all of which help
            connect to the right database

        """
        #: The port that the MongoDB connection lives on
        self.port = port

        #: The host or IP address to connect to
        self.host = host

        #: The name of the database
        self.db = db

        #: The name of the collection
        self.collection = collection

        #: The database username
        self.username = username

        #: The database password
        self.password = password

        #: The number of retries to attempt to reconnect after a connection
        #: is dropped.
        self.max_retries = max_retries

        #: Additional options to pass into the pymongo connection
        self.options = options

        #: Determines whether to permanently override default collection object
        #: on generic connections
        self.override = override

        # To prevent incidental recursion
        self._mode = None

    def __getattribute__(self, attribute):
        """
        Custom attribute override to allow a db connection to support multiple connections.

        This is basically replicating the feature of a standard pymongo collection object,
        except with the added benefit of mongolier's options and truncated syntax.

        To use, just pass a collection as an attribute to a mongolier Connection obj

        ::

            my_connection_obj = Connection(db='my_db')
            my_connection_obj.my_collection.find_one()

        This will override any collection passed into the instantiation of the class,
        but only for that method call.  It does not override the Connection's collection
        attribute.

        Note: You cannot name a collection the same as an attribute on the Connection
        object. If you do that, use item access instead.

        """
        try:
            return(super(BaseConnection, self).__getattribute__(attribute))
        except AttributeError:
            return(self._generic_connection(attribute))

    def __getitem__(self, item):
        """
        Same purpose as ``<meth::__getattribute__>__getattribute__``, except via
        item indexing.

        ::

            my_connection_obj = Connection(db='my_db')
            my_connection_obj['my_collection'].find_one()

        is the same as:

        ::

            my_connection_obj = Connection(db='my_db', collection='my_collection')
            my_connection_obj.api.find_one()


        """
        return(self._generic_connection(item))

    def _generic_connection(self, collection):
        """
        A method to handle generic connections created via __getattribute__ and
        __getitem__.
        """
        self._mode = 'api'
        if self.override:
            self.collection = collection

        return(self._connect(collection=collection))

    def _connect_to_db(self, retries=0):
        """
        Connect to the database, but do not initialize a connection.

        Depending on which public method is used, it initiates either a standard
            mongo connection or a gridfs connection
        """
        retries = retries

        try:
            # Establish a Connection
            connection = pymongo.Connection(self.host, self.port, **self.options)

            # Establish a database
            database = connection[self.db]

            # If user passed username and password args, give that to authenticate
            if self.username and self.password:
                database.authenticate(self.username, self.password)

        # Handle the following exceptions, if retries is less than what is
        # passed into this method, attempt to connect again.  Otherwise,
        # raise the proper exception.
        except AutoReconnect as error_message:
            time.sleep(2)
            retries += 1

            if retries <= self.max_retries:
                self._connect_to_db(retries=retries)
            else:
                raise ConnectionFailure('Max number of retries (%s) reached. Error: %s'\
                                         % (self.max_retries, error_message))

        except OperationFailure as error_message:
            time.sleep(2)
            retries += 1

            if retries <= self.max_retries:
                self._connect_to_db(retries=retries)
            else:
                raise OperationFailure('Max number of retries (%s) reached. Error: %s'\
                                         % (self.max_retries, error_message))

        return database

    def _check_mode(self, mode):
        """
        Check mode is a failsafe designed to prevent bad operations from happening.

        Because pymongo (and MongoDB) can be finnicky when using a standard query
        to access a gridfs collection and visa versa, we put in a check that once
        a connection is made, it can only be that type of connection.
        """
        if not self._mode:
            raise DoesNotExist("The mode does not exist, most likely because this\
                                was subclassed improperly.")
        if mode is not self._mode:
            raise InvalidMode(".The mode set does not match the mode requested. \n\
                                This connection object already used %s" % mode)

    def _connect(self, collection=None):
        """
        Connect to the mongo instance
        """
        self._check_mode('api')

        database = self._connect_to_db()

        if not collection:
            collection = self.collection

        collection = database[collection]

        return collection

    def _gridfs(self):
        """
        A module to connect to GridFS and chunk large files for saving into mongo
        """
        self._check_mode('gridfs')

        database = self._connect_to_db()

        grid = GridFS(database, collection=self.collection)

        return grid


class Connection(BaseConnection):
    """
    A wrapper for MongoConnection that stores a persistent set of connection information

    Import PersistentConnection from mongolier, and pass in the proper kwargs.

    ::

        my_connection = Connection(**{
            "database": "my_db",
            "collection": "my_collection",
            "port": 27017,
            "username": "my_login"
            "password": "my_pass",
            "retries": 5,
        })


    Inside your module, just pull in that connection and query against its api.

    ::

        from django.db.settings import my_connection
        my_connection.api.find_one({"query_param": "value"})

    For GridFS, use the gridfs API.

    >>> my_connection.gridfs.get_last_version(**{"query_param": "value"})
    """

    @property
    def api(self):
        self._mode = 'api'
        return(self._connect())

    @property
    def fs(self):
        self._mode = 'gridfs'
        return(self._gridfs())
