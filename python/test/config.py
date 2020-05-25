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
import ipaddress
import logging

if '..' not in sys.path:
    sys.path.insert(0,'..')

from trualias import CASE_SENSITIVE, HOST, PORT, LOGGING, DEBUG_ACCOUNT
import trualias.config as config
import trualias.parser as parser

def parse(text):
    return config.from_text(parser.MultilineStringLoader(text),raise_on_error=True).config

class TestBasicParsing(unittest.TestCase):
    """Tests basic parsing."""
    
    def test_empty_config(self):
        """Empty configuration."""
        configuration = parse('')
        
        self.assertEqual(configuration['case_sensitive'], CASE_SENSITIVE)
        self.assertEqual(configuration['host'], HOST)
        self.assertEqual(configuration['port'], PORT)
        self.assertEqual(configuration['logging'], LOGGING)
        self.assertEqual(configuration['debug_account'], DEBUG_ACCOUNT)
        self.assertEqual(len(configuration['aliases']), 0)

        return
    
    def test_blank_config(self):
        """Multiline but just white space."""
        configuration = parse(' \n\n    \n')
        
        self.assertEqual(configuration['case_sensitive'], CASE_SENSITIVE)
        self.assertEqual(configuration['host'], HOST)
        self.assertEqual(configuration['port'], PORT)
        self.assertEqual(configuration['logging'], LOGGING)
        self.assertEqual(configuration['debug_account'], DEBUG_ACCOUNT)
        self.assertEqual(len(configuration['aliases']), 0)

        return
    
    def test_unknown_text(self):
        """Garbage text."""
        self.assertRaises(parser.ParseError,parse,'FOO!')
        return

class TestParsingConfig(unittest.TestCase):
    """Tests parsing configuration values."""
    
    def test_oddballs(self):
        """Various oddball things."""
        self.assertTrue(parse('CASE SENSITIVE : true\n\n')['case_sensitive'],
                        msg='Should successfully parse "true" (space before ":")'
                       )
        self.assertTrue(parse(' CASE  SENSITIVE : true \n\n')['case_sensitive'],
                        msg='Should successfully parse "true" (extra space between keywords )'
                       )
        self.assertRaises(parser.ParseError, parse, 'DEBUG WALRUS : true \n\n')

        return

    def test_case_sensitive(self):
        """CASE SENSITIVE setting."""
        self.assertTrue(parse('CASE SENSITIVE: true\n\n')['case_sensitive'],
                        msg='Should successfully parse "true"'
                       )
        self.assertFalse(parse('CASE SENSITIVE: FALSE\n\n')['case_sensitive'],
                        msg='Should successfully parse "false"'
                       )
        self.assertTrue(parse('CASE SENSITIVE: 1\n\n')['case_sensitive'],
                        msg='Should successfully parse "1"'
                       )
        self.assertFalse(parse('CASE SENSITIVE: 0\n\n')['case_sensitive'],
                        msg='Should successfully parse "0"'
                       )
        self.assertRaises(ValueError, parse, 'CASE SENSITIVE: 42\n\n')
        self.assertRaises(ValueError, parse, 'CASE SENSITIVE: \n\n')

        return
    
    def test_host(self):
        """HOST: tests for return of a valid host."""
        self.assertEqual(parse('HOST: 127.0.0.1\n\n')['host'], ipaddress.ip_address('127.0.0.1'),
                              msg='Should have parsed 127.0.0.1'
                             )
        self.assertEqual(parse('HOST: 5.0.0.1\n\n')['host'], ipaddress.ip_address('5.0.0.1'),
                              msg='Should have parsed 5.0.0.1'
                             )
        self.assertEqual(parse('HOST: ::0\n\n')['host'], ipaddress.ip_address('::0'),
                              msg='Should have parsed ::0'
                             )
        self.assertRaises(ValueError, parse, 'HOST: example.com\n\n')
        
        return

    def test_port(self):
        """PORT: tests for return of a valid port."""
        self.assertEqual(parse('PORT: 3456\n\n')['port'], 3456,
                              msg='Should have parsed 3456'
                             )
        self.assertRaises(ValueError, parse, 'PORT: -1\n\n')
        self.assertRaises(ValueError, parse, 'PORT: 2535385091\n\n')
        
        return

    def test_logging(self):
        """LOGGING: tests for return of a logging level."""
        self.assertEqual(parse('LOGGING: DEBUG\n\n')['logging'], logging.DEBUG,
                              msg='Should have parsed DEBUG'
                             )
        self.assertEqual(parse('LOGGING: debug\n\n')['logging'], logging.DEBUG,
                              msg='Should have parsed DEBUG (lower cased)'
                             )
        self.assertRaises(ValueError, parse, 'LOGGING: YELLOW \n\n')
        
        return
    
    def test_debug_account(self):
        """DEBUG ACCOUNT: tests ability to specify debug account."""
        self.assertEqual(parse('DEBUG ACCOUNT: joe123\n\n')['debug_account'], 'joe123',
                              msg='Should have parsed joe123'
                             )
        self.assertRaises(ValueError, parse, 'DEBUG ACCOUNT: joe@example.com \n\n')
        return
    
class TestParsingAliases(unittest.TestCase):
    """Tests parsing ALIAS statements."""
    
    def test_fragments(self):
        """Tests ability to reject incorrect syntax."""
        self.assertRaises(parser.ParseError, parse, '   \nACCOUNT ; \n \n\n')
        self.assertRaises(parser.ParseError, parse, '   \nACCOUNT foo MATCHES bar; \n \n\n')
        self.assertRaises(parser.ParseError, parse, '   \nACCOUNT foo MATCHES bar WITH; \n \n\n')
        self.assertRaises(parser.ParseError, parse, '   \nACCOUNT foo WITH ANY(); \n \n\n')        
        self.assertRaises(parser.ParseError, parse, '   \nACCOUNT ALIASED foo WITH ANY(); \n \n\n')        
        return

    def test_basic_alias(self):
        """A basic sanity check."""
        aliases = parse('ACCOUNT foo MATCHES %ident%-%code% WITH CHARS();')['aliases']
        self.assertEqual(len(aliases), 1,
                         msg="Expected exactly one defined alias."
                        )
        alias = aliases[0]
        self.assertEqual(len(alias.accounts), 1,
                         msg='Should only be one defined account.'
                        )
        self.assertEqual(alias.accounts[0], 'foo',
                         msg='Expected account to be "foo".'
                        )
        self.assertEqual(alias.matchex.expression_, '%ident%-%code%',
                         msg='Expected match expression "%ident%-%code%".'
                        )
        self.assertEqual(len(alias.calc), 1,
                         msg='Expected exactly one calc.'
                        )
        self.assertEqual(alias.calc[0][0], 'CHARS',
                         msg='Expected calc to be CHARS.'
                        )
        self.assertEqual(len(alias.calc[0]), 1,
                         msg='Expected calc to have zero args.'
                        )
        return
    
    def test_multiple_accounts(self):
        """Multiple accounts get parsed correctly."""
        aliases = parse("""
                        ACCOUNT foo, bar,baz, zeep
                        MATCHES %account%-%ident%-%code%
                        WITH  CHAR(1,-);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].accounts), 4,
                         msg='Expected 4 accounts.'
                        )
        return
    
    def test_multiple_aliases(self):
        """Multiple aliases for an account."""
        aliases = parse("""
                        ACCOUNT foo
                        ALIASED banana, orange,yoyoma
                        MATCHES %alias%-%ident%-%code%
                        WITH  CHAR(1,-);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].aliases), 3,
                         msg='Expected 3 aliases.'
                        )
        return
    
    def test_multiple_calcs(self):
        """Multiple calcs in a calc expression."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES %account%-%ident%-%code%
                        WITH  CHAR(1,-),ANY(), DIGITS();
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 3,
                         msg='Expected 3 calcs.'
                        )
        return
    
    def test_bad_index_in_calc(self):
        """A non-integer, unrecognized index."""
        self.assertRaises(parser.ParseError, parse, '   \nACCOUNT foo MATCHES %ident%-%code% WITH ANY(bar); \n \n\n')        
        return
    
class TestMatchexSemantics(unittest.TestCase):
    """Verifies semantic checking of match expressions."""
    
    def test_adjacent_poison(self):
        """Some adjacent things should be out-and-out rejected."""
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES %ident%%ident%-%code%
                          WITH ANY(1),ANY(2);
                          """
                         )
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES something%alpha%%alpha%-%code%
                          WITH ANY(1),ANY(2);
                          """
                         )
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES something%alpha%%ident%-%code%
                          WITH ANY(1),ANY(2);
                          """
                         )
        return
    
    def test_friendly_bad(self):
        """Some things are allowed sometimes but disallowed others."""
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES something%alpha%%alpha%-%code%
                          WITH ANY(1),ANY(2);
                          """
                         )
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES something%number%%number%-%code%
                          WITH ANY(1),ANY(2);
                          """
                         )
        return
    
    def test_friendly_good(self):
        """Some things are disallowed sometimes but allowed others."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES something%number%%alpha%-%code%
                        WITH ANY(1),ANY(2);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].matchex.tokens), 7,
                         msg="Successfully parsed matchex should have 7 elements."
                        )
        return

class TestCalcSemantics(unittest.TestCase):
    """Verifies semantic checking of calcs."""
    
    def test_char_args_good_2(self):
        """Tests good CHAR() with 2 args."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES something%alpha%-%code%
                        WITH CHAR(2,-);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 3,
                         msg="Expected calc to have 2 args."
                        )
        return
    
    def test_char_args_good_3_idents(self):
        """Tests good CHAR() with 3 args, multiple idents."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES %account%-%alpha%-%alpha%-%code%
                        WITH CHAR(1,2,-);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 4,
                         msg="Expected calc to have 3 args."
                        )
        return

    def test_char_args_good_3_fqdn(self):
        """Tests good CHAR() with 3 args, fqdn."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES %account%-%fqdn%-%code%
                        WITH CHAR(1,2,-);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 4,
                         msg="Expected calc to have 3 args."
                        )
        return

    def test_char_args_good_4(self):
        """Tests good CHAR() with 4 args."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES %account%-%fqdn%-%fqdn%-%code%
                        WITH CHAR(2,1,2,-);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 5,
                         msg="Expected calc to have 4 args."
                        )
        return
    
    def test_char_3_args_opt(self):
        """Tests good CHAR() with an optional identifier index."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES something%alpha%-%code%
                        WITH CHAR(1,2,-);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 4,
                         msg="Expected calc to have 3 args."
                        )
        return

    def test_char_bad_index(self):
        """Tests CHAR() identifier index out of range."""
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES something%alpha%-%code%
                          WITH CHAR(0,2,-);
                          """
                         )
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES something%alpha%-%code%
                          WITH CHAR(42,2,-);
                          """
                         )
        return
    
    def test_generic_no_index_good(self):
        """Tests no index argument."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES something%alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        return
        
    def test_generic_no_index_bad(self):
        """Tests no index argument."""
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES something%alpha%-%alpha%-%code%
                          WITH ANY();
                          """
                         )
        return

    def test_generic_index_good(self):
        """Tests good index argument."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES %account%-%alpha%-%alpha%-%alpha%-%code%
                        WITH ANY(2);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 2,
                         msg="Expected calc to have 1 arg."
                        )
        return

    def test_generic_index_bad(self):
        """Tests CHAR() identifier index out of range."""
        self.assertRaises(config.SemanticError, parse,
                          """
                        ACCOUNT foo
                        MATCHES %account%-%alpha%-%alpha%-%alpha%-%code%
                        WITH ANY(0);
                          """
                         )
        self.assertRaises(config.SemanticError, parse,
                          """
                        ACCOUNT foo
                        MATCHES %account%-%alpha%-%alpha%-%alpha%-%code%
                        WITH ANY(5);
                          """
                         )
        return
    
    def test_account_good(self):
        """Tests good account argument."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES %account%-%alpha%-%code%
                        WITH ANY(account);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 2,
                         msg="Expected calc to have 1 arg."
                        )
        return
    
    def test_alias_good(self):
        """Tests good alias argument."""
        aliases = parse("""
                        ACCOUNT foo
                        ALIASED fizz
                        MATCHES %account%-%alpha%-%code%
                        WITH ANY(alias);
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 2,
                         msg="Expected calc to have 1 arg."
                        )
        return

    def test_alias_bad(self):
        """Tests bad (no) alias argument."""
        self.assertRaises(config.SemanticError, parse,
                        """
                        ACCOUNT foo
                        MATCHES %account%-%alpha%-%code%
                        WITH ANY(alias);
                        """
                       )
        return

class TestUniqueness(unittest.TestCase):
    """Tests our uniqueness guarantees."""
    
    def test_account_no_alias_good(self):
        """Test successful validation of an account with no aliases."""
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES %alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        
        aliases = parse("""
                        ACCOUNT foo
                        MATCHES %account%-%alpha%-%code%
                        WITH ANY();
                        
                        ACCOUNT bar
                        MATCHES %account%-%alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases), 2,
                         msg="Expected 2 account specs."
                        )
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        return

    def test_account_no_alias_bad(self):
        """Test failed validation of an account with no aliases."""
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          MATCHES %alpha%-%code%
                          WITH ANY();
                          
                          ACCOUNT bar
                          MATCHES %alpha%-%code%
                          WITH ANY();
                        """
                       )
        return
    
    def test_account_unique_alias_good(self):
        """Test successful validation of an account and alias both unique."""
        aliases = parse("""
                        ACCOUNT foo
                        ALIASED fizz
                        MATCHES %alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        aliases = parse("""
                        ACCOUNT foo
                        ALIASED fizz
                        MATCHES %account%-%alpha%-%code%
                        WITH ANY();
                        
                        ACCOUNT bar
                        ALIASED buzz
                        MATCHES %account%-%alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases), 2,
                         msg="Expected 2 account specs."
                        )
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        aliases = parse("""
                        ACCOUNT foo
                        ALIASED fizz
                        MATCHES %alias%-%alpha%-%code%
                        WITH ANY();
                        
                        ACCOUNT bar
                        ALIASED buzz
                        MATCHES %alias%-%alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases), 2,
                         msg="Expected 2 account specs."
                        )
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        return
        
    def test_account_unique_alias_bad(self):
        """Test failed validation of a unique account+alias."""
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          ALIASED fizz
                          MATCHES %alpha%-%code%
                          WITH ANY();
                          
                          ACCOUNT bar
                          ALIASED buzz
                          MATCHES %alpha%-%code%
                          WITH ANY();
                        """
                       )
        return
    
    def test_account_many_aliases_good(self):
        """Test successful validation of an account with many aliases."""
        aliases = parse("""
                        ACCOUNT foo
                        ALIASED fizz, buzz
                        MATCHES %alias%-%alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        return
        
    def test_account_many_aliases_bad(self):
        """Test failed validation of an account with many aliases.."""
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo
                          ALIASED fizz, buzz
                          MATCHES %account%-%alpha%-%code%
                          WITH ANY();
                        """
                       )
        return

    def test_many_accounts_good(self):
        """Test successful validation of many accounts single alias."""
        aliases = parse("""
                        ACCOUNT foo, bar
                        ALIASED fizz, buzz
                        MATCHES %account%-%alias%-%alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        aliases = parse("""
                        ACCOUNT foo
                        ALIASED fizz, buzz
                        MATCHES %account%-%alias%-%alpha%-%code%
                        WITH ANY();

                        ACCOUNT bar
                        ALIASED fizz, buzz
                        MATCHES %alias%-%account%-%alpha%-%code%
                        WITH ANY();
                        """
                       )['aliases']
        self.assertEqual(len(aliases[0].calc), 1,
                         msg="Expected one calc."
                        )
        self.assertEqual(len(aliases[0].calc[0]), 1,
                         msg="Expected calc to have no args."
                        )
        return

    def test_account_many_aliases_bad(self):
        """Test failed validation of an account with many aliases.."""
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo, bar
                          ALIASED fizz, buzz
                          MATCHES %account%-%alpha%-%code%
                          WITH ANY();
                        """
                       )
        self.assertRaises(config.SemanticError, parse,
                          """
                          ACCOUNT foo, bar
                          ALIASED fizz, buzz
                          MATCHES %alias%-%alpha%-%code%
                          WITH ANY();
                        """
                       )
        return

if __name__ == '__main__':
    unittest.main(verbosity=2)
    
