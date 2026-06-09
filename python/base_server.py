#!/usr/bin/python3
# Copyright (c) 2019-2026 by Fred Morris Tacoma WA
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

"""Create Your Own Adventure Postfix TCP Table Service.

REQUIRES PYTHON 3.6 OR BETTER

Provides a Postfix TCP table service for... whatever!

Configuration is loaded from a .ini file with the same name as this file, but
ending with .ini instead of .py. The file is looked for in two places, with
precedence:

    1.  The current working directory.
    2.  The directory containing this file.

Architecture
------------

There are three types of tasks:

Request Listener - CoroutineContext.handle_requests()
    The request listener binds to and listens for requests on the designated
    interface / port. When a connection is made, it spawns a Resolver.
    
Request Handler - Request
    Listens on a connection for commands / requests and formulates
    responses / replies.
    
Configuration Watchdog
    Monitors the configuration file on disk, reloading the configuration when
    a change is detected.

An Important Note: While using something like postmap to query the service results
in a short-lived connection, Postfix itself opens the TCP socket and keeps it open.
You might think the Request Listener task is unimportant, but it's not! It tracks,
and listens on, open connections.

There are three major classes in this module:

Configuration
    Loads and validates the configuration. Configurations are stored in .ini file
    format. The configuration is expected to have the same name as this file, but
    ending in .ini instead of .py.

Request
    For handling commands / requests. Along with Configuration, this is the one you
    are likely to augment / subclass to suit your purposes.
    
CoroutineContext
    Shared context for the connection listener and configuration watchdog.
"""

import os, sys
from os import path
from time import time
import sysconfig

from configparser import ConfigParser

import asyncio
from asyncio import CancelledError
import logging
import json

from ipaddress import ip_address

from trualias.utils import WrappedFunctionResult
from trualias.statistics import StatisticsFactory, StatisticsCollector, UndeterminedStatisticsCollector

WATCHDOG_SECONDS = 2
MAX_READ_SIZE = 1024

STATISTICS_PRINTER = logging.info

DEFAULT_STATISTICS = None
DEFAULT_LOGGING = 'info'
DEFAULT_ADDRESS = '127.0.0.1'
DEFAULT_PORT = 3047

def resolve_config_files():
    """The places to check for configs.
    
    The config file name is taken from the name the script was called as, with
    the extension .ini. For example if this script is called as base_server.py
    then the config file will be base_server.ini.
    
    In order of precedence the config file will be looked for:
    
        * in the current working directory
        * in the script directory
    """
    abspath = path.abspath(sys.argv[0])
    script_dir, script_name = path.split(abspath)
    script_dir += '/'
    if script_name.endswith('.py'):
        script_name = script_name[:-3]
    ini_name = script_name + '.ini'
    return ( ini_name, script_dir+ini_name )

class ConfigurationError(Exception):
    """A generic configuration error.
    
    Ideally the configuration property checker scripts raise exceptions if they
    encounter borkage, but if a routine returns False we raise this.
    """
    def __init__(self, checker, error):
        if isinstance( error, Exception ):
            error = '{}: {}'.format( type(error).__name__, error )
        Exception.__init__(self, '{}: {}'.format(checker.__name__, error))
        return
    
LOGGING_LEVELS = dict(debug=logging.DEBUG, info=logging.INFO, warning=logging.WARNING, error=logging.ERROR, critical=logging.CRITICAL)
Configuration_Checkers = set()
Configuration_Properties = set()
property_alias = property
class Configuration(object):
    """A simple configuration wrapper.
    
    The contents of the .ini file are available as the property parsed,
    which is a ConfigParser object.
    """
    #STATISTICS_MIN_INTERVAL = 60
    STATISTICS_MIN_INTERVAL = 10
    
    @classmethod
    def From_File( cls, file_name, check=True ):
        """Alternate constructor which initializes from a file."""
        parser = ConfigParser()
        parser.read(file_name)
        return cls(parser, check)
    
    def property(f):
        """Overrides the default property decorator...
        
        ...so that we can make a list of them.
        """
        Configuration_Properties.add(f.__name__)
        p = property_alias(f)
        return p
    
    def checker(f):
        """This is a decorator for validity checkers.
        
        These are all collected and then run at the end of __init__().
        Presumably they will raise exceptions if they encounter issues.
        """
        Configuration_Checkers.add(f)
        return f
    
    def cached(f):
        """When a getter mutates a value, we cache that."""
        def wrapper(self):
            if f in self.cached_items:
                return self.cached_items[f]
            v = f(self)
            self.cached_items[f] = v
            return v
        wrapper.__doc__ = f.__doc__
        wrapper.__name__ = f.__name__
        return wrapper

    def __init__(self, parsed, check=True):
        """Create a Configuration from ConfigParser output.
        
        If check is True then the configuration is checked for semantic validity.
        """
        self.parsed = parsed
        self.cached_items = dict()
        if check:
            self.check_config()
        return
    
    def check_config(self):
        """Raises ConfigurationError or returns True."""
        for f in Configuration_Checkers:

            try:
                exc = None
                good = f(self)
            except Exception as e:
                exc = e
            if exc:
                raise ConfigurationError( f, exc )

            if not good:
                raise ConfigurationError(f, 'Configuration issue detected.')

        return True
    
    def changed(self, other):
        """What is different in this config versus the other?
        
        Returns a tuple with sets of:
        
            new     newly defined properties
            changed changed properties
            deleted newly undefined / deleted properties
        """
        changes = dict( new=set(), changed=set(), deleted=set() )
        
        for prop in Configuration_Properties:

            try:
                no_v_new = True
                v_new = getattr(self, prop)
                no_v_new = False
            except AttributeError:
                pass
            try:
                no_v_old = True
                v_old = getattr(other, prop)
                no_v_old = False
            except AttributeError:
                pass

            if   ( no_v_new and not no_v_old ):
                changes['deleted'].add(prop)
            elif ( no_v_old and not no_v_new ):
                changes['new'].add(prop)
            elif ( not (no_v_old or no_v_new)
               and v_new != v_old
                 ):
                 changes['changed'].add(prop)
                
        return tuple( changes[k] for k in ('new','changed','deleted') )

    ############ PROPERTIES BELOW HERE ############

    @property
    @cached
    def statistics(self):
        """PROPERTY enable statistics and set frequency
        
        Section: Application
        
        Number of seconds between reports. If not zero or undefined, should be
        at least 60 seconds.
        """
        sect_opt = ( 'Application', 'statistics' )
        if self.parsed.has_option(*sect_opt):
            v = self.parsed.get(*sect_opt)
            if v == 'None':
                v = None
            else:
                v = int( self.parsed.get(*sect_opt) )
                if not v:
                    v = None
        else:
            v = None
        return v
    
    @checker
    def statistics_check(self):
        v = self.statistics     # may raise an exception
        if v is None:
            return True
        if v != 0 and v < self.STATISTICS_MIN_INTERVAL:
            raise ValueError( 'Application.statistics must be >= {} if nonzero.'.format(STATISTICS_MIN_INTERVAL) )
        return True
    
    @property
    @cached
    def logging(self):
        """PROPERTY logging level
        
        Section: Application

        Returns a logging level:
        
            debug    logging.DEBUG
            info     logging.INFO
            warning  logging.WARNING
            error    logging.ERROR
            critical logging.CRITICAL
            
        If not defined then the level defined in DEFAULT_LOGGING is used.
        """        
        sect_opt = ( 'Application', 'logging' )
        if self.parsed.has_option(*sect_opt):
            v = self.parsed.get(*sect_opt)
            if v == 'None':
                v = DEFAULT_LOGGING
        else:
            v = DEFAULT_LOGGING
        
        try:
            ke = False
            v = LOGGING_LEVELS[v.lower()]
        except KeyError:
            ke = True
        if ke:
            raise KeyError( 'Logging level must be one of {}'.format(', '.join(LOGGING_LEVELS.keys())) )
        return v
    
    @checker
    def logging_check(self):
        v = self.logging    # may raise an exception
        return True
    
    @property
    @cached
    def req_logging(self):
        """PROPERTY flags passed to Request to control logging.
        
        Section: Application
        
            A space-separated list of flags gleaned from reading the code. ;-)
        
        Returns a set of zero or more flags:
            conn_logging    Prints the first request on a new connection.
            raw_message     Prints out the raw client request.
        """
        sect_opt = ( 'Application', 'req_logging' )
        if self.parsed.has_option(*sect_opt):
            v = self.parsed.get(*sect_opt)
            v = set( v.strip().lower().split() )
        else:
            v = set()
        return v
        
    @property
    @cached
    def address(self):
        """PROPERTY address to listen on
        
        Section: Network
        
        Default is DEFAULT_ADDRESS (127.0.0.1 as shipped).
        """
        sect_opt = ( 'Network', 'address' )
        if self.parsed.has_option(*sect_opt):
            v = ip_address( self.parsed.get(*sect_opt) )
        else:
            v = ip_address(DEFAULT_ADDRESS)
        return str(v)
    
    @checker
    def address_check(self):
        v = self.address    # may raise an exception
        return True
    
    @property
    @cached
    def port(self):
        """PROPERTY port to listen on
        
        Section: Network
        
        Port to listen on. Must be between 1..65535. Default is DEFAULT_PORT
        (3047 as shipped).
        """
        sect_opt = ( 'Network', 'port' )
        if self.parsed.has_option(*sect_opt):
            v = int( self.parsed.get(*sect_opt) )
        else:
            v = DEFAULT_PORT
        return v
    
    @checker
    def port_check(self):
        v = self.port       # may raise an exception
        if v < 1 or v > 65535:
            raise ValueError( 'Network.port must be 1..65535.' )
        return True
    
    @property
    @cached
    def python_is_311(self):
        """PROPERTY is Python 3.11 or later?
        
        Section: Internal
        
        THIS IS AN EPHEMERAL PROPERTY AND YOU SHOULD NEVER NEED TO SET IT
        """
        return int( sysconfig.get_python_version().split('.')[1] ) >= 11
    
    def all_defined_properties(self):
        """Attempt to fetch all defined properties.
        
        For testing, if nothing else. Returns a hash with the values / exceptions.
        """
        results = {}
        for prop in Configuration_Properties:
            try:
                results[prop] = getattr(self, prop)
            except Exception as e:
                results[prop] = e
        return results
    
class ValidRequest(WrappedFunctionResult):
    """Valid if the validation function returns nothing."""
    def check_for_success(self):
        return not self.result and True or False

class Request(object):
    """Everything to do with processing a request.
    
    The idiom is generally Request(message, statistics, request_stats, config...).response
    and then do whatever is sensible with response. Response can be nothing,
    in which case there is nothing further to do. If there is a response then it is written
    back to the requestor.
    
    The optional self.deferred awaitable
    ------------------------------------
    
    Maybe you have some different data sources to pull together but in any case you
    want to take advantage of asyncio to parallelize I/O:

        async def my_deferred( self, arg ):
            ...
        def __init__( self ):
            ...
            Request.__init__(self)
            # After the parent (this) constructor has been called...
            self.deferred = self.my_deferred( something_i_just_calculated )
            
        # or maybe you only do it inside of get....
        def get(self, request):
            ...
            self.deferred = self.my_deferred( something_i_just_calculated )
    
    If self.deferred is defined and not None, it will be awaited in
    CoroutineContext.handle_requests() after the Request object is instantiated.
    
    In this case, you can defer however much of the processing is desirable into the
    awaitable. The connection over which requests are processed is single-issue, you
    won't see multiple requests from a single connection being interleaved: this is
    an architectural limitation of TCP tables.
    
    The optional argument "arg" is optional, self probably contains everything your awaitable
    needs. ;-)
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
    
    def __init__(self, message, statistics, request_stats, config, loop, logging_categories=set()):
        """Initialize a Request object.
        
        message         The message which was sent from the client.
        statistics      See CoroutineContext for further info...
        request_stats   ...set statistics = 60 in the .ini for statistics to print once a minute
        """
        self.config = config
        self.statistics = statistics
        self.response = ""
        self.loop = loop
        self.logging_categories = logging_categories
        self.deferred = None    # An optional awaitable to be awaited after initialization completes.
        if 'raw_message' in logging_categories:
            logging.info('Saw {}'.format(message.strip()))
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
        #delivery_address = request[1]
        #if delivery_address and self.config.processor:
            #try:
                #delivery_address = self.config.processor.preprocess(delivery_address)[0]
            #except Exception as e:
                #delivery_address = ''
                #logging.error('Error during processor.preprocess(): {}: {}'.format(type(e).__name__,e))
        #if delivery_address:
            #delivery_address = trualias.find(delivery_address, self.config)
        #if delivery_address and self.config.processor:
            #try:
                #delivery_address = self.config.processor.postprocess(delivery_address)[0]
            #except Exception as e:
                #delivery_address = ''
                #logging.error('Error during processor.postprocess(): {}: {}'.format(type(e).__name__,e))
        #if delivery_address:
            #self.response = '200 {}\n'.format(delivery_address)
            #self.stop_timer('success')
        #else:
            #self.response = '500 not found\n'
            #self.stop_timer('not_found')
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
        self.configure_statistics(statistics)
        # The following are updated by setting the property directly.
        self.statistics_reporting = None
        self.loop = None
        self.server = None
        return
    
    def configure_statistics(self, statistics):        
        if statistics is not None:
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
    
    async def process_config_updates(self, new, changed, deleted, all_changed):
        """Override this to process your own config updates.
        
        It is called from configuration_watchdog() with sets of the parameters
        which are new / changed / deleted... and any of the above as all_changed.
        """
        if 'statistics' in all_changed and self.statistics_reporting:
            self.statistics_reporting.cancel()
            try:
                was_cancelled = False
                await self.statistics_reporting
            except CancelledError:
                was_cancelled = True
            if not was_cancelled:
                logging.error('statistics_report() coroutine failed to cancel. Continuing to run with old configuration.')
            else:
                self.configure_statistics( None )
                self.statistics_reporting = None
        if 'statistics' in (new | changed) and self.statistics_reporting is None and self.config.statistics:
            self.configure_statistics( StatisticsFactory() )
            report_coro = statistics_report(self.statistics, self.config.statistics )
            self.statistics_reporting = self.loop.create_task( report_coro )
        
        if 'logging' in all_changed:
            logging.getLogger().setLevel( self.config.logging )
            
        if {'address','port'}  & all_changed:
            self.server.close()
            await self.server.wait_closed()
            await close_readers([
                task for task in (self.config.python_is_311 and asyncio.all_tasks() or asyncio.Task.all_tasks())
                if task._coro.__name__ == 'handle_requests'
            ])
            self.server = await asyncio.start_server(
                            self.handle_requests, self.config.address, self.config.port, limit=MAX_READ_SIZE
                        )
        return

    async def configuration_watchdog(self, seconds):
        """Reloads the configuration when it changes.
        
        This includes potentially the following actions:
        
          * starting / stopping statistics
          * changing the statistics reporting frequency
          * changing the logging level
          * changing the address / port the server listens on
        
        """
        try:
            while True:
                await asyncio.sleep(seconds)

                mtime = os.stat(self.config_file).st_mtime
                if mtime > self.mtime:
                    self.mtime = mtime
                    logging.info('Reloading configuration.')
                    try:
                        reload_failed = False
                        old_config = self.config
                        with open(self.config_file, "r") as f:
                            self.config = self.config_loader(f)
                    except Exception as e:
                        reload_failed = True
                        logging.error('Unable to reload configuration: {}. Continuing to run with old configuration.'.format(e))
                    if reload_failed:
                        continue
                else:
                    continue
                
                # Now see what needs to be updated based on what changed.
                new, changed, deleted = self.config.changed( old_config )
                all_changed = new | changed | deleted
                
                await self.process_config_updates(new, changed, deleted, all_changed)
                
        except CancelledError as e:
            raise e
        except Exception as e:
            logging.critical('configuration_watchdog() as died! {}: {}'.format(type(e).__name__, e))
            self.loop.stop()
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
            try:
                data = await reader.readline()
            except CancelledError:
                break
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
                if 'conn_logging' in self.config.req_logging:
                    logging.info("Received %r from %r" % (message, remote_addr))
            
            request = self.Request( message, self.statistics, self.request_stats, self.config, self.loop, 
                                    logging_categories=self.config.req_logging
                                  )
            if request.deferred:
                await request.deferred
            response = request.response
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
        self.peers.discard( remote_addr )
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
    #return CoroutineContext(config_loader, config, config_file, statistics, request_class=MyRequest)
    return CoroutineContext(config_loader, config, config_file, statistics)

def config_loader(f):
    """Create your own adventure!
    
    This server does not use the Trualias configuration parser, it uses the builtin Python
    ConfigParser
    """
    parser = ConfigParser()
    parser.read_file(f)
    return Configuration( parser )

def run_36(context, config, statistics):
    """Uses run_forever()."""
    loop = asyncio.get_event_loop()
    context.loop = loop
    coro = asyncio.start_server(context.handle_requests, config.address, config.port, loop=loop, limit=MAX_READ_SIZE)
    server = loop.run_until_complete(coro)
    context.server = server
    watchdog = loop.create_task(context.configuration_watchdog(WATCHDOG_SECONDS))
    if config.statistics is not None and config.statistics > 0:
        context.statistics_reporting = loop.create_task(statistics_report(statistics, config.statistics))
    else:
        context.statistics_reporting = None
        
    # Serve requests until we're told to exit (Ctrl+C is pressed, a signal, something really bad, etc.)
    logging.info('Serving on {}'.format(server.sockets[0].getsockname()))
    readers = None
    try:
        loop.run_forever()
    except (KeyboardInterrupt, Exception) as e:
        logging.info('Exiting: {}'.format(str(e) or type(e).__name__))
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
    context.loop = loop
    server = await asyncio.start_server(
            context.handle_requests, config.address, config.port, limit=MAX_READ_SIZE
        )
    context.server = server
    watchdog = loop.create_task(context.configuration_watchdog(WATCHDOG_SECONDS))
    if config.statistics is not None and config.statistics > 0:
        context.statistics_reporting = loop.create_task( statistics_report(statistics, config.statistics ))
    else:
        context.statistics_reporting = None
    
    logging.info('Serving on {}'.format(server.sockets[0].getsockname()))
    
    readers = None
    async with server:
        try:
            await server.serve_forever()
        except (CancelledError, Exception) as e:
            logging.info('Exiting: {}'.format(str(e) or type(e).__name__))
            readers = asyncio.all_tasks(loop)

    # Kill reader tasks.
    if readers:
        await close_readers(readers)

    # Close the server.
    server.close()
    await server.wait_closed()
    loop.close()

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
    
