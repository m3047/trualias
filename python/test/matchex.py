#!/usr/bin/python3

import sys
import unittest

if '..' not in sys.path:
    sys.path.insert(0,'..')
    
import

class TestProtobufVarint(unittest.TestCase):
    """Tests varints of various run lengths."""
    
    def test_varint_01(self):
        """Simplest varint test case."""
        s,v = protobuf.ProtobufField.get_varint('\x01')
        self.assertEqual(s,'',"Buffer should be empty.")
        self.assertEqual(v,1,"Value should be 1.")
        return
    
    def test_varint_8100(self):
        """Deviant case where the upper byte of a varint is all zeros."""
        s,v = protobuf.ProtobufField.get_varint('\x81\x00')
        self.assertEqual(s,'',"Buffer should be empty.")
        self.assertEqual(v,1,"Value should be 1.")
        return

    def test_varint_818000(self):
        """Even more deviant case where the upper byte of a varint is all zeros."""
        s,v = protobuf.ProtobufField.get_varint('\x81\x80\x00')
        self.assertEqual(s,'',"Buffer should be empty.")
        self.assertEqual(v,1,"Value should be 1.")
        return

    def test_varint_83D0FBB809(self):
        """This should be 2535385091."""
        s,v = protobuf.ProtobufField.get_varint('\x83\xd0\xfb\xb8\x09')
        self.assertEqual(s,'',"Buffer should be empty.")
        self.assertEqual(v,2535385091,"Value should be 2535385091.")
        return

class TestProtobufFieldHeader(unittest.TestCase):
    """Field headers define the field id and wire type as a varint."""
    
    def test_field_header_single_byte(self):
        s,id,wtype = protobuf.ProtobufField.get_field_header('\x08')
        self.assertEqual(s,'',"Buffer should be empty.")
        self.assertEqual(id,1,'Expected ID of 1, got '+str(id))
        self.assertEqual(wtype,0,'Expected WType of 0, got '+str(wtype))
        return
    
    def test_field_header_two_bytes(self):
        s,id,wtype = protobuf.ProtobufField.get_field_header('\xd2\x02')
        self.assertEqual(s,'',"Buffer should be empty.")
        self.assertEqual(id,42,'Expected ID of 42, got '+str(id))
        self.assertEqual(wtype,2,'Expected WType of 2, got '+str(wtype))
        return

class TestProtobufZigZag(unittest.TestCase):
    """ZigZag encoding is used for negative numbers."""
    
    def test_zigzag_0(self):
        v = protobuf.ProtobufVarintField.svi2si(0)
        self.assertEqual(v,0,'Expected 0, got '+str(v))
        return
    
    def test_zigzag_pos_1(self):
        v = protobuf.ProtobufVarintField.svi2si(2)
        self.assertEqual(v,1,'Expected 1, got '+str(v))
        return
    
    def test_zigzag_neg_1(self):
        v = protobuf.ProtobufVarintField.svi2si(1)
        self.assertEqual(v,-1,'Expected -1, got '+str(v))
        return
    
    def test_zigzag_pos_3047(self):
        v = protobuf.ProtobufVarintField.svi2si(6094)
        self.assertEqual(v,3047,'Expected 3047, got '+str(v))
        return
    
    def test_zigzag_neg_3047(self):
        v = protobuf.ProtobufVarintField.svi2si(6093)
        self.assertEqual(v,-3047,'Expected -3047, got '+str(v))
        return
    
if __name__ == '__main__':
    unittest.main()
    
