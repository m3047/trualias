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

"""All about configurations.

The central fixture of this module is the Configuration.
"""

import logging
from ipaddress import ip_address
from io import StringIO

CASE_SENSITIVE = False
HOST = ip_address('127.0.0.1')
PORT = 3047
LOGGING = logging.WARNING
DEBUG_ACCOUNT = None

def DEFAULT_CONFIG(minimal=False):
    """A function so that it generates a fresh one every time.
    
    Minimal causes the dictionary to be suitable for updating another
    config.
    """
    
    if minimal:
        config = dict()
    else:
        config = dict(
                    case_sensitive=CASE_SENSITIVE,
                    host=HOST,
                    port=PORT,
                    logging=LOGGING,
                    debug_account=DEBUG_ACCOUNT
                 )
    config['aliases'] = []
    return config

class ConfigurationError(Exception):
    """An invalid/inconsistent configuration."""
    def __init__(self, reason, additional=None):
        self.reason = reason
        self.additional = additional or []
        return
    
    def __str__(self):
        return '{} ({})'.format(self.reason,
                                ', '.join('{}:{}'.format(k,str(self.additional[k])) for k in self.additional.keys())
                               )
        
class ParseError(ConfigurationError):
    """A parsing error occurred."""
    pass

class SemanticError(ConfigurationError):
    """A semantic error occurred."""
    pass

BOOLEAN_VALUE = { 'true':True, '1':True, 'false':False, '0':False }

def to_boolean(value):
    """Map 0/1 and true/false as boolean values."""
    orig_value = value
    value = value.lower()
    if value not in BOOLEAN_VALUE:
        raise ValueError('Not a recognized boolean value: {}'.format(orig_value))
    return BOOLEAN_VALUE[value]

def to_host(value):
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

class Matcher(object):
    """Matches stuff in the address."""
    def __init__(self,*char_sets):
        self.char_sets = char_sets
        return
    
    def __call__(self, address, start_pos=0):
        """Returns a (zero based) starting and ending position tuple."""
        if len(self.char_sets) == 1:
            start_chars = self_char_sets[0]
            middle_chars = self_char_sets[0]
            end_chars = self_char_sets[0]
        else:
            start_chars, middle_chars, end_chars = char_sets

        while start_pos < len(address) and address[start_pos] not in start_chars:
            start_pos += 1
        if start_pos >= len(address):
            return None

        valid_end_pos = start_pos
        test_pos = start_pos
        while test_pos < len(address):
            test_char = address[test_pos]
            if test_char in end_chars:
                valid_end_pos = test_pos
            if test_char not in middle_chars:
                break
            test_pos += 1
        
        return (start_pos, valid_end_pos)
    
class MatchAny(Matcher):
    """Matches anything and everything!
    
    Subclassed from Matcher for no good functional but every good
    nonfunctional reason.
    """
    def __init__(self):
        return
    
    def __call__(self, address, start_pos=0):
        return 0, (len(address) - 1)

MATCH_ALPHA = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
MATCH_NUMBER = set('1234567890')
MATCH_ALNUM = MATCH_ALPHA | MATCH_NUMBER
MATCH_FQDN = MATCH_ALNUM | set('.-')
MATCH_IDENT = MATCH_ALNUM | set('_')

class MatchExpression(object):
    """A match expression."""
    DEFAULT_ACCOUNT_MATCH = 'ident'
    IDENT_MATCHERS = dict(   alnum=Matcher(MATCH_ALNUM),
                             alpha=Matcher(MATCH_ALPHA),
                             number=Matcher(MATCH_NUMBER),
                             ident=Matcher(MATCH_IDENT,MATCH_IDENT|set('-'),MATCH_IDENT),
                             fqdn=Matcher(MATCH_IDENT,MATCH_FQDN,MATCH_IDENT)
                           )
    ALL_MATCHERS = dict( IDENT_MATCHERS,
                             account=Matcher(MATCH_IDENT),
                             alias=Matcher(MATCH_IDENT),
                             code=MatchAny()
                       )
    FRIENDLIES = { 'alpha', 'number' }
    
    def __init__(self):
        self.account_matcher = self.DEFAULT_ACCOUNT_MATCH
        return
    
    def __str__(self):
        return self.expression_
    
    @property
    def account_matcher(self):
        return self.account_matcher_
    
    @account_matcher.setter
    def account_matcher(self, value):
        if value not in self.IDENT_MATCHERS:
            self.parse_error('Unrecognized identifier matcher: "{}"'.format(value))
        self.account_matcher_ = value
        self.ALL_MATCHERS['account'] = self.IDENT_MATCHERS[self.account_matcher_]
        self.ALL_MATCHERS['alias'] = self.IDENT_MATCHERS[self.account_matcher_]
        return
    
    @property
    def expression(self):
        return self.expression_
    
    @expression.setter
    def expression(self, value):
        """Compile the match expression while checking for semantic validity.
        
        Semantic validity chiefly means that only alpha and number can occur
        adjacent to each other.
        """
        if isinstance(value,tuple):
            value, self.line_number = value
        self.identifiers = 0
        self.fqdns = set()
        input_tokens = value.split('%')
        tokens = []
        state = ''
        outside = False
        i = 0
        for tok in input_tokens:
            i += 1
            outside ^= True
            if outside:
                if not tok and i+1 < len(input_tokens) and not input_tokens[i+1]:
                    tokens.append('%')
                else:
                    tokens.append(tok)
                if tok:
                    state = ''
            else:
                if not tok:
                    if i > 0 and not input_tokens[i-1]:
                        continue
                    else:
                        self.semantic_error('Empty matchvalue.')
                else:
                    if tok not in self.ALL_MATCHERS:
                        self.semantic_error('Unrecognized matchvalue "{}".'.format(tok))
                    if state == 'poison':
                        self.semantic_error('"{}" cannot occur next to any other matcher.'.format(tok))
                        
                    if tok in self.FRIENDLIES:
                        if tok == state:
                            self.semantic_error('"{}" cannot occur next to itself.'.format(tok))
                        state = tok
                    else:
                        if state in self.FRIENDLIES:
                            self.semantic_error('"{}" cannot occur next to any other matcher.'.format(tok))
                        state = 'poison'
                        
                    if tok in self.IDENT_MATCHERS:
                        self.identifiers += 1
                        if tok == 'fqdn':
                            self.fqdns.add(self.identifiers)
                        
                    tokens.append(tok)

        self.tokens = tokens
        self.expression_ = value
        return
    
    def semantic_error(self, reason, **kwargs):
        additional = dict(line_number=self.line_number)
        additional.update(kwargs)
        raise SemanticError(reason, additional)

    def match(self, accounts, aliases, address):
        # TODO: yes!!
        pass
    
class CalcExpression(object):
    """A Calculation Expression.
    
    Does a few arguably pointless things to be DWIMmy, such as being subscriptable.
    """
    
    def __init__(self):
        self.calcs_ = []
        return
    
    def __getitem__(self,i):
        """Implemented this to simplify writing test cases."""
        return self.calcs_[i]
    
    def __len__(self):
        """For test cases."""
        return len(self.calcs_)
    
    @property
    def calcs(self):
        return self.calcs_
    
    @calcs.setter
    def calcs(self,value):
        if isinstance(value,tuple):
            value, self.line_number = value
        self.calcs_ = value
        return
    
    def semantic_error(self, reason, **kwargs):
        additional = dict(line_number=self.line_number)
        additional.update(kwargs)
        raise SemanticError(reason, additional)

    def semantic_check(self, matchex):
        """Checks that the calc is valid with the match expression.
        
        Chiefly this consists of checking reference bounds and number of arguments.
        Some things cannot be caught (e.g. label indices) as they are dependent on the
        input (account) being matched.
        """
        n_identifiers = matchex.identifiers
        for calc in self.calcs:
            func = calc[0]
            args = calc[1:]
            needs_ident_subscript = n_identifiers > 1
            if func == 'CHAR':
                if len(args) > 4:
                    self.semantic_error('{} requires at most 4 arguments with {}'.format(func, matchex.expression))
                if needs_ident_subscript:
                    if len(args) < 3:
                        self.semantic_error('{} requires an identifier subscript with {}'.format(func, matchex.expression))
                    i_ident = int(args[0])
                    if i_ident < 1 or i_ident > n_identifiers:
                        self.semantic_error('{} index must be between 1 and {} with {}'.format(func, n_identifiers, matchex.expression))
                    if len(args) == 4:
                        if i_ident not in matchex.fqdns:
                            self.semantic_error('{} index {} does not reference an fqdn in {}'.format(func, i_ident, matchex.expression))
                    else:
                        if i_ident in matchex.fqdns:
                            self.semantic_error('{} index {} references an fqdn and needs a label index with {}'.format(func, i_ident, matchex.expression))
                else:
                    if len(args) < 2:
                        self.semantic_error('{} requires at least 2 arguments with {}'.format(func, matchex.expression))
                    if len(args) == ((1 in matchex.fqdns) and 4 or 3) and int(args[0]) != 1:
                        self.semantic_error('{} must have index of 1 with {}'.format(func, matchex.expression))
                for i in range(len(calc)-2):
                    calc[i+1] = int(calc[i+1])
            else:
                if len(args) > 1:
                    self.semantic_error('{} requires at most 1 argument with {}'.format(func, matchex.expression))
                if needs_ident_subscript:
                    if len(args) < 1:
                        print(self.calcs)
                        self.semantic_error('{} requires an identifier subscript with {}'.format(func, matchex.expression))
                    i_ident = int(args[0])
                    if i_ident < 1 or i_ident > n_identifiers:
                        self.semantic_error('{} index must be between 1 and {} with {}'.format(func, n_identifiers, matchex.expression))
                else:
                    if len(args) and int(args[0]) != 1:
                        self.semantic_error('{} must have index of 1 with {}'.format(func, matchex.expression))
                if len(calc) > 1:
                    calc[1] = int(calc[1])
        return

class Alias(object):
    """A single alias specification.
    
    Has the following properties:
    
      accounts:         local delivery accounts
      aliases:          aliases
      matchex:          the match expression
      calc:             the calculation
    """
    
    def __init__(self):
        self.accounts = []
        self.aliases = []
        self.matchex = MatchExpression()
        self.calc = CalcExpression()
        return
    
    def __str__(self):
        return '<accounts:{}  aliases:{}  matches:{}  calc:{}>'.format(
               self.accounts, self.aliases, self.matchex, self.calc)
        
    def semantic_check(self):
        """Makes sure that the match expression and calc are semantically valid.
        
        The match expression itself is checked for consistency when it is
        saved.
        """
        self.calc.semantic_check(self.matchex)
        return
    
class Loader(object):
    """Base class for all config generators/loaders."""
    pass

class StreamParsingLoader(Loader):
    """Creates a configuration dictionary by parsing a text stream.
    
    Configuration.load() will call our load(). Subclasses may need
    to override read_line().
    """

    CONFIG_FIRST_WORDS = set('CASE HOST PORT LOGGING DEBUG'.split())
    CONFIG_SECOND_WORDS = dict(CASE='SENSITIVE',DEBUG='ACCOUNT')
    CONFIG_MAP = {
            'CASE SENSITIVE': ('case_sensitive', to_boolean),
            'HOST': ('host', to_host),
            'PORT': ('port', to_port),
            'LOGGING': ('logging', to_loglevel),
            'DEBUG ACCOUNT': ('debug_account', to_account)
        }
    CALC_FUNC_NAMES = set('DIGITS ALPHAS LABELS CHARS VOWELS ANY CHAR'.split())
    
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
        self.line_number += 1
        line = self.fh.readline()
        if not line:
            raise EOFError()
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
            if keyword != self.CONFIG_SECOND_WORDS[item]:
                self.parse_error('Unrecognized keyword "{}"'.format(keyword))
            self.token_matched()
            item += ' ' + keyword
        config_item = self.CONFIG_MAP[item]
        if not colon_seen:
            more  = self.token()
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
    
    def parameters(self):
        params = ''
        while ')' not in params:
            params += self.token()
            self.token_matched()
        params, more = self.trailing(')',params)
        self.token_ = more
        params = params.strip().split(',')
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
            params = self.parameters()
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

def from_text(stream,raise_on_error=False):
    """Convenience method loads a Configuration.
    
    Accepts either a stream/filehandle object (which can be turned into an
    instance of StreamParsingLoader) or else an instance of a subclass
    of Loader.
    """
    if not isinstance(stream, Loader):
        stream = StreamParsingLoader(stream)
        
    return Configuration().load(stream, raise_on_error)
        
class Configuration(object):
    """A Configuration and the means to query it."""
    
    def __init__(self):
        """Create an empty, default configuration.
        
        A new Configuration is empty except for some defaults. You will typically
        call load() to update the configuration.
        """
        self.config = DEFAULT_CONFIG()
        self.error = 'Not configured.'
        return

    @property
    def case_sensitive(self):
        return self.config['case_sensitive']
    
    @property
    def host(self):
        return self.config['host']
    
    @property
    def port(self):
        return self.config['port']
    
    @property
    def logging(self):
        return self.config['logging']
    
    @property
    def debug_account(self):
        return self.config['debug_account']
    
    def build_maps(self):
        """Builds the internal maps used by lookup methods.
        
        FLUENT: returns the object.
        """
        # Determine which match expressions are unique.
        expressions = {}
        for expr in (spec.matchex for spec in self.config['aliases']):
            if expr.expression_ in expressions:
                expressions[expr.expression_] += 1
            else:
                expressions[expr.expression_] = 1
        for expr in (spec.matchex for spec in self.config['aliases']):
            expr.unique = expressions[expr.expression_] == 1
            
        # Determine which accounts / aliases are referenced by which account declarations.
        self.accounts = {}
        self.aliases = {}
        self.alias_accounts = {}
        for spec in self.config['aliases']:
            for ident in spec.accounts:
                if ident in self.accounts:
                    self.accounts[ident].append(spec)
                else:
                    self.accounts[ident] = [spec]
            for ident in spec.aliases:
                if ident in self.aliases:
                    self.aliases[ident].append(spec)
                    self.alias_accounts[ident] |= set(spec.accounts)
                else:
                    self.aliases[ident] = [spec]
                    self.alias_accounts[ident] = set(spec.accounts)
                
        return self
    
    def update_config(self, new_config):
        """Update the current config with the contents of the new one.
        
        FLUENT: returns the object.
        """
        self.config.update(new_config)
        self.build_maps()
        return self
    
    def semantic_check(self):
        """Check the semantic validity of the configuration."""
        for alias in self.config['aliases']:
            alias.semantic_check()
        return
    
    def associated_aliases(self, account):
        """Return the aliases associated with an account."""
        aliases = []
        for spec in self.accounts[account]:
            aliases += spec.aliases
        return set(aliases)
        
    def associated_accounts(self, alias):
        """Return the accounts associated with an alias."""
        return self.alias_accounts[alias]
    
    def enforce_uniqueness(self):
        """Enforce semantic requirements for uniqueness.
        
        The tuple consisting of the following should be unique according to some
        definition which varies depending on the data:
        
        * account
        * alias
        * match expression
        """
        for account in self.accounts:
            
            associated_aliases = self.associated_aliases(account)
            
            for spec in self.accounts[account]:

                # Has no aliases.

                if not associated_aliases:
                    if 'account' in spec.matchex.tokens or spec.matchex.unique:
                        continue
                    raise SemanticError('Ambiguous because the account is not present and expression not unique {}'.format(spec.matchex.expression_),
                                        additional=dict(line_number=spec.matchex.line_number)
                                       )
                    
                # Account and alias are uniquely paired.

                if len(associated_aliases) == 1 and len(self.associated_accounts(tuple(associated_aliases)[0])) == 1:
                    if 'account' in spec.matchex.tokens or 'alias' in spec.matchex.tokens or spec.matchex.unique:
                        continue
                    raise SemanticError('Ambiguous because neither account or alias is present and expression not unique {}'.format(spec.matchex.expression_),
                                        additional=dict(line_number=spec.matchex.line_number)
                                       )

                # Many aliases
                
                for alias in associated_aliases:
                    if len(self.associated_accounts(tuple(associated_aliases)[0])) == 1:
                        if 'alias' in spec.matchex.tokens:
                            continue
                        raise SemanticError('Ambiguous because alias is not present {}'.format(spec.matchex.expression_),
                                            additional=dict(line_number=spec.matchex.line_number)
                                       )
                
        # Alias has many accounts.

        for alias in self.aliases:

            if len(self.associated_accounts(alias)) < 2:
                continue
        
            for spec in self.aliases[alias]:
                
                if 'account' in spec.matchex.tokens and 'alias' in spec.matchex.tokens:
                    continue
                raise SemanticError('Ambiguous because account and alias are not present {}'.format(spec.matchex.expression_),
                                    additional=dict(line_number=spec.matchex.line_number)
                                )
        return
    
    def load(self,loader,raise_on_error=False):
        """Use the loader to update the configuration.
        
        FLUENT: returns the object.
        """
        self.error = ''
        try:
            self.update_config(loader.load())
            self.semantic_check()
            self.enforce_uniqueness()
        except (ConfigurationError, ValueError) as e:
            if raise_on_error:
                raise e
            self.error = ' {}: {}'.format(str(type(e)).split('.')[-1].split("'")[0], e)
            logging.error(self.error)
        return self

    
