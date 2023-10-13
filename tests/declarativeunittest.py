import pytest
import xml.etree.ElementTree as ET

from typing import Optional

xfail = pytest.mark.xfail
skip = pytest.mark.skip
skipif = pytest.mark.skipif

from dingsda.core import Construct
from dingsda.lib import Container, ONWINDOWS

import binascii

if not ONWINDOWS:
    devzero = open("/dev/zero", "rb")

ident = lambda x: x

def raises(func, *args, **kw):
    try:
        return func(*args, **kw)
    except Exception as e:
        return e.__class__


def common(format: Construct, datasample: bytes, objsample: Container, objsample_build: Optional[Container] = None, **kw):
    r"""
    :param format: the construct to test
    :param datasample: a sample of the data to parse
    :param objsample: the object that should be parsed from the data
    :param objsample_build: an example object that should produce the same datasample (optional). Used to test Rebuilds.
    :param preprocess: whether to preprocess the data before parsing (optional). Used to test special cases, where it is needed.
    :param kw: additional keyword arguments to pass to the context when parsing and building
    """
    # following are implied (re-parse and re-build)
    # assert format.parse(format.build(obj)) == obj
    # assert format.build(format.parse(data)) == data
    obj = format.parse(datasample, **kw)
    assert obj == objsample

    build_object = objsample

    data = format.build(build_object, **kw)
    assert data == datasample

    if objsample_build is not None:
        data2 = format.build(obj)
        assert data2 == datasample


def commonhex(format: Construct, hexdata):
    commonbytes(format, binascii.unhexlify(hexdata))


def commondumpdeprecated(format: Construct, filename: str):
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


def size_test(format: Construct, obj: Container, static_size: Optional[int] = None, size: Optional[int] = None, full_size: Optional[int] = None):
    if static_size is not None:
        assert(format.static_sizeof() == static_size)
    if size is not None:
        assert(format.sizeof(obj) == size)
    if full_size is not None:
        assert(format.full_sizeof(obj) == full_size)

    assert(static_size is not None or size is not None or full_size is not None)
