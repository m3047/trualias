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

import sys
import unittest

if '..' not in sys.path:
    sys.path.insert(0,'..')

from trualias.lookup import LookupThing
import trualias.config as config
import trualias.parser as parser

def parse(text):
    return config.from_text(parser.MultilineStringLoader(text), raise_on_error=False)

CONFIG = """
    LOGGING: warning
    DEBUG ACCOUNT: debug_account
    
    ACCOUNT foo, bar
    MATCHES %account%-%alnum%-%code%
    WITH DIGITS(), ANY(), VOWELS();
    
    ACCOUNT foo
    ALIASED griselda, pinky
    MATCHES %alias%-%ident%-%code%
    WITH ANY(), ANY(), CHAR(1,*);
"""

class TestAliasNameLookup(unittest.TestCase):
    """Try various things like we were a service trying to find delivery addresses."""
    
    def setUp(self):
        self.config = parse(CONFIG)
        self.looker = LookupThing(self.config)
        return
    
    def test_config_error(self):
        self.assertFalse(self.config.error)     # When raise_on_error=False
        return
    
    def test_fail(self):
        self.assertEqual(self.looker.find('hello'),'')
        return

    def test_account_bar(self):
        self.assertEqual(self.looker.find('bar-none-0n2'),'bar')
        return
    
    def test_account_foo(self):
        self.assertEqual(self.looker.find('foo-23skidoo-2k3'),'foo')
        return

    def test_alias_griselda(self):
        self.assertEqual(self.looker.find('griselda-23-skidoo-3k2'),'foo')
        return
    
if __name__ == '__main__':
    unittest.main(verbosity=2)
    
