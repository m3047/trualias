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

"""Matching.

The classes in this module match things. The basic concept is to match character
sets; every match can have potentially three separate matchers:

* first character
* interior characters
* last character

There are special matchers for "anything" and codes. Code matchers are built on
the fly from the calc functions specified in an ACCOUNT declaration.
"""

MATCH_ALPHA = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
MATCH_NUMBER = set('1234567890')
MATCH_ALNUM = MATCH_ALPHA | MATCH_NUMBER
MATCH_FQDN = MATCH_ALNUM | set('.-')
MATCH_IDENT = MATCH_ALNUM | set('_')

class Matcher(object):
    """Matches stuff in the address."""
    def __init__(self,*char_sets):
        if len(char_sets) == 2 or len(char_sets) == 4:
            self.name = char_sets[0]
            char_sets = char_sets[1:]
        else:
            self.name = None
        if len(char_sets) == 1:
            char_sets = (char_sets[0],char_sets[0],char_sets[0])
        self.char_sets = char_sets
        return
    
    def __repr__(self):
        name = getattr(self, 'name', None)
        if name is None:
            name = '<+' + ', '.join(( '{'+''.join((c for c in s))+'}' for s in self.char_sets )) + '+>'
        return name
    
    def __call__(self, address, start_pos=0, end_pos=None, minimal=False):
        """Returns a (zero based) starting and ending position tuple.
        
        Match control:
            end_pos:    If specified, then the substring must match exactly.
            minimal:    If true, then a minimal match is performed. If false,
                        the match is maximal.
            both:       If both end_pos and minimal are specified, then the
                        match is minimal but at least as long as the offset
                        of end_pos.
        """
        if start_pos >= len(address):
            return None
        start_chars, middle_chars, end_chars = self.char_sets
       
        # Match a fixed string.
        if not (end_pos is None or minimal):
            to_match = address[start_pos:end_pos]
            if to_match and to_match[0] in start_chars and to_match[-1] in end_chars:
                if len(to_match) > 2:
                    if not set(to_match[1:-1]) <= middle_chars:
                        return None
                return (start_pos, end_pos)
            return None

        valid_end_pos = None
        test_pos = start_pos
        while test_pos < len(address):
            test_char = address[test_pos]
            if test_char in end_chars:
                valid_end_pos = test_pos
                if minimal and (end_pos is None or test_pos >= end_pos):
                    break
            if test_char not in middle_chars:
                # Can't be any longer than this because the char isn't suitable for a middle.
                break
            test_pos += 1
        if valid_end_pos is None:
            return None
        
        return (start_pos, valid_end_pos)
    
    def match_one_more(self, address, start_pos, end_pos):
        """Returns True if address[start_pos:end_pos+1] is also a valid match.
        
        address[start_pos:end_pos] is presumed to be a known valid match.
        
        Special case of end_pos = start_pos - 1 is used to test the start of
        a match.
        """
        if start_pos >= len(address):
            return False
        if (end_pos + 1) >= len(address):
            return False
        if end_pos < start_pos and address[start_pos] not in self.char_sets[0]:
                return False
        if address[end_pos+1] not in self.char_sets[2]:
            return False
        if end_pos > start_pos and address[end_pos] not in self.char_sets[1]:
            return False
        
        return True
    
    def copy(self, name):
        """Copy a Matcher giving it a new name.
        
        The list of character sets is referenced, not copied.
        """
        return Matcher(name,*self.char_sets)
    
class MatchAny(Matcher):
    """Matches anything and everything!
    
    Subclassed from Matcher for no good functional but every good
    nonfunctional reason.
    """
    def __init__(self,*args):
        self.name = args and args[0] or ''
        return
    
    def __repr__(self):
        name = getattr(self, 'name', None)
        if name is None:
            name = '<+ .* +>'
        return name
    
    def __call__(self, address, start_pos=0, end_pos=None, minimal=False):
        if start_pos >= len(address) or end_pos is not None and end_pos >= len(address):
            return None
        if end_pos is not None:
            if end_pos < start_pos:
                end_pos = start_pos
            return start_pos, end_pos
        return start_pos, ((not minimal) and (len(address) - 1) or start_pos)
    
    def match_one_more(self, address, start_pos, end_pos):
        if start_pos >= len(address):
            return False
        if (end_pos + 1) >= len(address):
            return False
        return True

class MatchCode(MatchAny):
    """Special matcher for computed codes.
    
    Depending on what the calc is, there can be different matching requirements.
    """
    MATCH_TYPES = { 'number', 'any' }
    
    def __init__(self,name=None):
        self.name = name or ''
        self.char_sets = []     # Different contents than Matcher.
        self.anchors = None
        return

    def __repr__(self):
        name = getattr(self, 'name', 'code')
        return '{}{}'.format(name, self.char_sets)

    def build_anchors(self):
        if self.anchors:
            return
        self.anchors = [0]
        for match in self.char_sets:
            if match == 'any':
                self.anchors[-1] += 1
            else:
                self.anchors.append(0)
        self.end_group_size = 0
        while (self.end_group_size + 1) < len(self.anchors) and not self.anchors[-1 - self.end_group_size]:
            self.end_group_size += 1
        self.min_chars = sum(self.anchors) + len(self.anchors) - 1
        return

    def __call__(self, address, start_pos=0, end_pos=None, minimal=False):
        self.build_anchors()
        if start_pos >= len(address) or end_pos and end_pos >= len(address):
            return None

        n_at_start = self.anchors[0] == 0
        n_at_end = self.anchors[-1] == 0
        
        # Case where the matcher starts with a number.
        if n_at_start and address[start_pos] not in MATCH_NUMBER:
            return None
        # Case where the matcher ends with a number and end position is specified.
        if n_at_end and end_pos and address[end_pos] not in MATCH_NUMBER:
            return None
        
        # Start with a minimal match.
        minimal_end = start_pos
        for i in range(len(self.anchors)):
            # On subsequent matches
            if i > 0:
                while True:
                    if minimal_end >= len(address):
                        return None
                    if address[minimal_end] in MATCH_NUMBER:
                        break
                    minimal_end += 1
                minimal_end += 1
            # Skip a minimal number of any characters.
            minimal_end += self.anchors[i]
            if minimal_end >= len(address) and not (i + 1) >= len(self.anchors):
                return None
        minimal_end -= 1
        
        # More end_pos edge cases.
        if minimal:
            return start_pos, minimal_end
        if end_pos is not None:
            if end_pos == minimal_end:
                return start_pos, minimal_end
            if end_pos < minimal_end:
                if minimal:
                    return start_pos, minimal_end
                else:
                    return None
            # Fallthru: end_pos > minimal_end
            
        # If the last matcher is any, then we can expand the match at will.
        # Otherwise our maximal match will be determined by where the last numeral
        # is.
        if n_at_end:
            # Any n's grouped together at the end must be dealt with together.
            if end_pos:
                if not set(address[end_pos-self.end_group_size+1:end_pos+1]) <= MATCH_NUMBER:
                    return None
            else:
                end_pos = minimal_end
                curr_pos = minimal_end + 1
                while True:
                    if set(address[curr_pos-self.end_group_size+1:curr_pos+1]) <= MATCH_NUMBER:
                        end_pos = curr_pos
                    curr_pos += 1
                    if curr_pos >= len(address):
                        break

        return start_pos, end_pos or len(address) - 1
    
    def match_one_more(self, address, start_pos, end_pos):
        self.build_anchors()
        if start_pos >= len(address):
            return False
        if (end_pos + 1) >= len(address):
            return False
        if (end_pos - start_pos) + 1 < self.min_chars:
            return False
        return set(address[end_pos-self.end_group_size+2:end_pos+2]) <= MATCH_NUMBER
    
    def append(self, match_type):
        """Appends things to char_sets.
        
        char_sets contains strings indicating the match type rather than actual
        character matchers.
        """
        if match_type not in self.MATCH_TYPES:
            raise ValueError('Value must be in MATCH_TYPES.')
        self.char_sets.append(match_type)
        self.anchors = None
        return

