# -*- coding: utf-8 -*-

from tests.declarativeunittest import *
from construct import *
from construct.lib import *
from construct.core import list_to_string, string_to_list

from xml.etree import ElementTree as ET

def test_list_to_string():
    lst = ["foo","bar","baz"]
    str = list_to_string(lst)
    assert(str == 'foo,bar,baz')

def test_string_to_list():
    str = 'foo,bar,baz'
    lst = string_to_list(str)
    assert(lst == ["foo","bar","baz"])

def test_quoted_string_to_list():
    str = '"foo","bar","baz"'
    lst = string_to_list(str)
    assert(lst == ["foo","bar","baz"])

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
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Int32ul,
    )

    xml = ET.fromstring(b'<test a="1" b="2" />')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": 1, "b": 2})

def test_toET_FormatField_array():
    s = "test" / Struct(
        "a" / Array(2, Int32ul),
        "b" / Int32ul,
        )

    xml = ET.fromstring(b'<test a="[1,2]" b="2" />')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [1, 2], "b": 2})

def test_fromET_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Int32ul),
        "b" / Array(3, Int32ul),
        )

    xml = ET.fromstring(b'<test a="[1,1,1,1]" b="[1,2,2]" />')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [1,1,1,1], "b": [1,2,2]})


def test_fromET_struct_unnamed_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Struct("value" / Int32ul)),
        "b" / Array(3, Int32ul),
        )

    xml = ET.fromstring(b'<test b="[1,2,2]"><a value="1"></a></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [{"value": 1}], "b": [1,2,2]})

def test_fromET_struct_named_struct_array():
    s = "test" / Struct(
        "a" / Array(4, "Foo" / Struct("value" / Int32ul)),
        "b" / Array(3, Int32ul),
        )

    xml = ET.fromstring(b'<test b="[1,2,2]"><Foo value="1"></a></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [{"value": 1}], "b": [1,2,2]})

def test_fromET_struct_nested_array():
    s = "test" / Struct(
        "a" / Array(4, Array(4, Int32ul)),
        "b" / Array(3, Array(3, Int32ul)),
        )

    xml = ET.fromstring(b'<test a="[[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]]" b="[[1,2,2],[1,2,2],[1,2,2]]" />')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]], "b": [[1,2,2],[1,2,2],[1,2,2]]})

def test_fromET_struct_multiple_named_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Int32ul),
        "b" / Array(3, "b_item" / Struct("value" / Int32ul)),
        "c" / Array(3, "c_item" / Struct("value" / Int32ul)),
        )

    xml = ET.fromstring(b'<test a="[1,1,1,1]"><b_item value="1" /><b_item value="2" /><b_item value="3" /><c_item value="5"></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [1,1,1,1], "b": [{"value": 1}, {"value": 2}, {"value": 3}], "c": [{"value": 5}]})