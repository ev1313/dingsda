# -*- coding: utf-8 -*-

from tests.declarativeunittest import *
from construct import *
from construct.lib import *

from xml.etree import ElementTree as ET

def test_toET_struct():
    s = Struct(
        "a" / Int32ul,
        "b" / Int32ul,
    )

    data = {"a": 1, "b": 2}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test a="1" b="2" />')


def test_toET_struct_2():
    s = Struct(
        "a" / Int32ul,
        "b" / Int32ul,
        "s" / Struct(
            "c" / Int32ul,
            "d" / Int32ul,
        ),
        )

    data = {"a": 1, "b": 2, "s": {"c": 3, "d": 4}}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test a="1" b="2"><s c="3" d="4" /></test>')

def test_fromET_struct():
    s = Struct(
        "a" / Int32ul,
        "b" / Int32ul,
    )

    xml = ET.fromstring(b'<test a="1" b="2" />')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": 1, "b": 2})