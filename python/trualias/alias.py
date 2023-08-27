#!/usr/bin/python3
# Copyright (c) 2019,2013 by Fred Morris Tacoma WA
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

"""Alias specifications.

The Alias is the key part of a configuration, and maps to one ACCOUNT
statement in a configuration. (See parser.)

The PRINT_... constants control various debugging output. They can be
set to a print function which accepts a string, for example:

    PRINT_THIS = logging.debug
    PRINT_THAT = print
"""

import logging

from .config_base import ConfigurationError
from .utils import TestableIterator, BasicBooleanResult
from .matching import *

# Final result for the sketch.
PRINT_ALIAS_MATCH = None
# Start of MatchExpression.match()
PRINT_MATCH_ENTRY = None
# Details of code calculation.
PRINT_CALC_CODE = None
# Computed values of calculations.
PRINT_CALC_VALUE = None
# Details of match recursion.
PRINT_MATCH_SKETCH = None

class SemanticError(ConfigurationError):
    """A semantic error occurred."""
    pass

class MatchInfo(object):
    """Specifics of a match."""
    def __init__(self, delivery_account, built_match, ambiguous):
        """Encapsulates the specifics of a single match.
        
        Parameters:
        
            delivery_account    The resolved delivery account.
            built_match         One example of what matches.
            ambiguous           Is this ambiguous? (True/False)
        
        Why is this even necessary? Because matches against a match expression
        may be ambiguous, for example "%ident%x%ident% is ambiguous when
        presented with the input "xxxxxx".
        """
        self.delivery_account = delivery_account
        self.built_match = built_match
        self.ambiguous = ambiguous
        return
    
    def __repr__(self):
        return '<MatchInfo: delivery_account:{}, built_match:{}, ambiguous:{}>'.format(self.delivery_account, self.built_match, self.ambiguous)
    
class SpecMatch(object):
    """Represents a match against a definition.
    
    This object is returned to lookup.find().
    """
    def __init__(self, spec, matches=None):
        self.spec = spec
        self.matches = matches or []
        return

    def __len__(self):
        return len(self.matches)

    def matched(self, *args):
        """Every match generates one of these."""
        self.matches.append(MatchInfo(*args))
        return
    
    def ambiguous(self):
        """Returns True if at least one of the matches is ambiguous."""
        if len(self.matches) > 1:
            return True
        for match in self.matches:
            if match.ambiguous:
                return True
        return False
    
    def delivery_account(self):
        """Returns the delivery account if there is only one."""
        accounts = set(match.delivery_account for match in self.matches)
        if len(accounts) > 1:
            return None
        return accounts.pop()


class Literal(object):
    """Represents a literal in a matching sketch.
    
    "Literal", in turn, represents fixed text to be tested against the passed
    address, but is subject to substitution.
    """
    def __init__(self, parts, subs, params):
        """Define a literal with the specified parts and substitutions."""
        parts = TestableIterator(parts)
        # Put empty slots between the parts of parts for later substitutions.
        self.parts = [ parts.next() ]
        while parts():
            self.parts += [ '', parts.next() ]
        self.subs = subs
        self.params = params
        return
    
    def __repr__(self):
        return '<Literal "{}">'.format(''.join((str(part) for part in self.parts)))
    
    def __str__(self):
        i = 0
        parts = self.parts      # Actually modified in place.
        for sub in self.subs:
            parts[i*2 + 1] = self.params[sub]
            i += 1
        return ''.join((str(part) for part in parts))

class Sketch(object):
    """A matching sketch.
    
    For the raw sketch we just use a list because all of the literals are literals.
    But for conclusive matching we need to substitute accounts and aliases, which
    generates new literals.
    
    NOT THREAD SAFE. using() uses instance storage for the actual account and alias
    represented in the returned sketch.
    """
    def __init__(self, sketch):
        """Compile the passed sketch into one which can be efficiently substituted into."""
        self.params = dict(account=None, alias=None)
        self.sketch = []
        sketch = TestableIterator(sketch)
        while sketch():
            parts = [ sketch.next() ]   # literal
            subs = []
            while sketch():
                if sketch.next(lookahead=True).name not in self.params:
                    break
                subs.append( sketch.next().name )
                parts.append( sketch.next() )
            self.sketch.append( Literal(parts, subs, self.params) )
            if sketch():
                self.sketch.append( sketch.next() )
                
        return
    
    def using(self, account, alias):
        self.params['account'] = account
        self.params['alias'] = alias
        return self.sketch

class Identifier(object):
    """One matched identifier."""
    def __init__(self,type,value):
        self.type = type
        self.value = value
        return
    
    def __repr__(self):
        return '"{}"({})'.format(self.value, self.type)
    
class IdentifierList(list):
    """Lists of matched identifiers.
    
    This is the list of lists identifier matches in a matched expression.
    Each item in the list is a list of the identifiers matched for that particular
    match.
    """
    def __init__(self, success=True):
        """Create an IdentifierList.
        
        IdentifierLists have boolean semantics indicating whether or not there
        was any sublist match at all. As a consequence, when there was a successful
        match and everything has been consumed, we need an "empty" state which is
        also "success".
        """
        if success:
            # This is cleaned up in append() and provides semantic sugar a.k.a. "success".
            list.append(self, [])
        self.code = None
        return
    
    def append(self, type, value, sublists):
        """Appends annotated sublists to the list.
        
        The identifier lists are built in reverse order. When a sub
        match is found and percolates up, the match at this level needs
        to be prepended to each of the sublists.
        """
        for match in sublists:
            if match:
                list.append(self, [Identifier(type.name, value)] + match )
            else:
                list.append(self, [Identifier(type.name, value)] )
        return
    
    def unpack(self):
        """Returns an "unpacked" identifier list.
        
        Returns (code, idents) where idents is an (indexed) list of the Identifiers
        to calculate from.
        """
        for match in self:
            code = None
            idents = []
            for ident in match:
                if ident.type == 'code':
                    code = ident
                elif ident.type in MatchExpression.IDENT_MATCHERS:
                    idents.append(ident)
            yield code, idents
    
class MatchFailed(Exception):
    """A convenient way to abort processing when matching is no longer possible.
    
    The alternative would be to do something like Rust does with function
    results and encapsulate them in an object which also contains status
    information.
    """
    pass

class MatchExpression(object):
    """A match expression."""
    DEFAULT_ACCOUNT_MATCH = 'ident'
    IDENT_MATCHERS = dict(   alnum=Matcher('alnum',MATCH_ALNUM),
                             alpha=Matcher('alpha',MATCH_ALPHA),
                             number=Matcher('number',MATCH_NUMBER),
                             ident=Matcher('ident',MATCH_IDENT,MATCH_IDENT|set('-'),MATCH_IDENT),
                             fqdn=Matcher('fqdn',MATCH_IDENT,MATCH_FQDN,MATCH_IDENT)
                           )
    ALL_MATCHERS = dict( IDENT_MATCHERS,
                             account=Matcher('account',MATCH_IDENT),
                             alias=Matcher('alias',MATCH_IDENT),
                             code=MatchAny('code')
                       )
    FRIENDLIES = { 'alpha', 'number' }
    
    MATCH_ANY_CHAR = { 'ANY', 'NONE', 'CHAR' }
    
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
        self.ALL_MATCHERS['account'] = self.IDENT_MATCHERS[self.account_matcher_].copy('account')
        self.ALL_MATCHERS['alias'] = self.IDENT_MATCHERS[self.account_matcher_].copy('alias')
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
    
    def build_sketch(self, calcs):
        """Build a sketch to allow us to rule out / in whether or not an address potentially matches."""
        sketch = []
        outside = False
        for tok in self.tokens:
            outside ^= True
            if outside:
                sketch.append(tok)
                continue
            if tok != 'code':
                matcher = self.ALL_MATCHERS[tok]
                sketch.append(matcher)
                continue
            
            # tok == 'code'
            code_matcher = MatchCode('code')
            for calc in calcs.calcs:
                code_matcher.append(calc[0] in self.MATCH_ANY_CHAR and 'any' or 'number')
            sketch.append(code_matcher)
            
        self.sketch = sketch
        return

    def match_sketch(self, sketch, address, i=0, start_pos=0):
        """Called recursively to match the sketch.
        
        Return value:
            An IdentifierList of lists for all possible matches.
        """
        if PRINT_MATCH_SKETCH:
            PRINT_MATCH_SKETCH('  {}{}  {},{}'.format(' '*i, sketch, i, start_pos))
        # Success is when we consumed both the sketch and the address at the same time.
        at_the_end = 0
        at_the_end += (i + 1) >= len(sketch)
        at_the_end += start_pos >= len(address)
        if at_the_end:
            return IdentifierList(at_the_end == 2)
        
        # Still more sketch elements and address to match. Literal elements
        # are at even offsets while Matchers will be odd.
        
        # All subsequent tests have implicitly tested the starting lit.
        if start_pos == 0:
            literal = str(sketch[i])
            if not address.startswith(literal):
                return IdentifierList(False)
            start_pos = len(literal)
        if i >= (len(sketch)-1):
            return IdentifierList(True)

        end_lit = (len(sketch) > (i + 2)) and str(sketch[i+2]) or None
        end_offset = start_pos
        
        matches = IdentifierList(False)
        matched = BasicBooleanResult()
        
        while end_offset < len(address):

            if end_lit:
                if not (address[end_offset:].startswith(end_lit)
                    and sketch[i+1](address, start_pos, end_offset-1)
                       ):
                    end_offset += 1
                    continue

                ident_value = address[start_pos:end_offset]
                end_offset += len(end_lit)
            else:
                end_offset += 1
                if not sketch[i+1](address, start_pos, end_offset-1):
                    continue

                ident_value = address[start_pos:end_offset]
            
            if matched(self.match_sketch(sketch, address, i+2, end_offset)).success:
                matches.append( sketch[i+1], ident_value, matched.result)
        
        if PRINT_MATCH_SKETCH:
            PRINT_MATCH_SKETCH('  {}{}'.format(' '*i, matches))
        return matches
    
    def match(self, calc, accounts, aliases, address):
        """Tests whether or not the passed address can be resolved to a deliverable address or not."""
        if PRINT_MATCH_ENTRY:
            PRINT_MATCH_ENTRY('{}... {}  {}'.format(self.expression_,accounts,aliases))
        try:
            # First do a quick test to see if we can match the sketch.
            # The way this works is we do generalized matching after anchoring literals.
            
            if not self.match_sketch(self.sketch, address):
                return []
            
        except MatchFailed:
            return []

        # If that works, do it for real. This involves replacing occurrences of "account"
        # or "alias" with actual values and re-running the sketch for each combination.
        matches = []
        sketch = Sketch(self.sketch)
        for account in accounts or ['']:
            for alias in aliases or ['']:
                try:
                    if PRINT_MATCH_SKETCH:
                        PRINT_MATCH_SKETCH('             sketch.using({}, {})'.format(account,alias))
                    matched = self.match_sketch( sketch.using( account, alias ), address)
                    if PRINT_MATCH_SKETCH:
                        PRINT_MATCH_SKETCH('               matched {}'.format(matched))
                    if not matched:
                        continue
                    # Calculate the verification code. matched.unpack() returns (Identifier, [Identifier...])
                    verified = []
                    for code, idents in matched.unpack():
                        if not code:
                            # TODO: This should never happen. It's kind of like an assertion fail.
                            logging.warning('Empty code matching "{}" against "{}".'.format(address, self.expression_))
                            continue
                        if PRINT_CALC_CODE:
                            PRINT_CALC_CODE('               calculating {}, {}'.format(code, idents))
                        if calc.calculate(code, idents, account, alias):
                            if PRINT_CALC_CODE:
                                PRINT_CALC_CODE('               verified! {}, {}'.format(code, idents))
                            verified.append(idents)
                    
                    if verified:
                        matches.append( MatchInfo(account, verified[0], (len(verified) > 1)) )
                except MatchFailed:
                    continue
        return matches

class Subscriptable(object):
    """Encapsulates the notion that the subscript argument can be a subscript or account/alias."""
    NONINTEGER_PARAM_VALUES = set('account alias'.split())

    def __init__(self, identifiers, account, alias):
        self.identifiers = identifiers
        self.account = account
        self.alias = alias
        return
    
    @property
    def n_identifiers(self):
        return len(self.identifiers)
    
    def get(self, subscript):
        subscript = subscript.lower()
        if   subscript == 'account':
            return Identifier('account', self.account)
        elif subscript == 'alias':
            return Identifier('alias', self.alias)
        return self.identifiers[int(subscript)-1]
    
DIGITS = set("1234567890")
def func_digits(code,args,identifiers):
    i = args and args[0] or '1'
    return str(sum(( c in DIGITS for c in identifiers.get(i).value )))

ALPHAS = set('abcdefghijklmnopqrstuvwxyz')
def func_alphas(code,args,identifiers):
    i = args and args[0] or '1'
    return str(sum(( c in ALPHAS for c in identifiers.get(i).value )))

def func_labels(code,args,identifiers):
    i = args and args[0] or '1'
    if identifiers.get(i).type != 'fqdn':
        return None
    return str(len(identifiers.get(i).value.split('.')))
    
def func_chars(code,args,identifiers):
    i = args and args[0] or '1'
    return str(len(identifiers.get(i).value))

VOWELS = set('aeiou')
def func_vowels(code,args,identifiers):
    i = args and args[0] or '1'
    return str(sum(( c in VOWELS for c in identifiers.get(i).value )))

def func_any(code,args,identifiers):
    i = args and args[0] or '1'
    return code[0] in identifiers.get(i).value and code[0] or None

def func_none(code,args,identifiers):
    i = args and args[0] or '1'
    return code[0] not in identifiers.get(i).value and code[0] or None

def func_char(code,args,identifiers):
    """ This is the only one which has more than one possible argument..."""
    args = TestableIterator(args)
    
    if len(args) == 4 or (  len(args) == 3
                        and (identifiers.n_identifiers != 1 or identifiers.get('1').type != 'fqdn')
                         ):
        i = args.next()
    else:
        i = '1'

    label = identifiers.get(i).type == 'fqdn' and args.next() or 0
    
    char = args.next()
    default = args.next()
    
    identifier = identifiers.get(i).value
    if identifiers.get(i).type == 'fqdn':
        labels = identifier.split('.')
        if abs(label) > len(labels):
            return default
        if label > 0:
            label -= 1
        identifier = labels[label]
        
    if abs(char) > len(identifier):
        return default
    if char > 0:
        char -= 1       # one-based
    return identifier[char]
    
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

    def semantic_check(self, matchex, aliases):
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
            first_arg_is_label = False
            if func == 'CHAR':
                if len(args) > 4:
                    self.semantic_error('{} requires at most 4 arguments with {}'.format(func, matchex.expression))
                if needs_ident_subscript:
                    if len(args) < 3:
                        self.semantic_error('{} requires an identifier subscript with {}'.format(func, matchex.expression))
                    if len(args) == 4:
                        try:
                            i_ident = int(args[0])
                        except ValueError:
                            i_ident = -1
                        if i_ident not in matchex.fqdns:
                            self.semantic_error('{} index {} does not reference an fqdn in {}'.format(func, i_ident, matchex.expression))
                    else:
                        if args[0].lower() not in Subscriptable.NONINTEGER_PARAM_VALUES:
                            try:
                                i_ident = int(args[0])
                            except ValueError:
                                i_ident = -1
                            if i_ident < 1 or i_ident > n_identifiers:
                                self.semantic_error('{} index must be between 1 and {} with {}'.format(func, n_identifiers, matchex.expression))
                            if i_ident in matchex.fqdns:
                                self.semantic_error('{} index {} references an fqdn and needs a label index with {}'.format(func, i_ident, matchex.expression))
                        elif args[0].lower() == 'alias' and not aliases:
                            self.semantic_error('"alias" referenced in {} but no aliases present.'.format(matchex.expression))
                else:
                    if len(args) < 2:
                        self.semantic_error('{} requires at least 2 arguments with {}'.format(func, matchex.expression))
                    if 1 in matchex.fqdns:
                        try:
                            int(args[len(args)-3])
                        except ValueError:
                            self.semantic_error('{} requires numeric label index with {}'.format(func, matchex.expression))
                        if len(args) == 4:
                            try:
                                i_ident = int(args[0])
                            except ValueError:
                                i_ident = -1
                            if i_ident != 1:
                                self.semantic_error('{} requires index of 1 with {}'.format(func, matchex.expression))
                        else:
                            first_arg_is_label = True
                    else:
                        if len(args) == 4:
                            self.semantic_error('{} must not have a label argument with {}'.format(func, matchex.expression))
                        if len(args) == 3:
                            if args[0].lower() not in Subscriptable.NONINTEGER_PARAM_VALUES:
                                try:
                                    i_ident = int(args[0])
                                except ValueError:
                                    i_ident = -1
                                if i_ident < 1 or i_ident > n_identifiers:
                                    self.semantic_error('{} index must be between 1 and {} with {}'.format(func, n_identifiers, matchex.expression))                            
                            elif args[0].lower() == 'alias' and not aliases:
                                self.semantic_error('"alias" referenced in {} but no aliases present.'.format(matchex.expression))
                # Preconvert label index and character offset to int, but not identifier index.
                try:
                    calc[-2] = int(calc[-2])
                    if len(args) == 4 or first_arg_is_label:
                        calc[-3] = int(calc[-3])
                except ValueError:
                    self.semantic_error('{} has invalid label or character index in {}'.format(func, matchex.expression))
            else:
                if len(args) > 1:
                    self.semantic_error('{} requires at most 1 argument with {}'.format(func, matchex.expression))
                if needs_ident_subscript:
                    if len(args) < 1:
                        self.semantic_error('{} requires an identifier subscript with {}'.format(func, matchex.expression))
                if len(args):
                    if args[0].lower() not in Subscriptable.NONINTEGER_PARAM_VALUES:
                        try:
                            i_ident = int(args[0])
                        except ValueError:
                            i_ident = -1
                        if i_ident < 1 or i_ident > n_identifiers:
                            self.semantic_error('{} index must be between 1 and {} with {}'.format(func, n_identifiers, matchex.expression))                            
                    elif args[0].lower() == 'alias' and not aliases:
                        self.semantic_error('"alias" referenced in {} but no aliases present.'.format(matchex.expression))
        return
    
    FUNCS = dict(
                DIGITS=func_digits,
                ALPHAS=func_alphas,
                LABELS=func_labels,
                CHARS=func_chars,
                VOWELS=func_vowels,
                ANY=func_any,
                NONE=func_none,
                CHAR=func_char
        )

    def calculate(self, code, identifiers, account, alias):
        """Calculate the verification code from the list of Identifiers.
        
        Parameters
        ----------
        
            code        A single Identifier.
            identifiers A list of Identifiers.
            account     The account.
            alias       The alias.

        True if the calculated code matches the passed code. In particular, ANY()
        requires prior knowledge of the code being computed.
        
        Technically speaking, the "True" value is the built code string.
        """
        code = code.value
        results = []
        identifiers = Subscriptable(identifiers, account, alias)
        # The way that this works is that we consume the (passed) code and achieve success
        # if we run out at the same time we run out of functions to call.
        for calc in self.calcs:
            if not code:
                return False
            fv = self.FUNCS[calc[0]]( code, calc[1:], identifiers )
            if PRINT_CALC_VALUE:
                PRINT_CALC_VALUE('{}({},{}) -> {}'.format(calc[0], code, calc[1:], fv))
            if not fv:
                return False
            if code.startswith(fv):
                code = code[len(fv):]
            else:
                return False
            results.append(fv)
        
        # Shouldn't be anything left over.
        if code:
            return False
        
        return ''.join(results)

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
        self.calc.semantic_check(self.matchex, self.aliases)
        self.matchex.build_sketch(self.calc)
        return
    
    def match(self, name):
        """See if the name matches our match expression."""
        matches = self.matchex.match(self.calc, self.accounts, self.aliases, name)
        if PRINT_ALIAS_MATCH:
            PRINT_ALIAS_MATCH('{} -> {}'.format(self.matchex.expression_, matches))
        if not matches:
            return []
        return [ SpecMatch(self, matches) ]
    
