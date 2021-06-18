"""

   Shadofer#0001 and Otterlord#3653
   Copyright GPL-3 
   
"""

""" BUILT-IN MODULES """

""" Parsing responses. """
from json import loads
from json.decoder import JSONDecodeError

""" Specifying variable types. """
from typing import Dict, Awaitable

""" Inspecting functions. """
from inspect import getfullargspec

""" Performance reports. """
from time import time

""" Generating unique IDs. """
from uuid import uuid4

""" Better way for using classes. """
from dataclasses import dataclass, field

""" 3RD-PARTY MODULES """

""" The main way of communicating. """
from websockets.exceptions import ConnectionClosed
from websockets.client import WebSocketClientProtocol

""" Production server MongoDB. """
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import OperationFailure

""" LOCAL MODULES """
from opendogeserver.utilities import *
from opendogeserver.constants import *
from opendogeserver.classes import *

@dataclass(frozen=False, eq=False)
class Server():
    """The `Server` class handles all requests/responses."""

    """ The Mongo Database. """
    mdb: Database = None
    
    """ The registered events to callback. """
    events: Dict[str, function] = field(default_factory=dict)
    
    """ Telemetry. """
    total_requests = 0
    ip_requests: Dict[str, int] = field(default_factory=dict)
    
    """ Linking IPs to accounts. """
    wss_accounts: Dict[str, str] = field(default_factory=dict)

    def register(self, callback: Awaitable) -> None:
        """Register an event"""
        event = to_camel_case(callback.__name__)
        if event not in self.events:
            self.events[event] = callback

    async def handle_event(self, wss, data) -> str:
        """Handles an event"""
        try:
            event = data['event']
            assert len(data['event']) > 0
        except:
            return

        if 'ref' not in data.keys():
            data['ref'] = False

        try:
            target: function = self.events[event]

            args = {}
            target_args = getfullargspec(target).args

            for arg, value in data.items():
                arg_to_add = to_snake_case(arg, True)
                if arg_to_add in target_args:
                    """ Preserve event name. """
                    if arg == 'event':
                        arg_to_add = arg
                    args[arg_to_add] = value

            """ Custom arguments to pass manually. """
            if 'wss' in target_args:
                args['wss'] = wss

            if 'ref' in target_args:
                args['ref'] = data['ref']

            """ Check for arguments before calling, the call may not error but some arguments may be empty. """
            args_errored = check_loop_data(args, target_args)

            if args_errored:
                return format_res_err(event, 'FormatError', data['ref'], args_errored, True)
            try:
                return await target(**args)
            except Exception as e:
                """ Create bug report. """
                if IS_LOCAL:
                    print(e)
                else:
                    try:
                        self.mdb.users.insert_one(
                            {f'bug{str(uuid4())}', str(e)})
                    except:
                        print(f'FATAL DATABASE ERROR EXITING: \n{str(e)}')
                        exit()

                return format_res_err(event, 'EventUnknownError', 'Unknown internal server error.', data['ref'], True)
        except KeyError:
            """ Provide the user with the available events, in a seperate key to be able to split them. """
            possible_events = [event for event in self.events.keys()]

            events_response = ''

            for i in range(len(possible_events)):
                ev = possible_events[i]
                events_response = f"{events_response}{ev}|" if i + \
                    1 < len(possible_events) else f"{events_response}{ev}"
            return format_res_err(event, 'EventNotFound', 'This event doesn\'t exist.', data['ref'], True, possibleEvents=events_response)

    async def serve(self, wss: WebSocketClientProtocol, path: str) -> None:
        """Called only by websockets.serve.

Args:
        wss (WebSocketClientProtocol): The websocket client.
        path (str): The path which the client wants to access.
"""

        print(
            f'A traveller has connected. Travellers online: {len(self.wss_accounts)}')

        """ Set to 0 ONLY if the ip doesn't exist since previous IPs are stored even if it disconnects. """
        if wss.remote_address[0] not in self.ip_requests:
            self.ip_requests[wss.remote_address[0]] = 0

        while True:
            try:
                response = await wss.recv()

                """ Prevent malicious intents. """
                if self.ip_requests[wss.remote_address[0]] > IP_RATELIMIT_MAX:
                    continue

                self.ip_requests[wss.remote_address[0]] += 1

                try:
                    data = loads(response)
                except JSONDecodeError:
                    continue

                try:
                    assert isinstance(data, dict)

                    """ Prevent strange values. """
                    for key, item in data.items():
                        assert isinstance(key, str)
                        assert isinstance(item, str)
                except AssertionError:
                    continue

                global current_ref

                """ Remember to return passed reference. """
                if 'ref' in data:
                    current_ref = data['ref']

                result = await self.handle_event(wss, data)

                """ If nothing is returned, skip this call. """
                if not result:
                    continue

                await wss.send(result)

                self.total_requests += 1

                result = loads(result)

                print(
                    f"[{self.total_requests}] {result['originalEvent']}: {result['event']}")

                current_ref = None

            except ConnectionClosed as e:
                """ Don't remove traveller from IP requests, prevent spam. """

                """ Remove a traveller from the linked accounts list, not online anymore. Only for production servers. """
                if wss.remote_address[0] in self.wss_accounts and not IS_LOCAL:
                    del self.wss_accounts[wss.remote_address[0]]

                print(
                    f'A traveller has disconnected. Code: {e.code} | Travellers online: {len(self.wss_accounts)}')

                break


def setup_mongo(mongodb_username: str, mongodb_password: str) -> Database:
    """Sets up the mongo database for production servers.

    Args:
            mongodb_username (str): The username of an authored user of the database.
            mongodb_password (str): The password of the authored user.
    """
    start = time()

    try:
        mdbclient = MongoClient(
            f'mongodb+srv://{mongodb_username}:{mongodb_password}@{mongo_project_name}.vevnl.mongodb.net/{mongo_database_name}?{mongo_client_extra_args}')

        mdb = mdbclient[mongo_database_name]

        """ Prevent cold-booting MongoDB's first request in responses, use a random collection. """
        mdb.some_random_collection.count_documents({})

        print(
            f'Successfully setup MongoDB in {int(round(time() - start, 2) * 1000)} ms.')

        return mdb

    except OperationFailure:
        print('Invalid username or password provided for MongoDB, exiting.')
        exit()
