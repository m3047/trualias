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

The central fixture of this module is the Configuration. A function
from_text() is provided to parse a configuration from text.
"""

import logging

from .config_base import ConfigurationError, Loader, DEFAULT_CONFIG
from .alias import SemanticError
from .parser import StreamParsingLoader

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
    
    @property
    def statistics(self):
        return self.config['statistics']
    
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
        
        It may be useful to read inline comments in this method.
        
        FEEDBACK / TEST CASES ENCOURAGED: This is all about edge cases. The cases considered
        here are probably safe, and also probably overly restrictive.
        """
        
        # ACCOUNTS...
        for account in self.accounts:
            
            associated_aliases = self.associated_aliases(account)
            
            for spec in self.accounts[account]:

                # Has no aliases.
                #
                # Ok if:
                #     * 'account' in the matchex
                #   or
                #     * matchex is unique
                #
                if not associated_aliases:
                    if 'account' in spec.matchex.tokens or spec.matchex.unique:
                        continue
                    raise SemanticError('Ambiguous because the account is not present and expression not unique {}'.format(spec.matchex.expression_),
                                        additional=dict(line_number=spec.matchex.line_number)
                                       )
                    
                # Account and alias are uniquely paired.
                #
                # Ok if:
                #     * alias has one account
                #   and
                #     * account has one alias
                #   and
                #       * 'account' in matchex
                #     or
                #       * 'alias' in matchex
                #     or
                #       * matchex is unique
                #
                if len(associated_aliases) == 1 and len(self.associated_accounts(tuple(associated_aliases)[0])) == 1:
                    if 'account' in spec.matchex.tokens or 'alias' in spec.matchex.tokens or spec.matchex.unique:
                        continue
                    raise SemanticError('Ambiguous because neither account or alias is present and expression not unique {}'.format(spec.matchex.expression_),
                                        additional=dict(line_number=spec.matchex.line_number)
                                       )

                # Many aliases
                # 
                # Ok if:
                #     * alias has one account
                #   and
                #       * 'alias' in matchex
                #     or
                #       * no aliases for this spec (some other spec has aliases)
                #
                for alias in associated_aliases:
                    if len(self.associated_accounts(tuple(associated_aliases)[0])) == 1:
                        if 'alias' in spec.matchex.tokens or not spec.aliases:
                            continue
                        raise SemanticError('Ambiguous because alias is not present {}'.format(spec.matchex.expression_),
                                            additional=dict(line_number=spec.matchex.line_number)
                                       )

        # ALIASES
        
        # Alias has many accounts.
        #
        # Ok if:
        #     * 'account' in matchex
        #   and
        #     * 'alias' in matchex
        #
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

    
