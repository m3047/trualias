#!/usr/bin/python3

import sys
import unittest

if '..' not in sys.path:
    sys.path.insert(0,'..')

from config import TestBasicParsing, TestParsingConfig, TestParsingAliases, TestMatchexSemantics, TestCalcSemantics, TestUniqueness
from matchex import TestSimpleSketchCases, TestMatchingPrimitives, TestMoreSketchCases, TestCalcFunctions
from lookup import TestAliasNameLookup
from fqdn_vs_ident import TestFQDNvsIdent

if __name__ == '__main__':
    unittest.main(verbosity=2)

