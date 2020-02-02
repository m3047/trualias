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
# 
# SMTP class contains portions of the base class smtplib.SMTP which
# are copyright © 2001-2018 Python Software Foundation; All Rights
# Reserved and distributed under the Python software license.

"""Used by the Milter Server as an option for local account validation using VRFY."""

import socket
import smtplib
import asyncio
import logging

import re

TIMEOUT = 10    # seconds
MAXLINE = 1024
CRLF = "\r\n"

class NotASocket(object):
    """Not a socket but used like one in SMTP connections."""
    def __init__(self, host, port, timeout, event_loop):

        self.future_connection = asyncio.open_connection(host, port, loop=event_loop)
        self.timeout = timeout
        self.event_loop = event_loop
        self.reader = None
        self.writer = None
        return

    async def ensure_socket(self):
        """Decorator to ensure a good to go socket."""
        reader, writer = await asyncio.wait_for(self.future_connection, self.timeout, loop=self.event_loop)
        self.reader = reader
        self.writer = writer
        return
    
    # Methods on the socket.
    async def sendall(self, s):
        if self.writer is None:
            await self.ensure_socket()
        self.writer.write(s)
        await self.writer.drain()
        return
    
    def makefile(self, mode):
        return self
    
    # Methods on the file.
    async def readline(self):
        if self.reader is None:
            await self.ensure_socket()
        return await self.reader.readline()
        
    # Methods on both the file and the socket.
    def close(self):
        if self.writer:
            self.writer.close()
        self.reader = None
        self.writer = None
        
class SMTP(smtplib.SMTP):
    """Adapted for asyncio.
    
    Does not support anything but plain unencrypted SMTP.
    
    SMELL: I don't even like smtplib, it seems immature. All this for VRFY? Hrmmm....
           My impulse is to throw it out and write something designed around asyncio.
           
           It might be useful though to someone thinking of implementing some other
           kind of account lookup service: try not to do this!
    
    A lot of this is direct alliteration from smtplib.SMTP to make it work with
    asyncio, apologies in advance.
    """
    def __init__(self, host, port, event_loop, local_hostname,
                           timeout=TIMEOUT,
                           source_address=None
                          ):
        # Will callback to _get_socket() so needs to be set first.
        self.event_loop = event_loop

        self._host = host
        self._port = port
        self.timeout = timeout
        self.esmtp_features = {}
        self.command_encoding = 'ascii'
        self.source_address = source_address
        self.local_hostname = local_hostname
        
    async def init(self):

        if self._host:
            code, msg = await self.connect(self._host, self._port)
            if code != 220:
                self.close()
                raise smtplib.SMTPConnectError(code, msg)

        return

    def _get_socket(self, host, port, timeout):
        return NotASocket(host, port, timeout, self.event_loop)

    async def __exit__(self, *args):
        try:
            code, message = await self.docmd("QUIT")
            if code != 221:
                raise smtplib.SMTPResponseException(code, message)
        except smtplib.SMTPServerDisconnected:
            pass
        finally:
            self.close()
            
    async def connect(self, host='localhost', port=0, source_address=None):
        """Connect to a host on a given port.

        If the hostname ends with a colon (`:') followed by a number, and
        there is no port specified, that suffix will be stripped off and the
        number interpreted as the port number to use.

        Note: This method is automatically invoked by __init__, if a host is
        specified during instantiation.

        """

        if source_address:
            self.source_address = source_address

        if not port and (host.find(':') == host.rfind(':')):
            i = host.rfind(':')
            if i >= 0:
                host, port = host[:i], host[i + 1:]
                try:
                    port = int(port)
                except ValueError:
                    raise OSError("nonnumeric port")
        if not port:
            port = self.default_port
        if self.debuglevel > 0:
            self._print_debug('connect:', (host, port))
        self.sock = self._get_socket(host, port, self.timeout)
        self.file = None
        (code, msg) = await self.getreply()
        if self.debuglevel > 0:
            self._print_debug('connect:', repr(msg))
        return (code, msg)

    async def send(self, s):
        """Send `s' to the server."""
        if self.debuglevel > 0:
            self._print_debug('send:', repr(s))
        if hasattr(self, 'sock') and self.sock:
            if isinstance(s, str):
                # send is used by the 'data' command, where command_encoding
                # should not be used, but 'data' needs to convert the string to
                # binary itself anyway, so that's not a problem.
                s = s.encode(self.command_encoding)
            try:
                await self.sock.sendall(s)
            except OSError:
                self.close()
                raise smtplib.SMTPServerDisconnected('Server not connected')
        else:
            raise smtplib.SMTPServerDisconnected('please run connect() first')
        
        return

    async def putcmd(self, cmd, args=""):
        """Send a command to the server."""
        if args == "":
            str = '%s%s' % (cmd, CRLF)
        else:
            str = '%s %s%s' % (cmd, args, CRLF)
        await self.send(str)
        return

    async def getreply(self):
        """Get a reply from the server.

        Returns a tuple consisting of:

          - server response code (e.g. '250', or such, if all goes well)
            Note: returns -1 if it can't read response code.

          - server response string corresponding to response code (multiline
            responses are converted to a single, multiline string).

        Raises SMTPServerDisconnected if end-of-file is reached.
        """
        resp = []
        if self.file is None:
            self.file = self.sock.makefile('rb')
        while 1:
            try:
                line = await self.file.readline()
            except OSError as e:
                self.close()
                raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed: "
                                             + str(e))
            if not line:
                self.close()
                raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
            if self.debuglevel > 0:
                self._print_debug('reply:', repr(line))
            if len(line) > MAXLINE:
                self.close()
                raise smtplib.SMTPResponseException(500, "Line too long.")
            resp.append(line[4:].strip(b' \t\r\n'))
            code = line[:3]
            # Check that the error code is syntactically correct.
            # Don't attempt to read a continuation line if it is broken.
            try:
                errcode = int(code)
            except ValueError:
                errcode = -1
                break
            # Check if multiline response.
            if line[3:4] != b"-":
                break

        errmsg = b"\n".join(resp)
        if self.debuglevel > 0:
            self._print_debug('reply: retcode (%s); Msg: %a' % (errcode, errmsg))
        return errcode, errmsg

    async def docmd(self, cmd, args=""):
        """Send a command, and return its response code."""
        await self.putcmd(cmd, args)
        return await self.getreply()

    async def ehlo(self, name=''):
        """ SMTP 'ehlo' command.
        Hostname to send for this command defaults to the FQDN of the local
        host.
        """
        self.esmtp_features = {}
        await self.putcmd(self.ehlo_msg, name or self.local_hostname)
        (code, msg) = await self.getreply()
        # According to RFC1869 some (badly written)
        # MTA's will disconnect on an ehlo. Toss an exception if
        # that happens -ddm
        if code == -1 and len(msg) == 0:
            self.close()
            raise smtplib.SMTPServerDisconnected("Server not connected")
        self.ehlo_resp = msg
        if code != 250:
            return (code, msg)
        self.does_esmtp = 1
        #parse the ehlo response -ddm
        assert isinstance(self.ehlo_resp, bytes), repr(self.ehlo_resp)
        resp = self.ehlo_resp.decode("latin-1").split('\n')
        del resp[0]
        for each in resp:
            # To be able to communicate with as many SMTP servers as possible,
            # we have to take the old-style auth advertisement into account,
            # because:
            # 1) Else our SMTP feature parser gets confused.
            # 2) There are some servers that only advertise the auth methods we
            #    support using the old style.
            auth_match = smtplib.OLDSTYLE_AUTH.match(each)
            if auth_match:
                # This doesn't remove duplicates, but that's no problem
                self.esmtp_features["auth"] = self.esmtp_features.get("auth", "") \
                        + " " + auth_match.groups(0)[0]
                continue

            # RFC 1869 requires a space between ehlo keyword and parameters.
            # It's actually stricter, in that only spaces are allowed between
            # parameters, but were not going to check for that here.  Note
            # that the space isn't present if there are no parameters.
            m = re.match(r'(?P<feature>[A-Za-z0-9][A-Za-z0-9\-]*) ?', each)
            if m:
                feature = m.group("feature").lower()
                params = m.string[m.end("feature"):].strip()
                if feature == "auth":
                    self.esmtp_features[feature] = self.esmtp_features.get(feature, "") \
                            + " " + params
                else:
                    self.esmtp_features[feature] = params
        return (code, msg)

    async def vrfy(self, address):
        """SMTP 'verify' command -- checks for address validity."""
        await self.putcmd("vrfy", smtplib._addr_only(address))
        return await self.getreply()

    async def ehlo_or_helo_if_needed(self):
        """Call self.ehlo() and/or self.helo() if needed.

        If there has been no previous EHLO or HELO command this session, this
        method tries ESMTP EHLO first.

        This method may raise the following exceptions:

         SMTPHeloError            The server didn't reply properly to
                                  the helo greeting.
        """
        if self.helo_resp is None and self.ehlo_resp is None:
            if not (200 <= await self.ehlo()[0] <= 299):
                raise smtplib.SMTPHeloError(code, resp)

    async def quit(self):
        """Terminate the SMTP session."""
        res = await self.docmd("quit")
        # A new EHLO is required after reconnecting with connect()
        self.ehlo_resp = self.helo_resp = None
        self.esmtp_features = {}
        self.does_esmtp = False
        self.close()
        return res

