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

"""Internal components of the verified alias service.

There are four major components:

    config:        Components for representation of a configuration and
                   querying a configuration.
    parser:        Components for parsing a configuration from text.
    controller:    Receiving and dispatching requests and responses, and
                   orchestrating use of resources to generate responses for
                   requests.
    lookup:        Machinery for resolving a supplied name based on the
                   configuration.
"""

import logging
from ipaddress import ip_address

CASE_SENSITIVE = False
HOST = ip_address('127.0.0.1')
PORT = 3047
LOGGING = logging.WARNING
DEBUG_ACCOUNT = None

class Loader(object):
    """Base class for all config generators/loaders."""
    pass

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

class EndOfIterable(object):
    """Something used by TestableIterator to determine the end of an iterable."""
    pass
    
class TestableIterator(object):
    """An iterator which can be tested to see if it will return something."""
    def __init__(self, iterable, empty_flag=EndOfIterable()):
        self.iterator = iter(iterable)
        self.length = len(iterable)
        self.empty_flag = empty_flag
        self.item = next(self.iterator, empty_flag)
        return
    
    def __len__(self):
        return self.length
    
    def __call__(self):
        """Returns True if the next item is not equal to the empty_flag."""
        return not isinstance(self.item, EndOfIterable)
    
    def next(self, lookahead=False):
        if lookahead:
            return self.item
        item = self.item
        self.item = next(self.iterator, self.empty_flag)
        return item

class WrappedFunctionResult(object):
    """A wrapper for function results which provides a boolean test.
    
    The success property will provide true/false based on testing the result.
    """
    def __call__(self, result):
        self.result = result
        return self
    
    @property
    def success(self):
        return self.check_for_success()
    
    def check_for_success(self):
        """Subclasses must implement this to test the result for success / failure."""
        pass
    
class BasicBooleanResult(WrappedFunctionResult):
    """Something which implicitly returns true/false when tested as a boolean."""
    
    def check_for_success(self):
        return self.result and True or False
    