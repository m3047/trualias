#!/usr/bin/python3
# Copyright (c) 2019,2023 by Fred Morris Tacoma WA
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
    
    ACCOUNT foo
    MATCHES %account%.%ident%.%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT bar
    MATCHES %account%.%fqdn%.%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT ping
    MATCHES parsely.%ident%.%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT pong
    MATCHES eggplant.%fqdn%.%code%
    WITH ANY(), VOWELS(), ANY();
    
    ACCOUNT zip
    MATCHES walnut-%ident%-%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT zap
    MATCHES almond-%fqdn%-%code%
    WITH ANY(), VOWELS(), ANY();
"""

class TestFQDNvsIdent(unittest.TestCase):
    """Test interference between potentially ambiguous FQDNs and Idents."""
    
    def setUp(self):
        self.config = parse(CONFIG)
        self.looker = LookupThing(self.config)
        return
    
    def test_config_error(self):
        """Baseline check that the configuration parsed successfully."""
        self.assertFalse(self.config.error)     # When raise_on_error=False
        return
    
    def test_basic_lookups(self):
        """A successful test of each rule."""
        self.assertEqual(self.looker.find('foo.green.g2r'),'foo')
        self.assertEqual(self.looker.find('bar.green.beans.g4r'),'bar')
        self.assertEqual(self.looker.find('parsely.green.g2r'),'ping')
        self.assertEqual(self.looker.find('eggplant.green.beans.g4r'),'pong')
        self.assertEqual(self.looker.find('walnut-shrimp-s1m'),'zip')
        self.assertEqual(self.looker.find('almond-mocha.latte-t4l'),'zap')        
        return

    def test_extra_stuff(self):
        """Is extra trailing data being detected?"""
        self.assertEqual(self.looker.find('foo.green.g2rx'),'')
        self.assertEqual(self.looker.find('bar.green.beans.g4rxx'),'')
        self.assertEqual(self.looker.find('parsely.green.g2rxxx'),'')
        self.assertEqual(self.looker.find('eggplant.green.beans.g4rxxxx'),'')
        self.assertEqual(self.looker.find('walnut-shrimp-s1mxxxxx'),'')
        self.assertEqual(self.looker.find('almond-mocha.latte-t4lxxxxxx'),'')        
        return

if __name__ == '__main__':
    unittest.main(verbosity=2)
