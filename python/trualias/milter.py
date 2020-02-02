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

import logging
import asyncio
import smtplib

from .parser import StreamParsingLoader, to_boolean, to_address, to_port, to_loglevel, to_account
from .config import Configuration as BaseConfiguration

UNSIGNED_BIG_ENDIAN = dict(byteorder='big', signed=False)
CRLF = '\r\n'

#
# SMFI* see sendmail/include/libmilter/mfdef.h and mfapi.h
#

# Commands in typical execution order.
SMFIC_OPTNEG =  'O'         # Option negotiation
SMFIC_MACRO =   'D'         # Define macro
SMFIC_CONNECT = 'C'         # Connection info
SMFIC_UNKNOWN = 'U'         # Any unknown (SMTP) command
SMFIC_HELO =    'H'         # HELO
SMFIC_ABORT =   'A'         # Abort is valid any time.
SMFIC_MAIL =    'M'         # MAIL from
SMFIC_RCPT =    'R'         # RCPT to
SMFIC_DATA =    'T'         # DATA
SMFIC_HEADER =  'L'         # Header
SMFIC_EOH =     'N'         # eoh
SMFIC_BODY =    'B'         # Body chunk
SMFIC_EOB =     'E'         # Final body chunk
SMFIC_QUIT =    'Q'         # QUIT
SMFIC_QUIT_NC = 'K'         # Quit + start new connection

# Actions
SMFIR_ADDRCPT =     '+'     # Add recipient 
SMFIR_DELRCPT =     '-'     # Remove recipient 
SMFIR_ADDRCPT_PAR = '2'     # Add recipient (incl. ESMTP args)
SMFIR_SHUTDOWN =    '4'     # 421 shutdown (internal to MTA)
SMFIR_ACCEPT =      'a'     # Accept 
SMFIR_REPLBODY =    'b'     # Replace body (chunk)
SMFIR_CONTINUE =    'c'     # Continue
SMFIR_DISCARD =     'd'     # Discard
SMFIR_CHGFROM =     'e'     # Change envelope sender
SMFIR_CONN_FAIL =   'f'     # Cause a connection failure
SMFIR_ADDHEADER =   'h'     # Add header
SMFIR_INSHEADER =   'i'     # Insert header
SMFIR_SETSYMLIST =  'l'     # Set list of symbols
SMFIR_CHGHEADER =   'm'     # Change header
SMFIR_PROGRESS =    'p'     # Progress
SMFIR_QUARANTINE =  'q'     # Quarantine
SMFIR_REJECT =      'r'     # Reject
SMFIR_SKIP =        's'     # Skip further events
SMFIR_TEMPFAIL =    't'     # Tempfail
SMFIR_REPLYCODE =   'y'     # Reply code etc.

# Possible allowed / wanted actions
SMFIF_ADDHDRS =      0x0001 # add headers
SMFIF_CHGBODY =      0x0002 # replace body
SMFIF_ADDRCPT =      0x0004 # add recipients
SMFIF_DELRCPT =      0x0008 # delete recipients
SMFIF_CHGHDRS =      0x0010 # change/delete headers
SMFIF_QUARANTINE =   0x0020 # quarantine envelope
SMFIF_CHGFROM =      0x0040 # change sender
SMFIF_ADDRCPT_PAR =  0x0080 # recipients & args
SMFIF_SETSYMLIST =   0x0100 # milter may request macros

# Commands the MTA shouldn't send:
SMFIP_NOCONNECT =  0x000001 # connection info
SMFIP_NOHELO =     0x000002 # HELO
SMFIP_NOMAIL =     0x000004 # MAIL from
SMFIP_NORCPT =     0x000008 # RCPT to
SMFIP_NOBODY =     0x000010 # body chunks
SMFIP_NOHDRS =     0x000020 # headers
SMFIP_NOEOH =      0x000040 # EOH
SMFIP_NOUNKNOWN =  0x000100 # unknown cmds
SMFIP_NODATA =     0x000200 # DATA
# MTA understands SMFIR_SKIP
SMFIP_SKIP =       0x000400
# MTA should send rejected recipients
SMFIP_RCPT_REJ =   0x000800
# Things that the MTA shouldn't expect replies to:
SMFIP_NR_HDR =     0x000080 # headers
SMFIP_NR_CONN =    0x001000 # connection info
SMFIP_NR_HELO =    0x002000 # HELO
SMFIP_NR_MAIL =    0x004000 # MAIL from
SMFIP_NR_RCPT =    0x008000 # RCPT to
SMFIP_NR_DATA =    0x010000 # DATA
SMFIP_NR_UNKN =    0x020000 # unknown cmds
SMFIP_NR_EOH =     0x040000 # EOH
SMFIP_NR_BODY =    0x080000 # body chunks
SMFIP_HDR_LEADSPC =0x100000 # header value has leading space
# Dunno what this is:
SMFIP_MDS_256K = 0x10000000 # MILTER_MAX_DATA_SIZE = 256K
SMFIP_MDS_1M =   0x20000000 # MILTER_MAX_DATA_SIZE 1M

# Used to figure out when we need to send acknowledgements.
SMFIC_TO_SMFIP = dict(
        SMFIC_HEADER    = SMFIP_NR_HDR,
        SMFIC_CONNECT   = SMFIP_NR_CONN,
        SMFIC_HELO      = SMFIP_NR_HELO,
        SMFIC_MAIL      = SMFIP_NR_MAIL,
        SMFIC_RCPT      = SMFIP_NR_RCPT,
        SMFIC_DATA      = SMFIP_NR_DATA,
        SMFIC_UNKNOWN   = SMFIP_NR_UNKN,
        SMFIC_EOH       = SMFIP_NR_EOH,
        SMFIC_BODY      = SMFIP_NR_BODY
    )

def to_host(value):
    """Basically a passthrough."""
    return value

def to_host_list(value):
    """Space separated list of FQDNs."""
    return value.split()

class ServerConfigLoader(StreamParsingLoader):
    
    CONFIG_FIRST_WORDS = set('CASE HOST PORT LOGGING DEBUG SMTP LOCAL HOST'.split())
    CONFIG_SECOND_WORDS = dict(CASE=['SENSITIVE'],DEBUG=['ACCOUNT'],SMTP=['HOST','PORT'],LOCAL=['HOST','DOMAINS'])
    CONFIG_MAP = {
            'CASE SENSITIVE': ('case_sensitive', to_boolean),
            'HOST': ('host', to_address),
            'PORT': ('port', to_port),
            'SMTP HOST': ('smtp_host', to_host),
            'SMTP PORT': ('smtp_port', to_port),
            'LOCAL HOST': ('local_host', to_host),
            'LOGGING': ('logging', to_loglevel),
            'DEBUG ACCOUNT': ('debug_account', to_account),
            'LOCAL DOMAINS': ('local_domains', to_host_list)
        }

class Configuration(BaseConfiguration):
    
    @property
    def smtp_host(self):
        return self.config['smtp_host']

    @property
    def smtp_port(self):
        return self.config['smtp_port']
    
    @property
    def local_host(self):
        return self.config.get('local_host', None)

    @property
    def local_domains(self):
        return self.config.get('local_domains', None)

class NoAccountNameException(Exception):
    pass
class NoDomainNameException(Exception):
    pass

class Recipient(object):
    """The target of one RCPT command."""
    def __init__(self, rcpt):
        self.rcpt = rcpt
        self.parsed = rcpt[rcpt.find('<')+1:rcpt.rfind('>')].split('@')
        self.alias = None
        return
    
    def name(self):
        """Extract the account name from the rcpt."""
        acct = self.parsed[0].strip()
        if not len(acct):
            raise NoAccountNameException('No account found in "{}"'.format(self.rcpt))
        return acct
    
    def domain(self):
        """Extract the domain from the rcpt."""
        fqdn = self.parsed[-1].strip()
        if not len(fqdn):
            raise NoDomainNameException('No domain found in "{}"'.format(self.rcpt))
        return fqdn
    
    def set_alias(self, alias):
        self.alias = '<' + '@'.join([alias] + self.parsed[1:]) + '>'
        return
    
    def set_noalias(self):
        self.alias = self.rcpt
        return

class CapabilitiesMissingException(Exception):
    pass

class MilterServer(object):
    
    SMFIC_CONTEXT_RESET = set((SMFIC_ABORT, SMFIC_EOB, SMFIC_QUIT, SMFIC_QUIT_NC))
    
    VERSION = 6
    ACTIONS = SMFIF_ADDRCPT | SMFIF_DELRCPT
    PROTO_EXTS = (SMFIP_NOCONNECT | SMFIP_NOHELO | SMFIP_NOMAIL | SMFIP_NOBODY | SMFIP_NOHDRS |
                  SMFIP_NOEOH | SMFIP_NR_HDR | SMFIP_NOUNKNOWN | SMFIP_NODATA | SMFIP_NR_CONN |
                  SMFIP_NR_HELO | SMFIP_NR_MAIL | SMFIP_NR_DATA |
                  SMFIP_NR_UNKN | SMFIP_NR_EOH | SMFIP_NR_BODY
                 )
    
    def __init__(self, smtp_connection, domains):
        """A Milter Server context.
        
        smtp_connection is probably poorly named if you want to use some other source of identity
        truth besides calling SMTP VRFY. Since this is an asynchronous framework, the notion is
        that this connection guarantees and is guaranteed a single stateful conversation with a
        single other conversant. In other words, you issue an SMTP command you get an SMTP answer.
        It is context to the milter server connection since conceptually each milter server instance
        needs its own connection to the identity service in order to maintain the contract. It will
        be supplied to the service_requests() validate_account() callback to query the identity
        service with.
        
        domains is our local delivery domains. These are the only domains for which Trualias
        expansion and subsequent VRFY validation are attempted. All others pass the milter without
        intermediation.
        """
        self.smtp = smtp_connection
        self.domains = set((domain.lower() for domain in domains))
        self.recipients = []
        self.command = None
        self.eof = False
        return
        
    async def read_command(self, reader):
        buffered = await reader.read(4)
        if len(buffered) == 0:
            return False
        cmd_len = int.from_bytes(buffered[:4], **UNSIGNED_BIG_ENDIAN)
        self.command = await reader.read(cmd_len)
        if len(buffered) == 0:
            return False
        return True
    
    async def write_command(self, writer, command, strings=None, data=None):
        # Convert data to strings, if any.
        if not data:
            if strings is None:
                strings = []
            if isinstance(strings, str):
                strings = [ strings ]
            data = b''.join(( s.encode() + b'\0' for s in strings ))
        message = command.encode() + data
        message = len(message).to_bytes(4, **UNSIGNED_BIG_ENDIAN) + message
        writer.write(message)
        await writer.drain()
        return

    @staticmethod
    def unpack_strings(packed_strings):
        strings = [ s.decode() for s in packed_strings.split(b'\0') ]
        # A python artifact.
        if len(strings[-1]) == 0:
            del strings[-1:]
        return strings
        
    async def service_requests(self, reader, writer, loop, check_trualias, verify_account):
        """Handle all milter requests on a connection."""
        
        # Read enough for a command.
        while await self.read_command(reader):
            print('Read a command...')

            command = self.command
            cmd = command[:1].decode()
            command = self.command[1:]
            
            # Option Negotiation
            if  cmd == SMFIC_OPTNEG:
                print('OPTNEG')
                version = int.from_bytes(command[:4],**UNSIGNED_BIG_ENDIAN)
                if version != self.VERSION:
                    raise CapabilitiesMissingException('Needs version {}  offered {}'.format(
                                                        self.VERSION, version))
                actions_offered = int.from_bytes(command[4:8],**UNSIGNED_BIG_ENDIAN)
                protocol_exts_offered = int.from_bytes(command[8:12],**UNSIGNED_BIG_ENDIAN)
                
                if actions_offered & self.ACTIONS != self.ACTIONS:
                    raise CapabilitiesMissingException('Needs SMFIF_* {:06x}  offered {:06x}'.format(
                                                        self.ACTIONS, actions_offered & self.ACTIONS))
                self.negotiated_proto_exts = protocol_exts_offered & self.PROTO_EXTS
                
                await self.write_command( writer, SMFIC_OPTNEG,
                                          data=self.VERSION.to_bytes(4, **UNSIGNED_BIG_ENDIAN) +
                                               self.ACTIONS.to_bytes(4, **UNSIGNED_BIG_ENDIAN) +
                                               self.negotiated_proto_exts.to_bytes(4, **UNSIGNED_BIG_ENDIAN)
                                        )
            # RCPT
            elif cmd == SMFIC_RCPT:
                print('RCPT')
                for recipient in ( Recipient(s) for s in self.unpack_strings(command) if len(s) ):
                    
                    # Local delivery only!
                    if recipient.domain().lower() not in self.domains:
                        recipient.set_noalias()
                        self.recipients.append(recipient)
                        continue
                    
                    # Run it through trualias.
                    try:
                        result = check_trualias(recipient.name())
                        if result:
                            recipient.set_alias(result)
                        else:
                            recipient.set_noalias()
                    except NoAccountNameException:
                        # This exception is generated by recipient.name().
                        recipient.set_noalias()
                        
                    print('rcpt: {}    alias: {}'.format(recipient.rcpt, recipient.alias))
                    
                    # This callback may die with its own special Exception, which we are
                    # not catching here. That Exception is for the case where the failing
                    # status is an unexpected one and might indicate misbehavior of the
                    # underlying service.
                    if await verify_account(recipient.alias, self.smtp):
                        self.recipients.append(recipient)
                        await self.write_command( writer, SMFIR_CONTINUE, None )
                    else:
                        # Bad recipient
                        await self.write_command( writer, SMFIR_REJECT, None )
            
            # EOB
            elif cmd == SMFIC_EOB:
                print('EOB')
                for recipient in self.recipients:
                    if recipient.rcpt != recipient.alias:
                        await self.write_command( writer, SMFIR_DELRCPT, recipient.rcpt)
                        await self.write_command( writer, SMFIR_ADDRCPT, recipient.alias)
                
                await self.write_command( writer, SMFIR_CONTINUE, None )
                
                # Fall through...

            # Close / Abort / EOB
            if   cmd in self.SMFIC_CONTEXT_RESET:
                self.recipients = []

            # If it's not a command we care about, do we need to acknowledge it?
            elif cmd in SMFIC_TO_SMFIP and not self.negotiated_proto_exts & SMFIC_TO_SMFIP[cmd]:
                await self.write_command( writer, SMFIR_CONTINUE, None )
        
        return
    
    