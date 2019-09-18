#!/usr/bin/python3

import sys
import unittest
import ipaddress
import logging

if '..' not in sys.path:
    sys.path.insert(0,'..')
    
import trualias.config_parser as config_parser

def parse(text):
    return config_parser.from_text(config_parser.MultilineStringLoader(text),raise_on_error=True).config

class TestBasicParsing(unittest.TestCase):
    """Tests basic parsing."""
    
    def test_empty_config(self):
        """Empty configuration."""
        config = parse('')
        
        self.assertEqual(config['case_sensitive'], config_parser.CASE_SENSITIVE)
        self.assertEqual(config['host'], config_parser.HOST)
        self.assertEqual(config['port'], config_parser.PORT)
        self.assertEqual(config['logging'], config_parser.LOGGING)
        self.assertEqual(config['debug_account'], config_parser.DEBUG_ACCOUNT)
        self.assertEqual(len(config['aliases']), 0)

        return
    
    def test_blank_config(self):
        """Multiline but just white space."""
        config = parse(' \n\n    \n')
        
        self.assertEqual(config['case_sensitive'], config_parser.CASE_SENSITIVE)
        self.assertEqual(config['host'], config_parser.HOST)
        self.assertEqual(config['port'], config_parser.PORT)
        self.assertEqual(config['logging'], config_parser.LOGGING)
        self.assertEqual(config['debug_account'], config_parser.DEBUG_ACCOUNT)
        self.assertEqual(len(config['aliases']), 0)

        return
    
    def test_unknown_text(self):
        """Garbage text."""
        self.assertRaises(config_parser.ParseError,parse,'FOO!')
        return

class TestParsingConfig(unittest.TestCase):
    """Tests parsing configuration values."""
    
    def test_oddballs(self):
        """Various oddball things."""
        self.assertTrue(parse('CASE SENSITIVE : true\n\n')['case_sensitive'],
                        msg='Should successfully parse "true" (space before ":")'
                       )
        self.assertTrue(parse(' CASE  SENSITIVE : true \n\n')['case_sensitive'],
                        msg='Should successfully parse "true" (space before ":")'
                       )
        self.assertRaises(config_parser.ParseError, parse, 'DEBUG WALRUS : true \n\n')

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
        self.assertRaises(config_parser.ParseError, parse, '   \nACCOUNT ; \n \n\n')
        self.assertRaises(config_parser.ParseError, parse, '   \nACCOUNT foo MATCHES bar; \n \n\n')
        self.assertRaises(config_parser.ParseError, parse, '   \nACCOUNT foo MATCHES bar WITH; \n \n\n')
        self.assertRaises(config_parser.ParseError, parse, '   \nACCOUNT foo WITH ANY(); \n \n\n')        
        self.assertRaises(config_parser.ParseError, parse, '   \nACCOUNT ALIASED foo WITH ANY(); \n \n\n')        
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
                        MATCHES %account%-%code%
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
                        MATCHES %account%-%code%
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

if __name__ == '__main__':
    unittest.main()
    
