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
import trualias.alias as alias

def parse(text):
    return config.from_text(parser.MultilineStringLoader(text), raise_on_error=False)

CONFIG = """
    LOGGING: warning
    DEBUG ACCOUNT: debug_account
    
    ACCOUNT foo
    MATCHES %account%.%ident%.%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT foo
    MATCHES %account%.%code%.%ident%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT foo
    MATCHES %code%.%account%.%ident%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT bar
    MATCHES %account%.%fqdn%.%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT bar
    MATCHES %account%.%code%.%fqdn%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT bar
    MATCHES %code%.%account%.%fqdn%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT ping
    MATCHES parsely.%ident%.%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT ping
    MATCHES parsely.%code%.%ident%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT ping
    MATCHES %code%.parsely.%ident%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT pong
    MATCHES eggplant.%fqdn%.%code%
    WITH ANY(), VOWELS(), ANY();
    
    ACCOUNT pong
    MATCHES eggplant.%code%.%fqdn%
    WITH ANY(), VOWELS(), ANY();
    
    ACCOUNT pong
    MATCHES %code%.eggplant.%fqdn%
    WITH ANY(), VOWELS(), ANY();
    
    ACCOUNT zip
    MATCHES walnut-%ident%-%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT zip
    MATCHES walnut-%code%-%ident%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT zip
    MATCHES %code%-walnut-%ident%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT zap
    MATCHES almond-%fqdn%-%code%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT zap
    MATCHES almond-%code%-%fqdn%
    WITH ANY(), VOWELS(), ANY();

    ACCOUNT zap
    MATCHES %code%-almond-%fqdn%
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

    def test_ident_underscores(self):
        """Underscores and dashes alone and in various combinations."""
        self.assertEqual(self.looker.find('foo.ab.a1b'),'foo')
        self.assertEqual(self.looker.find('foo.a_b.a1b'),'foo')
        self.assertEqual(self.looker.find('foo.a__b.a1b'),'foo')
        self.assertEqual(self.looker.find('foo.a_x_b.a1b'),'foo')
        self.assertEqual(self.looker.find('parsely.a_b.a1b'),'ping')
        self.assertEqual(self.looker.find('walnut-a_b-a1b'),'zip')
        return

    def test_ident_dash(self):
        """A single label with a dash is not mistaken for either an ident or fqdn."""
        self.assertEqual(self.looker.find('foo.a-b.a1b'),'')
        return
    
    def test_fqdn_dash(self):
        """FQDNs with dashes in various combinations."""
        self.assertEqual(self.looker.find('eggplant.ab.cd.ef.a2f'),'pong')
        self.assertEqual(self.looker.find('eggplant.a-b.cd.ef.a2f'),'pong')
        self.assertEqual(self.looker.find('eggplant.a--b.cd.ef.a2f'),'pong')
        self.assertEqual(self.looker.find('eggplant.a-x-b.cd.ef.a2f'),'pong')
        self.assertEqual(self.looker.find('eggplant.ab.c-d.ef.a2f'),'pong')
        return

    def test_fqdn_dash_last_label(self):
        """FQDN with a dash in the last label."""
        self.assertEqual(self.looker.find('eggplant.ab.cd.e-f.a2f'),'pong')
        return
    
class TestFqdnMatcher(unittest.TestCase):
    """Testing of the FQDN Matcher specifically."""
    
    def setUp(self):
        self.matcher = alias.MatchExpression.IDENT_MATCHERS['fqdn']
        return
    
    def test_sanity(self):
        """Assure that we're looking at the right test item."""
        self.assertEqual(str(self.matcher), 'fqdn')
        common = self.matcher.char_sets[0].copy()
        common.union(*self.matcher.char_sets[1:])
        self.assertEqual(common, alias.MATCH_ALNUM)
        self.assertEqual(self.matcher.char_sets[1] - alias.MATCH_ALNUM, set('.-'))
        return

    def test_fqdn_match(self):
        """It should match an FQDN."""
        self.assertEqual(self.matcher('abc.def.ghi'), (0,10))
        self.assertEqual(self.matcher('xyz,abc.def.ghi,123'), (0,2))
        self.assertEqual(self.matcher('xyz,abc.def.ghi,123', 4), (4,14))
        return
    
    def test_dashes(self):
        """Dashes should be allowed within the FQDN."""
        self.assertEqual(self.matcher('a-b.cd.ef'), (0,8))
        self.assertEqual(self.matcher('ab.c-d.ef'), (0,8))
        self.assertEqual(self.matcher('ab.cd.e-f'), (0,8))
        return
    
    def test_leading_trailing(self):
        """Leading and trailing dashes and dots should be disallowed."""
        self.assertEqual(self.matcher('.a-b.cd.ef'), None)
        self.assertEqual(self.matcher('.ab.c-d.ef'), None)
        self.assertEqual(self.matcher('.ab.cd.e-f'), None)
        self.assertEqual(self.matcher('a-b.cd.ef.'), (0,8))
        self.assertEqual(self.matcher('ab.c-d.ef.'), (0,8))
        self.assertEqual(self.matcher('ab.cd.e-f.'), (0,8))
        self.assertEqual(self.matcher('-a-b.cd.ef'), None)
        self.assertEqual(self.matcher('-ab.c-d.ef'), None)
        self.assertEqual(self.matcher('-ab.cd.e-f'), None)
        self.assertEqual(self.matcher('a-b.cd.ef-'), (0,8))
        self.assertEqual(self.matcher('ab.c-d.ef-'), (0,8))
        self.assertEqual(self.matcher('ab.cd.e-f-'), (0,8))
        return
        
    
class TestCodePositions(unittest.TestCase):
    """Test placement of verification code."""
    
    def setUp(self):
        self.config = parse(CONFIG)
        self.looker = LookupThing(self.config)
        return
    
    def test_code_at_start(self):
        """Code at the end."""
        self.assertEqual(self.looker.find('g2r.foo.green'),'foo')
        self.assertEqual(self.looker.find('g4r.bar.green.beans'),'bar')
        self.assertEqual(self.looker.find('g2r.parsely.green'),'ping')
        self.assertEqual(self.looker.find('g4r.eggplant.green.beans'),'pong')
        self.assertEqual(self.looker.find('s1m-walnut-shrimp'),'zip')
        self.assertEqual(self.looker.find('t4l-almond-mocha.latte'),'zap')   
        return

    def test_code_in_middle(self):
        """Code in the middle."""
        self.assertEqual(self.looker.find('foo.g2r.green'),'foo')
        self.assertEqual(self.looker.find('bar.g4r.green.beans'),'bar')
        self.assertEqual(self.looker.find('parsely.g2r.green'),'ping')
        self.assertEqual(self.looker.find('eggplant.g4r.green.beans'),'pong')
        self.assertEqual(self.looker.find('walnut-s1m-shrimp'),'zip')
        self.assertEqual(self.looker.find('almond-t4l-mocha.latte'),'zap')        
        return

    def test_code_at_end(self):
        """Code at the end."""
        self.assertEqual(self.looker.find('foo.green.g2r'),'foo')
        self.assertEqual(self.looker.find('bar.green.beans.g4r'),'bar')
        self.assertEqual(self.looker.find('parsely.green.g2r'),'ping')
        self.assertEqual(self.looker.find('eggplant.green.beans.g4r'),'pong')
        self.assertEqual(self.looker.find('walnut-shrimp-s1m'),'zip')
        self.assertEqual(self.looker.find('almond-mocha.latte-t4l'),'zap')        
        return

if __name__ == '__main__':
    unittest.main(verbosity=2)
