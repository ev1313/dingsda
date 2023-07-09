import pytest

xfail = pytest.mark.xfail
skip = pytest.mark.skip
skipif = pytest.mark.skipif

import os, math, random, collections, itertools, io, hashlib, binascii

from xml.etree import ElementTree as ET

from dingsda import *
from dingsda.lib import *

if not ONWINDOWS:
    devzero = open("/dev/zero", "rb")

ident = lambda x: x

def raises(func, *args, **kw):
    try:
        return func(*args, **kw)
    except Exception as e:
        return e.__class__

def common(format, datasample, objsample, sizesample=SizeofError, **kw):
    # following are implied (re-parse and re-build)
    # assert format.parse(format.build(obj)) == obj
    # assert format.build(format.parse(data)) == data
    obj = format.parse(datasample, **kw)
    assert obj == objsample
    data = format.build(objsample, **kw)
    assert data == datasample

    if isinstance(sizesample, int):
        size = format.sizeof(**kw)
        assert size == sizesample
    else:
        size = raises(format.sizeof, **kw)
        assert size == sizesample

def commonhex(format, hexdata):
    commonbytes(format, binascii.unhexlify(hexdata))

def commondumpdeprecated(format, filename):
    filename = "tests/deprecated_gallery/blobs/" + filename
    with open(filename,'rb') as f:
        data = f.read()
    commonbytes(format, data)

def commondump(format, filename):
    filename = "tests/gallery/blobs/" + filename
    with open(filename,'rb') as f:
        data = f.read()
    commonbytes(format, data)

def commonbytes(format, data):
    obj = format.parse(data)
    data2 = format.build(obj)

def common_xml_test(s, xml, obj, obj_from = None):
    if obj_from is None:
        obj_from = obj
    test_et = ET.fromstring(xml)
    test_obj = s.fromET(xml=test_et)
    assert(obj_from == test_obj)
    test_xml = s.toET(obj=obj, name="test")
    test_xml_str = ET.tostring(test_xml)
    assert(test_xml_str == xml)

def common_endtoend_xml_test(s, byte_data, obj=None, xml=None):
    data = s.parse(byte_data)
    if obj is not None:
        assert(data == obj)
    test_xml = s.toET(obj=data, name="test")
    if xml is not None:
        assert(ET.tostring(test_xml) == xml)
    xml_data = s.fromET(xml=test_xml)
    assert(byte_data == s.build(xml_data))

