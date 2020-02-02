#!/usr/bin/python3
# Copyright (c) 2020 by Fred Morris Tacoma WA
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

"""Milter Service.

REQUIRES PYTHON 3.6 OR BETTER

Provides a Milter to resolve aliases to delivery addresses.


Architecture
------------

There are four major types of tasks:

Request Listener
    The request listener started with asyncio.start_server binds to and listens for
    requests on the designated interface / port. When a connection is made, it spawns
    a Request Handler.
    
Request Handler
    The request handler represented by handle_requests() reads requests, attempts to
    determine the delivery addresses and delivers the replies.

Verification Handler
    After alias resolution a VRFY attempt is made with the result, which determines whether
    or not the recipient is accepted. This is represented by verify_account.
    
Configuration Watchdog
    Monitors the configuration file on disk, reloading the configuration when
    a change is detected.
    

Account Verification
--------------------

Trualias attempts to resolve aliases to local delivery accounts; it does not verify
that the accounts (whether resolved as aliases or not) are valid for local delivery.
Verification needs to happen as a separate step.

Trualias is intended to alter the recipient for local delivery. Unimaginative milter
implementations do not fast forward RCPT-only milters, and therefore any alterations
cannot be utilized for additional envelope-only checks. This is why for instance
Postfix cannot perform its local delivery checks after calling milters.

By default, this server ships with account verification based on calling SMTP VRFY.
This test is performed after attempting trualias resolution, on either the original
account name (if no trualias was found) or the resolved account name. Only addresses
with FQDNs found in the LOCAL DOMAINS onfiguration parameter are tested.

In the Postfix case particularly, VRFY is not guaranteed to perform identically to
local delivery checks. You should ensure by testing that your configuration does not
leave your mail server as an open relay or as a source of backscatter from undeliverable
mail.

To implement an alternate source of identity verification, you will need to replace
or modify the following methods in CoroutineContext:

* verify_account() This will be completely rewritten. It expects a recipient (as
  received with SMTP RCPT) and a communications channel with which it can query
  the identity validation service. Only accounts in domains listed in LOCAL DOMAINS
  will be checked; if you need all domains to be checked you will need to alter
  trualias.milter.MilterServer.service_requests().

* say_hello() This is a way of priming the identity verification channel. You may
  or may not need something similar.
  
* handle_requests() Anything referring to "smtp" needs to be rewritten as appropriate
  for the identity verification service.
"""

import os, sys
from os import path
from time import time

import socket
import asyncio
from concurrent.futures import CancelledError
import logging

#import trualias
from trualias.utils import WrappedFunctionResult
from trualias.milter import ServerConfigLoader, Configuration, MilterServer
# A sucky tinbash of smtplib.SMTP so that we can use VRFY with asyncio :-(
from trualias.smtplib import SMTP
import trualias

WATCHDOG_SECONDS = 2
CONFIG_FILE = ('milter_server.conf','trualias.conf')
MAX_READ_SIZE = 4096

def config_files():
    code_path = path.dirname(path.abspath(__file__))
    return (code_path + '/' + f for f in CONFIG_FILE)

class UnexpectedSmtpStatus(Exception):
    pass

class SynchronizerPromise(object):
    def __call__(self, future):
        self.future = future
        return future

class CoroutineContext(object):
    
    def __init__(self, config, config_file, local_fqdn, event_loop):
        self.config = config
        self.config_file = config_file
        self.local_fqdn = local_fqdn
        self.domains = config.local_domains or [ local_fqdn ]
        self.event_loop = event_loop
        self.mtime = os.stat(config_file).st_mtime
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
                        self.config = Configuration().load(ServerConfigLoader(f), raise_on_error=True)
                except Exception as e:
                    logging.error('Unable to reload configuration: {}. Continuing to run with old configuration.'.format(e))                
        return
    
    def check_trualias(self, name):
        """This callback allows us to get a "hot" copy of the config."""
        return trualias.find(name, self.config)
    
    async def verify_account(self, recipient, smtp_connection):
        """If you use some other kind of account validation, you will replace this function.
        
        This callback defines how fine grained VRFY checking is.
        
        This function should return True if the (SMTP) status is acceptable
        and False otherwise.
        
        However, it should affirmatively check for failure as well and raise
        an error if an unexpected status occurs.
        
        The smtp connection is passed in since it is tied to the milter connection.
        """
        if not smtp_connection.future_hello.done():
            await smtp_connection.future_hello
        status = await smtp_connection.vrfy(recipient)
        if status[0] >= 200 and status[0] < 300:
            return True
        if status[0] == 550:
            return False
        raise UnexpectedSmtpStatus(status[0],status[1].decode())
    
    async def say_hello(self, smtp_connection):
        """A task we use to kickstart the SMTP connection."""
        await smtp_connection.init()
        status = await smtp_connection.ehlo()
        if status[0] != 250:
            raise UnexpectedSmtpStatus(status[0],status[1].decode())
        return
        
    async def handle_requests(self, reader, writer):
        """One task is started for each milter connection.
        
        This is the other task you will need to modify if you use some other account
        validation instead of SMTP VRFY.
        """
        print('Connected, creating server task.')
        smtp = SMTP(self.config.smtp_host, self.config.smtp_port, self.event_loop, self.local_fqdn)
        smtp.future_hello = asyncio.ensure_future(self.say_hello(smtp), loop=self.event_loop)
        milter = MilterServer(smtp, self.domains)
        try:
            await milter.service_requests(reader, writer, self.event_loop, self.check_trualias, self.verify_account)
        except UnexpectedSmtpStatus as e:
            logging.error('Unexpected SMTP Status: {} -- {}'.format(*e.args))
            self.event_loop.stop()
        await smtp.quit()
        writer.close()
        return
    
async def close_task(task):
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
        for file_name in config_files():
            try:
                with open(file_name, "r") as f:
                    config = Configuration().load(ServerConfigLoader(f), raise_on_error=True)
                last_exception = None
                config_file = file_name
                break
            except FileNotFoundError as e:
                last_exception = e
        if last_exception:
            raise e
    except Exception as e:
        logging.fatal('Unable to load configuration: {}'.format(e))
        sys.exit(1)
    
    local_fqdn = config.local_host
    if local_fqdn is None:
        local_fqdn = socket.get_fqdn()
    if not local_fqdn:
        logging.fatal('Unable to determine local fully qualified domain name (specify LOCAL HOST in config).')
        sys.exit(1)
        
    logging.basicConfig(level=config.logging)
    
    loop = asyncio.get_event_loop()
    context = CoroutineContext(config, config_file, local_fqdn, loop)

    coro = asyncio.start_server(context.handle_requests, str(config.host), config.port, loop=loop, limit=MAX_READ_SIZE)
    server = loop.run_until_complete(coro)

    watchdog = loop.create_task(context.configuration_watchdog(WATCHDOG_SECONDS))
    
    # Serve requests until we're told to exit (Ctrl+C is pressed, a signal, something really bad, etc.)
    logging.info('Serving on {}'.format(server.sockets[0].getsockname()))
    readers = None
    try:
        loop.run_forever()
    except (KeyboardInterrupt, Exception) as e:
        logging.info('Exiting: {}'.format(str(e) or type(e)))
        readers = asyncio.Task.all_tasks(loop)
    
    # Cancel the periodic task.
    loop.run_until_complete(close_task(watchdog))
    
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
  