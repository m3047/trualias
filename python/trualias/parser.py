#!/usr/bin/python3
# Copyright (c) 2019-2024 by Fred Morris Tacoma WA
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

"""This is the configuration parser.

Alias specifications (in the configuration) are parsed into sketches. Any
potential alias is them matched against each of the alias specifications
by trualias.lookup.find(). The actual parsing / matching of an alias against
the specifications is done by calling trualias.alias.Alias.match().
"""
import logging
from ipaddress import ip_address
from io import StringIO
import importlib

from .config_base import ConfigurationError, Loader, DEFAULT_CONFIG
from .alias import Alias, Subscriptable

class ParseError(ConfigurationError):
    """A parsing error occurred."""
    pass

class ProcessorError(ConfigurationError):
    """An error was encountered loading the pre/post processing module."""
    pass

BOOLEAN_VALUE = { 'true':True, '1':True, 'false':False, '0':False }

def to_boolean(value):
    """Map 0/1 and true/false as boolean values."""
    orig_value = value
    value = value.lower()
    if value not in BOOLEAN_VALUE:
        raise ValueError('Not a recognized boolean value: {}'.format(orig_value))
    return BOOLEAN_VALUE[value]

def to_address(value):
    return ip_address(value)

def to_port(value):
    orig_value = value
    value = int(value)
    if value < 0 or value >= 2**16:
        raise ValueError('Not valid for a port number: {}'.format(orig_value))
    return value

LOGGING_LEVELS = dict(debug=logging.DEBUG, info=logging.INFO, warning=logging.WARNING, error=logging.ERROR, critical=logging.CRITICAL)

def to_loglevel(value):
    orig_value = value
    value = value.lower()
    if value not in LOGGING_LEVELS:
        raise ValueError('Not a valid logging level: {}'.format(orig_value))
    return LOGGING_LEVELS[value]

BAD_ACCOUNT_LETTERS = set(' @')

def to_account(value):
    if not set(value).isdisjoint(BAD_ACCOUNT_LETTERS):
        raise ValueError('Not a valid account: {}'.format(value))
    return value

NO_STATISTICS = {'none','no'}

def to_statistics(value):
    if value.lower() in NO_STATISTICS:
        return None
    value = int(value)
    if value < 0:
        value = 0
    return value

REQUIRED_PROCESSOR_MODULE_ATTRIBUTES = "ACCOUNTS ALIASES reload preprocess postprocess".split()

def to_module(value):
    """Import a module and return a handle to it."""
    try:
        module = importlib.import_module(value)
    except Exception as e:
        raise ProcessorError('{}: {}'.format(type(e).__name__, e))
    for attr in REQUIRED_PROCESSOR_MODULE_ATTRIBUTES:
        if not hasattr(module, attr):
            raise ProcessorError('Processing module "{}" is missing "{}"'.format(module, attr))
    return module

class StreamParsingLoader(Loader):
    """Creates a configuration dictionary by parsing a text stream.
    
    Configuration.load() will call our load(). Subclasses may need
    to override read_line().
    """

    CONFIG_FIRST_WORDS = set('HOST PORT LOGGING DEBUG STATISTICS PYTHON_IS_311 PROCESSOR'.split())
    CONFIG_SECOND_WORDS = dict(DEBUG=['ACCOUNT'])
    CONFIG_MAP = {
            'PYTHON_IS_311': ('python_is_311', to_boolean),
            'PROCESSOR': ('processor', to_module),
            'HOST': ('host', to_address),
            'PORT': ('port', to_port),
            'LOGGING': ('logging', to_loglevel),
            'DEBUG ACCOUNT': ('debug_account', to_account),
            'STATISTICS': ('statistics', to_statistics)
        }
    CALC_FUNC_NAMES = set('DIGITS ALPHAS LABELS CHARS VOWELS ANY NONE CHAR'.split())
    NONINTEGER_PARAM_VALUES = Subscriptable.NONINTEGER_PARAM_VALUES
    
    def __init__(self, fh):
        """Create a loader for the supplied filehandle."""
        self.fh = fh
        self.line_number = 0
        self.buffer = ''
        self.token_ = None
        self.config = DEFAULT_CONFIG(minimal=True)
        return
    
    def parse_error(self, reason, **kwargs):
        additional = dict(line_number=self.line_number)
        additional.update(kwargs)
        raise ParseError(reason, additional)
    
    def load(self):
        """Load and parse the stream."""
        try:
            while self.statement():
                pass
            if self.token_ or self.buffer or self.fh.readline():
                additional = {}
                if self.token_:
                    additional['token'] = self.token_
                if self.buffer:
                    additional['buffer'] = self.buffer
                self.parse_error("Data remains in buffer.", **additional)
        except EOFError:
            pass
        if self.partial:
            self.parse_error("Unexpected end of file.")
        return self.config
    
    def read_line(self):
        """Reads one line from the stream.
        
        Read one line and return it.
        
        The newline characters should be stripped and replaced with
        (a single) white space.
        """
        while True:
            self.line_number += 1
            line = self.fh.readline()
            if not line:
                raise EOFError()
            if line.lstrip().startswith('#'):
                continue
            return line.rstrip() + ' '

    ## Parser components below here. ##
    
    def statement(self):
        """Any statement."""
        #print('statement...')
        self.partial = False
        success = self.config_statement() or self.alias_spec()
        #print('...success: {}'.format(success))
        if success:
            self.partial = False
        return success
    
    @staticmethod
    def trailing(token,item):
        """Looks for a trailing instance of token in item."""
        checked = item.split(token,maxsplit=1)
        return checked[0], (len(checked) > 1) and checked[1] or ''
    
    def config_statement(self):
        #print('config statement. in buffer: {}'.format(self.buffer))
        item = self.token()
        colon_seen = ':' in item
        item, more = self.trailing(':',item)
        if item not in self.CONFIG_FIRST_WORDS:
            return False
        self.token_matched()
        self.partial = True
        if item in self.CONFIG_SECOND_WORDS:
            if more:
                self.parse_error('Keyword error "{}".'.format(item))
            keyword = self.token()
            colon_seen = ':' in keyword
            keyword, more = self.trailing(':',keyword)
            if keyword not in self.CONFIG_SECOND_WORDS[item]:
                self.parse_error('Unrecognized keyword "{}"'.format(keyword))
            self.token_matched()
            item += ' ' + keyword
        if item not in self.CONFIG_MAP:
            self.parse_error('Unrecognized item "{}"'.format(item))
        config_item = self.CONFIG_MAP[item]
        if not colon_seen:
            more = self.token()
            self.token_matched()
            if not more.startswith(':'):
                self.parse_error('Invalid syntax for {}'.format(item))
            discard, more = self.trailing(':', more)
        self.config[config_item[0]] = config_item[1]((more + ' ' + self.buffer).strip())
        self.buffer = ''
        return True
        
    def alias_spec(self):
        #print('alias spec...')
        item = self.token()
        if item != 'ACCOUNT':
            return False
        self.token_matched()
        self.partial = True

        spec = Alias()
        
        # One or more accounts, until we see USING, ALIASED or MATCHES.
        spec.accounts = self.accounts_or_aliases()
        
        item = self.token()
        if item == 'USING':
            self.token_matched()
            item == self.token()
            spec.matchex.account_matcher = item
            self.token_matched()
        
            item = self.token()
        
        if item == 'ALIASED':
            self.token_matched()
            spec.aliases = self.accounts_or_aliases()
            
            item = self.token()
            
        if item != 'MATCHES':
            self.parse_error('Syntax Error: Unrecognized keyword "{}" expecting "MATCHES"'.format(item))
        
        self.token_matched()
        
        spec.matchex.expression = (self.token(), self.line_number)
        self.token_matched()
        
        item = self.token()
        if item != 'WITH':
            self.parse_error('Syntax Error: Unrecognized keyword "{}" expecting "WITH"'.format(item))
        self.token_matched()
        
        spec.calc.calcs = (self.calcs(), self.line_number)
        
        item = self.token()
        if not item.startswith(';'):
            self.parse_error('Syntax Error: Expected end of a spec, found "{}"'.format(item))
        if len(item) > 1:
            self.token_ = self.token_[1:]
        else:
            self.token_matched()
        
        self.config['aliases'].append(spec)

        return True
        
    def accounts_or_aliases(self):
        """Runs of comma-separated idents."""
        accounts = self.token()
        self.token_matched()
        item = self.token()
        while accounts.endswith(',') or item.startswith(','):
            self.token_matched()
            accounts += item
            item = self.token()
        return accounts.split(',')
    
    def parameters(self, func):
        params = ''
        while ')' not in params:
            params += self.token()
            self.token_matched()
        params, more = self.trailing(')',params)
        self.token_ = more
        params = params.strip().split(',')
        try:
            if func.upper() == 'CHAR':
                if len(params) < 2:
                    self.parse_error('CHAR() requires a minimum of two arguments.')
                if len(params) == 3:
                    if params[0].lower() not in self.NONINTEGER_PARAM_VALUES:
                        param = params[0]
                        param and int(param)
                else:
                    for param in params[:-1]:
                        param and int(param)
            else:
                if len(params) > 1:
                    self.parse_error('{}() requires no more than one argument.'.format(func.upper()))
                if len(params):
                    param = params[0]
                    if param.lower() not in self.NONINTEGER_PARAM_VALUES:
                        param and int(param)
        except ValueError:
                self.parse_error('Invalid calc parameter "{}" must be integer or "account" or "alias"'.format(param))
        return (len(params) != 1 or params[0]) and params or []

    def calcs(self):
        calc_list = []
        while True:
            item = self.token()
            func, item = self.trailing('(',item)
            if func not in self.CALC_FUNC_NAMES:
                self.parse_error('Unrecognized calc function: {}'.format(func))
            self.token_matched()
            self.token_ = item
            params = self.parameters(func)
            calc_list.append([func]+params)
            item = self.token()
            if item.startswith(','):
                self.token_ = item[1:]
            else:
                break
        return calc_list
    
    def token_matched(self):
        self.token_ = None
        return
    
    def token(self):
        if self.token_:
            return self.token_
        while True:
            if not self.buffer:
                self.buffer = self.read_line()
            try:
                tok, more = self.buffer.split(maxsplit=1)
            except ValueError:
                tok = self.buffer.strip()
                more = ''
            if not tok:
                self.buffer = ''
                continue
            self.token_ = tok
            self.buffer = more
            return tok

class MultilineStringLoader(StreamParsingLoader):
    """A StreamParsingLoader which takes a multiline string.
    
    This is used for testing.
    """
    def __init__(self, text):
        """Create a loader for the supplied multiline string."""
        self.fh = StringIO(text)
        self.line_number = 0
        self.buffer = ''
        self.token_ = None
        self.config = DEFAULT_CONFIG(minimal=True)
        return
