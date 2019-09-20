#!/usr/bin/python3

import sys
import unittest

if '..' not in sys.path:
    sys.path.insert(0,'..')

from config import TestBasicParsing, TestParsingConfig, TestParsingAliases, TestMatchexSemantics, TestCalcSemantics, TestUniqueness

if __name__ == '__main__':
    unittest.main(verbosity=2)

