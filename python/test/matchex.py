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
    
import trualias.alias as alias
import trualias.config as config
import trualias.parser as parser
import trualias.matching as matching

def parse(text):
    return config.from_text(parser.MultilineStringLoader(text),raise_on_error=True).config['aliases']

class TestSimpleSketchCases(unittest.TestCase):
    """Does it work? Is there smoke?"""
    TEST_CONFIGURATION = """
        ACCOUNT foo
        MATCHES %account%-%ident%-%code%
        WITH CHARS();
    """

    def setUp(self):
        self.aliases = parse(self.TEST_CONFIGURATION)
        return
    
    def test_priors(self):
        """We should know these are true (we test them elsewhere)..."""
        self.assertEqual(len(self.aliases), 1)
        self.assertEqual(self.aliases[0].matchex.expression_, '%account%-%ident%-%code%')
        self.assertEqual(len(self.aliases[0].calc), 1)
        self.assertEqual(len(self.aliases[0].calc.calcs[0]), 1)
        self.assertEqual(self.aliases[0].calc.calcs[0][0], 'CHARS')
        return
    
    def test_sketch(self):
        """Are we building sketches?"""
        matchex = self.aliases[0].matchex
        self.assertEqual(len(matchex.sketch), 7)
        return
    
    def test_sketch_match(self):
        """Does the machinery for matching work?"""
        alias = self.aliases[0]
        matchex = alias.matchex
        
        matched = matchex.match_sketch(matchex.sketch, 'foo-bar-3')
        self.assertEqual([ ident.value for ident in matched[0]], 'foo-bar-3'.split('-'))
        return
    
    def test_sketch_match_fail(self):
        """Multiple dashes in the account name..."""
        alias = self.aliases[0]
        matchex = alias.matchex
        
        matched = matchex.match_sketch(matchex.sketch, 'foo-bar---3')
        self.assertEqual(len(matched), 0)
        return

class TestMatchingPrimitives(unittest.TestCase):
    """Tests for matching primitives."""
    
    MATCH_AT_ENDS = set("abc")
    MATCH_INTERIOR = MATCH_AT_ENDS | set("-_")
    
    def test_basic_matcher(self):
        """Basic character set matcher."""
        matcher = matching.Matcher(self.MATCH_AT_ENDS, self.MATCH_INTERIOR, self.MATCH_AT_ENDS)
        result = matcher("aaa.bbb.c-c", start_pos=0, end_pos=None, minimal=False)
        self.assertEqual(result, (0,2))
        result = matcher("aaa.bbb.c-c", start_pos=8, end_pos=None, minimal=False)
        self.assertEqual(result, (8,10))
        result = matcher("aaa.bbb.c-c", start_pos=7, end_pos=None, minimal=False)
        self.assertEqual(result, None)
        result = matcher("aaa.bbb.c-c", start_pos=8, end_pos=9, minimal=False)
        self.assertEqual(result, (8,9))
        result = matcher("aaa.bbb.c-c", start_pos=4, end_pos=9, minimal=False)
        self.assertEqual(result, None)
        result = matcher("aaa.bbb.c-c", start_pos=4, end_pos=None, minimal=True)
        self.assertEqual(result, (4,4))
        result = matcher("aaa.bbb.c-c", start_pos=8, end_pos=8, minimal=True)
        self.assertEqual(result, (8,8))
        result = matcher("aaa.bbb.c-c", start_pos=8, end_pos=9, minimal=True)
        self.assertEqual(result, (8,10))

        result = matcher.match_one_more("aaa.bbb.c-c", start_pos=7, end_pos=6)
        self.assertFalse(result)
        result = matcher.match_one_more("aaa.bbb.c-c", start_pos=8, end_pos=7)
        self.assertTrue(result)
        result = matcher.match_one_more("aaa.bbb.c-c", start_pos=8, end_pos=8)
        self.assertFalse(result)
        
        return
        
    def test_any_matcher(self):
        """Matches anything."""
        matcher = matching.MatchAny()
        
        result = matcher("aaa.bbb.c-c", start_pos=0, end_pos=None, minimal=False)
        self.assertEqual(result, (0,10))
        result = matcher("aaa.bbb.c-c", start_pos=8, end_pos=None, minimal=False)
        self.assertEqual(result, (8,10))
        result = matcher("aaa.bbb.c-c", start_pos=11, end_pos=None, minimal=False)
        self.assertEqual(result, None)
        result = matcher("aaa.bbb.c-c", start_pos=8, end_pos=9, minimal=False)
        self.assertEqual(result, (8,9))
        result = matcher("aaa.bbb.c-c", start_pos=8, end_pos=8, minimal=True)
        self.assertEqual(result, (8,8))

        result = matcher.match_one_more("aaa.bbb.c-c", start_pos=7, end_pos=6)
        self.assertTrue(result)
        result = matcher.match_one_more("aaa.bbb.c-c", start_pos=8, end_pos=9)
        self.assertTrue(result)
        result = matcher.match_one_more("aaa.bbb.c-c", start_pos=8, end_pos=10)
        self.assertFalse(result)

        return
    
    def test_code_matcher_n(self):
        """Single numeric calc."""
        matcher = matching.MatchCode()
        matcher.append('number')
        
        result = matcher("aaa.b2b.c-c", start_pos=4, end_pos=None, minimal=False)
        self.assertEqual(result, None)
        result = matcher("aaa.b2b.c-c", start_pos=5, end_pos=None, minimal=False)
        self.assertEqual(result, (5,5))
        
        return

    def test_code_matcher_a(self):
        """Single any calc."""
        matcher = matching.MatchCode()
        matcher.append('any')

        result = matcher("aaa.b2b.c-c", start_pos=4, end_pos=None, minimal=False)
        self.assertEqual(result, (4,10))
        result = matcher("aaa.b2b.c-c", start_pos=5, end_pos=None, minimal=False)
        self.assertEqual(result, (5,10))

        return
    
    def test_code_matcher_naan(self):
        """Number calcs on the ends."""
        matcher = matching.MatchCode()
        for mtype in 'number any any number'.split():
            matcher.append(mtype)
        
        result = matcher("abc123fun321", start_pos=4, end_pos=None, minimal=False)
        self.assertEqual(result, (4,11))
        result = matcher("abc123fun321", start_pos=5, end_pos=None, minimal=False)
        self.assertEqual(result, (5,11))
        result = matcher("abc123fun321", start_pos=6, end_pos=None, minimal=False)
        self.assertEqual(result, None)
        result = matcher("abc123fun321", start_pos=5, end_pos=9, minimal=False)
        self.assertEqual(result, (5,9))
        result = matcher("abc123fun321", start_pos=5, end_pos=8, minimal=False)
        self.assertEqual(result, None)
        result = matcher("abc123fun321", start_pos=4, end_pos=None, minimal=True)
        self.assertEqual(result, (4,9))
        
        result = matcher.match_one_more("abc123fun321", start_pos=0, end_pos=5)
        self.assertFalse(result)
        result = matcher.match_one_more("abc123fun321", start_pos=5, end_pos=9)
        self.assertTrue(result)

        return

    def test_code_matcher_anna(self):
        """Number calcs in the middle."""
        matcher = matching.MatchCode()
        for mtype in 'any number number any'.split():
            matcher.append(mtype)
        
        result = matcher("abc123fun321", start_pos=3, end_pos=None, minimal=False)
        self.assertEqual(result, (3,11))
        result = matcher("abc123fun321", start_pos=4, end_pos=None, minimal=False)
        self.assertEqual(result, (4,11))
        result = matcher("abc123fun321", start_pos=2, end_pos=5, minimal=False)
        self.assertEqual(result, (2,5))
        result = matcher("abc123fun321", start_pos=3, end_pos=9, minimal=False)
        self.assertEqual(result, (3,9))
        result = matcher("abc123fun321", start_pos=4, end_pos=9, minimal=False)
        self.assertEqual(result, None)
        result = matcher("abc123fun321", start_pos=0, end_pos=None, minimal=True)
        self.assertEqual(result, (0,5))

        result = matcher.match_one_more("abc123fun321", start_pos=0, end_pos=5)
        self.assertTrue(result)
        result = matcher.match_one_more("abc123fun321", start_pos=4, end_pos=7)
        self.assertTrue(result)

        return
        
    
class TestMoreSketchCases(unittest.TestCase):
    """Various additional tests of core functionality."""

    def test_index_on_calc(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%-%code%
        WITH CHARS(1);
        """
        alias = parse(self.test_index_on_calc.__doc__)[0]
        matchex = alias.matchex
        
        matched = matchex.match_sketch(matchex.sketch, 'foo-bar-3')
        self.assertEqual([ ident.value for ident in matched[0]], 'foo-bar-3'.split('-'))
        return
    
    def test_multiple_calcs(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%-%code%
        WITH CHARS(1),ANY();
        """
        alias = parse(self.test_multiple_calcs.__doc__)[0]
        matchex = alias.matchex
        
        matched = matchex.match_sketch(matchex.sketch, 'foo-bar-3a')
        self.assertEqual([ ident.value for ident in matched[0]], 'foo-bar-3a'.split('-'))
        return
    
    def test_alias_match(self):
        """Call Alias.match()"""
        alias = parse("""
            ACCOUNT foo
            MATCHES %account%-%ident%-%code%
            WITH CHARS(1),ANY();
        """)[0]
        matches = alias.match('foo-bar-3a')

        self.assertEqual(len(matches),1)
        self.assertEqual(len(matches[0].matches),1)
        self.assertFalse(matches[0].ambiguous())
        self.assertEqual(matches[0].delivery_account(),'foo')

        return

class TestCalcFunctions(unittest.TestCase):
    """Test the defined calc functions."""
    
    def test_digits(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%+%fqdn%+%code%
        WITH DIGITS(1);
        """
        alias = parse(self.test_digits.__doc__)[0]
        matchex = alias.matchex

        matched = matchex.match(alias.calc, alias.accounts, alias.aliases, 'foo-party1999+m3047.net+4')
        self.assertEqual(len(matched),1)
        return

    def test_alphas(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%+%fqdn%+%code%
        WITH ALPHAS(1);
        """
        alias = parse(self.test_alphas.__doc__)[0]
        matchex = alias.matchex
    
        matched = matchex.match(alias.calc, alias.accounts, alias.aliases, 'foo-party1999+m3047.net+5')
        self.assertEqual(len(matched),1)
        return

    def test_labels(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%+%fqdn%+%code%
        WITH LABELS(2);
        """
        alias = parse(self.test_labels.__doc__)[0]
        matchex = alias.matchex
    
        matched = matchex.match(alias.calc, alias.accounts, alias.aliases, 'foo-party1999+m3047.net+2')
        self.assertEqual(len(matched),1)
        return

    def test_chars(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%+%fqdn%+%code%
        WITH CHARS(1);
        """
        alias = parse(self.test_chars.__doc__)[0]
        matchex = alias.matchex

        matched = matchex.match(alias.calc, alias.accounts, alias.aliases, 'foo-party1999+m3047.net+9')
        self.assertEqual(len(matched),1)
        return

    def test_vowels(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%+%fqdn%+%code%
        WITH VOWELS(1);
        """
        alias = parse(self.test_vowels.__doc__)[0]
        matchex = alias.matchex

        matched = matchex.match(alias.calc, alias.accounts, alias.aliases, 'foo-party1999+m3047.net+1')
        self.assertEqual(len(matched),1)
        return

    def test_any(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%+%fqdn%+%code%
        WITH ANY(1);
        """
        alias = parse(self.test_any.__doc__)[0]
        matchex = alias.matchex

        matched = matchex.match(alias.calc, alias.accounts, alias.aliases, 'foo-party1999+m3047.net+y')
        self.assertEqual(len(matched),1)
        return

    def test_char(self):
        """
        ACCOUNT foo
        MATCHES %account%-%ident%+%fqdn%+%code%
        WITH CHAR(2,1,3,*);
        """
        alias = parse(self.test_char.__doc__)[0]
        matchex = alias.matchex

        matched = matchex.match(alias.calc, alias.accounts, alias.aliases, 'foo-party1999+m3047.net+0')
        self.assertEqual(len(matched),1)
        return

if __name__ == '__main__':
    unittest.main(verbosity=2)
    
