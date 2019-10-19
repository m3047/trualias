#!/usr/bin/python3
# Copyright (c) 2019 by Fred Morris Tacoma WA
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Postfix TCP Table Service.

REQUIRES PYTHON 3.6 OR BETTER

Provides a Postfix TCP table service to resolve aliases to delivery addresses.
If the service is running (assuming it's listening on 127.0.0.1:3047), you can
query it with postmap (from the Postfix distribution) like this:

    postmap -q "alias_to_resolve" tcp:127.0.0.1:3047

Architecture
------------

There are three types of tasks:

Request Listener
    The request listener binds to and listens for requests on the designated
    interface / port. When a connection is made, it spawns a Resolver.
    
Resolver
    The resolver attempts to determine the delivery addresses and deliver the
    replies.
    
Configuration Watchdog
    Monitors the configuration file on disk, reloading the configuration when
    a change is detected.

An Important Note: While using something like postmap to query the service results
in a short-lived connection, Postfix itself opens the TCP socket and keeps it open.
You might think the Request Listener task is unimportant, but it's not! It tracks,
and listens on, open connections.
"""

import os, sys
from os import path
from time import time

import asyncio
from concurrent.futures import CancelledError
import logging

import trualias
from trualias.utils import WrappedFunctionResult

WATCHDOG_SECONDS = 2
CONFIG_FILE = 'trualias.conf'
MAX_READ_SIZE = 1024

def config_file():
    return path.dirname(path.abspath(__file__)) + '/' + CONFIG_FILE

class ValidRequest(WrappedFunctionResult):
    """Valid if the validation function returns nothing."""
    def check_for_success(self):
        return not self.result and True or False

class CoroutineContext(object):
    
    def __init__(self, config):
        self.config = config
        self.mtime = os.stat(config_file()).st_mtime
        self.peers = set()
        return

    async def configuration_watchdog(self, seconds):
        """Reloads the configuration when it changes.
        
        Only the alias specifications are updated. Configuration items (logging,
        host, port, etc.) are not updated; you must restart the service to
        change them.
        """
        while True:
            await asyncio.sleep(seconds)
            mtime = os.stat(config_file()).st_mtime
            if mtime > self.mtime:
                self.mtime = mtime
                logging.info('Reloading configuration.')
                try:
                    with open(config_file(), "r") as f:
                        self.config = trualias.load_config(f, raise_on_error=True)
                except Exception as e:
                    logging.error('Unable to reload configuration: {}. Continuing to run with old configuration.'.format(e))                
        return
    
    @staticmethod
    def validate_request(request):
        if len(request) != 2:
            return 'improperly formed request'
        if request[0].lower() != 'get':
            return 'unrecognized command'
        return ''

    async def handle_requests(self, reader, writer):
        validated = ValidRequest()
        while True:
            remote_addr = writer.get_extra_info('peername')
            data = await reader.readline()
            try:
                message = data.decode()
            except UnicodeDecodeError:
                logging.warn('Invalid characters in stream (UnicodeDecodeError), closing connection for {}'.format(remote_addr))
                break
            if not message:
                break

            if remote_addr not in self.peers:
                self.peers.add(remote_addr)
                logging.info("Received %r from %r" % (message, remote_addr))
            
            request = message.strip().split()
            if not request:
                continue
            if validated(self.validate_request(request)).success:
                delivery_address = trualias.find(request[1], self.config)
                if delivery_address:
                    response = '200 {}\n'.format(delivery_address)
                else:
                    response = '500 not found\n'
            else:
                response = '400 {}\n'.format(validated.result)

            writer.write(response.encode())
            await writer.drain()

        writer.close()
        return
    
async def close_watchdog(task):
    task.cancel()
    return
    
async def close_readers(readers):
    all_readers = asyncio.gather(*readers)
    all_readers.cancel()
    try:
        await all_readers
    except CancelledError:
        pass
    return

def main():
    try:
        with open(config_file(), "r") as f:
            config = trualias.load_config(f, raise_on_error=True)
    except Exception as e:
        logging.fatal('Unable to load configuration: {}'.format(e))
        sys.exit(1)
    
    logging.basicConfig(level=config.logging)
    
    context = CoroutineContext(config)
    
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(context.handle_requests, str(config.host), config.port, loop=loop, limit=MAX_READ_SIZE)
    server = loop.run_until_complete(coro)
    watchdog = asyncio.run_coroutine_threadsafe(context.configuration_watchdog(WATCHDOG_SECONDS), loop)
    
    # Serve requests until we're told to exit (Ctrl+C is pressed, a signal, something really bad, etc.)
    logging.info('Serving on {}'.format(server.sockets[0].getsockname()))
    readers = None
    try:
        loop.run_forever()
    except (KeyboardInterrupt, Exception) as e:
        logging.info('Exiting: {}'.format(str(e) or type(e)))
        readers = asyncio.Task.all_tasks(loop)
    
    # Cancel the periodic task.
    loop.run_until_complete(close_watchdog(watchdog))
    
    # Kill reader tasks.
    if readers:
        loop.run_until_complete(close_readers(readers))
    
    # Close the server.
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
    
    return

if __name__ == "__main__":
    main()
    