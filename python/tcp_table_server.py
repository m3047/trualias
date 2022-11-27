#!/usr/bin/python3
# Copyright (c) 2019-2022 by Fred Morris Tacoma WA
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
from asyncio import CancelledError
import logging
import json

import trualias
from trualias.utils import WrappedFunctionResult
from trualias.statistics import StatisticsFactory, StatisticsCollector, UndeterminedStatisticsCollector

WATCHDOG_SECONDS = 2
CONFIG_FILE = ('tcp_table_server.conf','trualias.conf')
MAX_READ_SIZE = 1024

STATISTICS_PRINTER = logging.info

def resolve_config_files(config_file_names=CONFIG_FILE):
    code_path = path.dirname(path.abspath(__file__))
    return (code_path + '/' + f for f in config_file_names)

class ValidRequest(WrappedFunctionResult):
    """Valid if the validation function returns nothing."""
    def check_for_success(self):
        return not self.result and True or False

class Request(object):
    """Everything to do with processing a request.
    
    The idiom is generally Request(message, statistics, request_stats, config).response
    and then do whatever is sensible with response. Response can be nothing,
    in which case there is nothing further to do. If response is something,
    a timer is started and stop_timer() should be called with one of the types
    configured with configure_statistics().
    """

    COMMANDS = dict(get=2, stats=1, jstats=1)
    STATISTICS_TYPES = ('success','not_found','bad','stats')
    
    @classmethod
    def configure_statistics(cls, statistics):
        """This is called to register statistics collectors.
        
        Enumerate the statuses/types of requests you will collect by calling
        request_timer.stop().
        """
        return statistics.Collector( cls.STATISTICS_TYPES, 
                                     using=UndeterminedStatisticsCollector
                                   )
    
    def __init__(self, message, statistics, request_stats, config):
        self.config = config
        self.statistics = statistics
        self.response = ""
        request = message.strip().split()
        if not request:
            return
        if request_stats is not None:
            self.request_timer = request_stats.start_timer()
        else:
            self.request_timer = None
        self.dispatch_request(request)
        return
    
    def validate_request(self, request):
        verb = request[0].lower()
        if verb not in self.COMMANDS:
            return 'unrecognized command'
        if len(request) != self.COMMANDS[verb]:
            return 'improperly formed request'
        if verb == 'stats' and (self.config.statistics is None or self.statistics is None):
            return 'statistics disabled'
        return ''

    def dispatch_request(self, request):
        """Called by __init__() to dispatch the request."""
        validated = ValidRequest()
        if validated(self.validate_request(request)).success:
            verb = request[0].lower()
            if   verb == 'get':
                self.get(request)
            elif verb == 'stats':
                self.stats()
            elif verb == 'jstats':
                self.jstats()
        else:
            self.bad_request(validated)
        return
    
    def get(self, request):
        """A get request."""
        delivery_address = trualias.find(request[1], self.config)
        if delivery_address:
            self.response = '200 {}\n'.format(delivery_address)
            self.stop_timer('success')
        else:
            self.response = '500 not found\n'
            self.stop_timer('not_found')
        return
    
    def stats(self):
        """Statistics in text format."""
        code = 210
        response = []
        for stat in sorted(self.statistics.stats(), key=lambda x:x['name']):
            response.append('{} {}'.format(code, format_statistics(stat)))
            code = 212
        self.response = '\n'.join(response) + '\n'
        self.stop_timer('stats')
        return
    
    def jstats(self):
        """Statistics in JSON format."""
        if (self.config.statistics is None or self.statistics is None):
            self.response = '400 []\n'
        else:
            self.response = '210 ' + json.dumps(self.statistics.stats()) + '\n'
        self.stop_timer('stats')
        return
    
    def bad_request(self, validator):
        """A bad/unrecognized request."""
        self.response = '400 {}\n'.format(validator.result)
        self.stop_timer('bad')
        return
    
    def stop_timer(self, category):
        if self.request_timer is not None:
            self.request_timer.stop(category)
        return

class CoroutineContext(object):
    
    def __init__(self, config_loader, config, config_file, statistics, request_class=Request):
        self.config_loader = config_loader
        self.config = config
        self.config_file = config_file
        self.mtime = os.stat(config_file).st_mtime
        self.peers = set()
        self.Request = request_class
        if config.statistics is not None:
            self.statistics = statistics
            self.connection_stats = statistics.Collector('connections')
            self.read_stats = statistics.Collector('reads')
            self.write_stats = statistics.Collector('writes')
            self.request_stats = self.Request.configure_statistics(statistics)
        else:
            self.statistics = None
            self.connection_stats = None
            self.read_stats = None
            self.write_stats = None
            self.request_stats = None
        return

    async def configuration_watchdog(self, seconds):
        """Reloads the configuration when it changes.
        
        Only the alias specifications are updated. Configuration items (logging,
        host, port, etc.) are not updated; you must restart the service to
        change them.
        """
        while True:
            await asyncio.sleep(seconds)
            mtime = os.stat(self.config_file).st_mtime
            if mtime > self.mtime:
                self.mtime = mtime
                logging.info('Reloading configuration.')
                try:
                    with open(self.config_file, "r") as f:
                        self.config = self.config_loader(f)
                except Exception as e:
                    logging.error('Unable to reload configuration: {}. Continuing to run with old configuration.'.format(e))                
        return
    
    async def handle_requests(self, reader, writer):
        if self.config.statistics is not None and self.connection_stats is not None:
            connection_timer = self.connection_stats.start_timer()
        else:
            connection_timer = None
        remote_addr = writer.get_extra_info('peername')
        while True:
            if self.config.statistics is not None and self.read_stats is not None:
                read_timer = self.read_stats.start_timer()
            else:
                read_timer = None
            data = await reader.readline()
            if read_timer is not None:
                read_timer.stop()
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
            
            response = self.Request(message, self.statistics, self.request_stats, self.config).response
            if not response:
                continue

            if self.config.statistics is not None and self.write_stats is not None:
                write_timer = self.write_stats.start_timer()
            else:
                write_timer = None
            writer.write(response.encode())
            await writer.drain()
            if write_timer is not None:
                write_timer.stop()

        writer.close()
        if connection_timer is not None:
            connection_timer.stop()
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

def format_statistics(stat):
    if 'depth' in stat:
        return '{}: emin={:.4f} emax={:.4f} e1={:.4f} e10={:.4f} e60={:.4f} dmin={} dmax={} d1={:.4f} d10={:.4f} d60={:.4f} nmin={} nmax={} n1={:.4f} n10={:.4f} n60={:.4f}'.format(
                stat['name'],
                stat['elapsed']['minimum'], stat['elapsed']['maximum'], stat['elapsed']['one'], stat['elapsed']['ten'], stat['elapsed']['sixty'],
                stat['depth']['minimum'], stat['depth']['maximum'], stat['depth']['one'], stat['depth']['ten'], stat['depth']['sixty'],
                stat['n_per_sec']['minimum'], stat['n_per_sec']['maximum'], stat['n_per_sec']['one'], stat['n_per_sec']['ten'], stat['n_per_sec']['sixty'])
    else:
        return '{}: emin={:.4f} emax={:.4f} e1={:.4f} e10={:.4f} e60={:.4f} nmin={} nmax={} n1={:.4f} n10={:.4f} n60={:.4f}'.format(
                stat['name'],
                stat['elapsed']['minimum'], stat['elapsed']['maximum'], stat['elapsed']['one'], stat['elapsed']['ten'], stat['elapsed']['sixty'],
                stat['n_per_sec']['minimum'], stat['n_per_sec']['maximum'], stat['n_per_sec']['one'], stat['n_per_sec']['ten'], stat['n_per_sec']['sixty'])

async def statistics_report(statistics, frequency):
    while True:
        await asyncio.sleep(frequency)
        for stat in sorted(statistics.stats(), key=lambda x:x['name']):
            STATISTICS_PRINTER(format_statistics(stat))
    return

def allocate_context(config_loader, config, config_file, statistics):
    """Create your own adventure!
    
    A typical reason to contemplate subclassing CoroutineContext would be to handle a
    different type of request or handle requests differently. But you don't need to do
    that, instead subclass Request and then specify your subclass when instantiating
    CoroutineContext.
    """
    #return CoroutineContext(config, config_file, statistics, request_class=MyRequests)
    return CoroutineContext(config_loader, config, config_file, statistics)

def config_loader(f):
    """Create your own adventure!
    
    If you're trying to implement your own functionality, you'll likely need custom
    configuration parameters. To do that you'd implement your own configuration
    loader (see trualias.parser.StreamParsingLoader) and configuration (see
    trualias.config.Configuration).
    """
    return trualias.load_config(f, raise_on_error=True)

def run_36(context, config, statistics):
    """Uses run_forever()."""
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(context.handle_requests, str(config.host), config.port, loop=loop, limit=MAX_READ_SIZE)
    server = loop.run_until_complete(coro)
    watchdog = asyncio.run_coroutine_threadsafe(context.configuration_watchdog(WATCHDOG_SECONDS), loop)
    if config.statistics is not None and config.statistics > 0:
        asyncio.run_coroutine_threadsafe(statistics_report(statistics, config.statistics), loop)
        
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

async def run_311(context, config, statistics):
    """Runs as a coroutine itself."""
    loop = asyncio.get_running_loop()
    server = await asyncio.start_server(
            context.handle_requests, str(config.host), config.port, limit=MAX_READ_SIZE
        )
    watchdog = loop.create_task(context.configuration_watchdog(WATCHDOG_SECONDS))
    if config.statistics is not None and config.statistics > 0:
        statistics_reporting = loop.create_task( statistics_report(statistics, config.statistics ))
    else:
        statistics_reporting = None
    
    logging.info('Serving on {}'.format(server.sockets[0].getsockname()))
    
    async with server:
        try:
            await server.serve_forever()
        except (CancelledError, Exception) as e:
            logging.info('Exiting: {}'.format(str(e) or type(e)))
            
    return

def main(allocate_context=allocate_context, config_files=None, config_loader=config_loader):
    """Call main() with a different context allocator if you subclass CoroutineContext."""
    if config_files is None:
        config_files = resolve_config_files()
    try:
        for file_name in config_files:
            try:
                with open(file_name, "r") as f:
                    config = config_loader(f)
                last_exception = None
                config_file = file_name
                break
            except FileNotFoundError as e:
                last_exception = e
        if last_exception:
            raise FileNotFoundError('No configuration file could be found.')
    except Exception as e:
        logging.fatal('Unable to load configuration: {}'.format(e))
        sys.exit(1)
    
    logging.basicConfig(level=config.logging)
    
    if config.statistics is not None:
        statistics = StatisticsFactory()
    else:
        statistics = None
    context = allocate_context(config_loader, config, config_file, statistics)
    
    standard_run_args = (context, config, statistics)
    if config.python_is_311:
        # Requires everything to run within the loop context.
        asyncio.run(run_311(*standard_run_args))
    else:
        # Coroutines in the nonrunning loop queue is a feature, not a bug.
        run_36(*standard_run_args)
    
    return

if __name__ == "__main__":
    main()
    
