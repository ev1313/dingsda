# -*- coding: utf-8 -*-
from dingsda.numbers import Int8ul, Int16ul, Int32ul
from dingsda.lazy import Lazy, LazyBound
from dingsda.string import PascalString, CString
from tests.declarativeunittest import *
from dingsda import *
from dingsda.core import list_to_string, string_to_list

import xml.etree.ElementTree as ET

def test_list_to_string():
    lst = ["foo","bar","baz"]
    str = list_to_string(lst)
    assert(str == 'foo,bar,baz')

def test_list_to_string_spaces():
    lst = [" foo","bar "," baz "]
    str = list_to_string(lst)
    assert(str == ' foo,bar , baz ')

def test_string_to_list():
    str = 'foo,bar,baz'
    lst = string_to_list(str)
    assert(lst == ["foo","bar","baz"])

def test_quoted_string_to_list():
    str = '"foo","bar","baz"'
    lst = string_to_list(str)
    assert(lst == ["foo","bar","baz"])

def test_xml_struct():
    s = Struct(
        "a" / Int32ul,
        "b" / Int32ul,
    )
    common_xml_test(s, b'<test a="1" b="2" />', {"a": 1, "b": 2})
    common_endtoend_xml_test(s, b'\x01\x00\x00\x00\x02\x00\x00\x00')


def test_xml_struct_2():
    s = Struct(
        "a" / Int32ul,
        "b" / Int32ul,
        "s" / Struct(
            "c" / Int32ul,
            "d" / Int32ul,
        ),
        )
    data = {"a": 1, "b": 2, "s": {"c": 3, "d": 4}}
    xml = b'<test a="1" b="2"><s c="3" d="4" /></test>'
    common_xml_test(s, xml, data)
    common_endtoend_xml_test(s, b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00', data, xml)

def test_xml_struct_3():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Int32ul,
    )
    xml = b'<test a="1" b="2" />'
    obj = {"a": 1, "b": 2}
    common_xml_test(s, xml, obj)
    common_endtoend_xml_test(s, b'\x01\x00\x00\x00\x02\x00\x00\x00', obj, xml)

def test_xml_FormatField_array():
    s = "test" / Struct(
        "a" / Array(2, Int32ul),
        "b" / Int32ul,
        )

    data = {"a": [1,2], "b": 2}
    xml = b'<test a="[1,2]" b="2" />'
    common_xml_test(s, xml, data)

def test_xml_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Int32ul),
        "b" / Array(3, Int32ul),
        )

    xml = b'<test a="[1,1,1,1]" b="[1,2,2]" />'
    obj = {"a": [1,1,1,1], "b": [1,2,2]}
    common_xml_test(s, xml, obj)

def test_xml_struct_unnamed_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Struct("value" / Int32ul)),
        "b" / Array(3, Int32ul),
        )
    obj = {"a": [{"value": 1}], "b": [1,2,2]}
    xml = b'<test b="[1,2,2]"><Struct value="1" /></test>'
    common_xml_test(s, xml, obj)

@xfail(raises=AssertionError, reason="design decision: nested arrays are not supported")
def test_fromET_struct_nested_array():
    s = "test" / Struct(
        "a" / Array(4, Array(4, Int32ul)),
        "b" / Array(3, Array(3, Int32ul)),
        )

    xml = ET.fromstring(b'<test><a>1,1,1,1</a><a>1,1,1,1</a><a>1,1,1,1</a><a>1,1,1,1</a><b>1,2,2</b><b>1,2,2</b><b>1,2,2</b></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]], "b": [[1,2,2],[1,2,2],[1,2,2]]})

def test_fromET_struct_multiple_named_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Int32ul),
        "b" / Array(3, "b_item" / Struct("value" / Int32ul)),
        "c" / Array(3, "c_item" / Struct("value" / Int32ul)),
        )

    # the order of the items is ensured
    xml = ET.fromstring(b'<test a="[1,1,1,1]"><b_item value="1" /><b_item value="2" /><b_item value="3" /><c_item value="5" /></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [1,1,1,1], "b": [{"value": 1}, {"value": 2}, {"value": 3}], "c": [{"value": 5}]})

def test_xml_String_array():
    s = "test" / Struct(
        "a" / Array(2, CString("utf-8")),
        "b" / Int32ul,
        )
    data = {"a": ["foo","bar"], "b": 2}
    xml = b'<test a="[foo,bar]" b="2" />'
    common_xml_test(s, xml, data)

@xfail(raises=AssertionError, reason="design decision: nested arrays are not supported")
def test_toET_nested_String_array():
    s = "test" / Struct(
        "a" / Array(2, Array(2, CString("utf-8"))),
        "b" / Int32ul,
        )

    data = {"a": [["foo", "bar"],["baz", "foobar"]], "b": 2}
    xml = s.toET(obj=data, name="test")

    assert (ET.tostring(xml) == b'<test b="2"><a>[foo,bar]</a><a>[baz,foobar]</a></test>')


def test_xml_rebuild():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Rebuild(Int32ul, lambda ctx: ctx.a + 1),
        )

    data = {"a": 1}
    xml = b'<test a="1" />'
    common_xml_test(s, xml, data)

def test_xml_switch():
    s = "test" / Struct(
        "type" / Rebuild(Int8ul, lambda ctx: ctx._switchid_data),
        "data" / Switch(this.type, {
            1: "b32bit" / Struct("value" / Int32ul),
            2: "b16bit" / Struct("value" / Int16ul),
            3: "test" / Struct("a" / Int32ul, "b" / Int32ul),
        }),
        )
    data = {"type": 1, "data": {"value": 32}}
    data_from = {"data": {"value": 32}}
    xml = b'<test><b32bit value="32" /></test>'
    common_xml_test(s, xml, data, data_from)

def test_xml_switch_2():
    s = "test" / Struct(
        "type" / Rebuild(Int8ul, lambda ctx: ctx._switchid_data),
        "data" / Switch(this.type, {
            1: "b32bit" / Struct("value" / Int32ul),
            2: "b16bit" / Struct("value" / Int16ul),
            3: "test" / Struct("a" / Int32ul, "b" / Int32ul),
        }),
        # do not name the elements in two different switches on the same level the same
        "second" / Switch(this.type, {
            1: "foo" / Struct("value" / Int32ul),
            2: "bar" / Struct("value" / Int16ul),
            3: "baz" / Struct("a" / Int32ul, "b" / Int32ul),
        }),
        )
    data = {"type": 1, "data": {"value": 32}, "second": {"value": 32}}
    data_from = {"data": {"value": 32}, "second": {"value": 32}}
    xml = b'<test><b32bit value="32" /><foo value="32" /></test>'
    common_xml_test(s, xml, data, data_from)


def test_xml_switch_array():
    s = "test" / Struct(
        "a" / Array(2, "foo" / Struct(
            "type" / Rebuild(Int8ul, lambda ctx: ctx._switchid_data),
            "data" / Switch(this.type, {
                1: "b32bit" / Struct("value" / Int32ul),
                2: "b16bit" / Struct("value" / Int16ul),
                3: "test2" / Struct("a" / Int32ul, "b" / Int32ul)
                }),
        )),
        "b" / Array(3, Int32ul),
        )

    xml = b'<test b="[1,2,2]"><foo><b32bit value="32" /></foo><foo><b16bit value="16" /></foo></test>'
    obj_from = {"a": [{"data": {"value": 32}}, {"data": {"value": 16}}], "b": [1,2,2]}
    obj = {"a": [{"type": 1, "data": {"value": 32}}, {"type": 2, "data": {"value": 16}}], "b": [1,2,2]}
    common_xml_test(s, xml, obj, obj_from)


def test_xml_focusedseq():
    s = FocusedSeq("b",
        "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
        "b" / Struct("value" / Int32ul),
        "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
        )

    data = {"value": 2}
    xml = b'<test value="2" />'
    common_xml_test(s, xml, data)


def test_xml_focusedseq_struct():
    s = Struct("a" / FocusedSeq("b",
                   "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                   "b" / Struct("value" / Int32ul),
                   "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                ))

    data = {"a": {"value": 2}}
    xml = b'<test><a value="2" /></test>'
    common_xml_test(s, xml, data)

def test_xml_focusedseq_array():
    s = Struct("arr" / Array(2, "a" / FocusedSeq("b",
                                "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                "b" / Struct("value" / Int32ul),
                                "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                )))

    data = {"arr": [{"value": 4}, {"value": 2}]}
    xml = b'<test><a value="4" /><a value="2" /></test>'
    common_xml_test(s, xml, data)


def test_xml_focusedseq_unnamed_array():
    s = Struct("arr" / Array(2, FocusedSeq("b",
                                                 "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                                 "b" / Struct("value" / Int32ul),
                                                 "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                                 )))

    data = {"arr": [{"value": 4}, {"value": 2}]}
    xml = b'<test><b value="4" /><b value="2" /></test>'
    common_xml_test(s, xml, data)

@xfail(raises=AssertionError, reason="design decision: nested arrays are not supported")
def test_xml_switch_focusedseq():
    s = "test" / Struct(
        "a" / Array(2, FocusedSeq("data",
                                          "type" / Rebuild(Int8ul, lambda ctx: ctx._switchid_data),
                                          "data" / Switch(this.type, {
                                              1: "b32bit" / Struct("value" / Int32ul),
                                              2: "b16bit" / Struct("value" / Int16ul),
                                              3: "test2" / Struct("a" / Int32ul, "b" / Int32ul)
                                          }),
                                          )),
        "b" / Array(3, Int32ul),
        )
    obj = {"a": [{"type": 1, "data": {"value": 32}}, {"type": 1, "data": {"value": 16}}], "b": [1, 2, 2]}
    obj_from = {"a": [{"data": {"value": 32}}, {"data": {"value": 16}}], "b": [1, 2, 2]}
    xml = b'<test b="[1,2,2]"><b32bit value="32" /><b32bit value="16" /></test>'
    common_xml_test(s, xml, obj, obj_from)

@xfail(raises=AssertionError, reason="design decision: nested arrays are not supported")
def test_fromET_switch_focusedseq():
    s = "test" / Struct(
        "a" / Array(2, FocusedSeq("data",
            "type" / Rebuild(Int8ul, lambda ctx: ctx._switchid_data),
            "data" / Switch(this.type, {
                1: "b32bit" / Struct("value" / Int32ul),
                2: "b16bit" / Struct("value" / Int16ul),
                3: "test2" / Struct("a" / Int32ul, "b" / Int32ul)
            }),
            )),
        "b" / Array(3, Int32ul),
        )

    xml = ET.fromstring(b'<test b="[1,2,2]"><b32bit value="32" /><b32bit value="16" /></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [{"data": {"value": 32}}, {"data": {"value": 16}}], "b": [1,2,2]})

def test_xml_prefixedarray():
    s = Struct(
        "a" / PrefixedArray(Int32ul, "Property" / Struct("x" / Int32ul)),
        "b" / Int32ul,
        )

    data = {"a": [{"x": 0}, {"x": 1}, {"x": 4}], "b": 2}
    xml = b'<test b="2"><Property x="0" /><Property x="1" /><Property x="4" /></test>'
    common_xml_test(s, xml, data)

def test_xml_repeatuntil():
    s = Struct(
        "a" / RepeatUntil(lambda obj, lst, ctx: obj.x == 0x4, "Property" / Struct("x" / Int32ul)),
        "b" / Int32ul,
        )

    data = {"a": [{"x": 0}, {"x": 1}, {"x": 4}], "b": 2}
    xml = b'<test b="2"><Property x="0" /><Property x="1" /><Property x="4" /></test>'
    common_xml_test(s, xml, data)

def test_xml_pointer():
    s = Struct(
        "b" / Int32ul,
        "a" / Pointer(lambda obj: int(obj.x), "Property" / Struct("x" / Int32ul)),
        )

    data = {"b": 2, "a": {"x": 0}}
    xml = b'<test b="2"><Property x="0" /></test>'
    common_xml_test(s, xml, data)


def test_xml_pointer_2():
    s = "test" / Struct(
        "b" / Int32ul,
        "a" / Pointer(lambda obj: int(obj.x), "Property" / Struct("x" / Int32ul)),
        )

    xml = b'<test b="2"><Property x="4" /></test>'
    obj = {"b": 2, "a": {"x": 4}}
    common_xml_test(s, xml, obj)

def test_xml_lazy():
    s = Struct(
        "b" / Int32ul,
        "a" / Lazy("Property" / Struct("x" / Int32ul)),
        )

    data = {"b": 2, "a": {"x": 0}}
    xml = b'<test b="2"><Property x="0" /></test>'
    common_xml_test(s, xml, data)


def test_xml_lazy_2():
    s = Struct(
        "b" / Int32ul,
        "a" / Lazy("Property" / Struct("x" / Int32ul)),
        )

    xml = b'<test b="2"><Property x="4" /></test>'
    obj = {"b": 2, "a": {"x": 4}}
    common_xml_test(s, xml, obj)


def test_xml_lazybound():
    p = "Property" / Struct("x" / Int32ul)
    s = Struct(
        "b" / Int32ul,
        "a" / LazyBound(lambda: p),
        )

    data = {"b": 2, "a": {"x": 0}}
    xml = b'<test b="2"><Property x="0" /></test>'
    common_xml_test(s, xml, data)

def test_xml_lazybound_2():
    p = "Property" / Struct("x" / Int32ul)
    s = Struct(
        "b" / Int32ul,
        "a" / LazyBound(lambda: p),
        )

    xml = b'<test b="2"><Property x="4" /></test>'
    obj = {"b": 2, "a": {"x": 4}}
    common_xml_test(s, xml, obj)

def test_xml_lazybound_nested():
    NestedType = Struct(
        "typeId" / Rebuild(Int32ul, this._switchid_data),
        "data" / Switch(this.typeId, {
            0x00000000: "Boolean" / Struct("value" / Enum(Int8ul, false=0, true=1)),
            0x00000001: "Int8" / Struct("value" / Int8ul),
            0x00000011: "ListItem" / PrefixedArray(Int32ul, "ListItem" / LazyBound(lambda: NestedType)),
        }))

    obj = {"typeId": 0x00000011, "data": [{"typeId": 0x00000000, "data": {"value": "true"}}, {"typeId": 0x00000001, "data": {"value": 0x01}}]}
    obj_from = {"data": [{"data": {"value": "true"}}, {"data": {"value": 0x01}}]}
    xml = b'<test><ListItem><Boolean value="true" /></ListItem><ListItem><Int8 value="1" /></ListItem></test>'
    common_xml_test(NestedType, xml, obj, obj_from)


def test_xml_const():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Const(b"test"),
        )

    xml = b'<test a="1" />'
    obj = {"a": 1}
    common_xml_test(s, xml, obj)


def test_xml_enum():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Enum(Int32ul, test=1, foo=2, bar=3),
        )

    data = {"a": 1, "b": "foo"}
    data_from = {"a": 1, "b": 2}
    xml = b'<test a="1" b="foo" />'
    common_xml_test(s, xml, data)


def test_xml_enum_2():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Enum(Int32ul, test=1, foo=2, bar=3),
        )

    xml = b'<test a="1" b="foo" />'
    obj = {"a": 1, "b": "foo"}
    common_xml_test(s, xml, obj)

def test_xml_bytes():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Bytes(4),
        )

    data = {"a": 1, "b": b"fooo"}
    xml = b'<test a="1" b="666f6f6f" />'

def test_xml_ifthenelse_formatfield():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / Int16ul, "bar" / Int32ul)
        )

    data = {"a": 1, "b": 2}
    xml = b'<test a="1" foo="2" />'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_formatfield_rebuild_hack():
    s = "test" / Struct(
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / Int16ul, "bar" / Int32ul, rebuild_hack=True),
        "a" / Int32ul,
    )

    data = {"a": 1, "b": 2}
    xml = b'<test foo="2" a="1" />'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_string():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / PascalString(4, "utf-8"), "bar" / Int32ul)
    )

    data = {"a": 1, "b": "test"}
    xml = b'<test a="1" foo="test" />'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_string_rebuildhack():
    s = "test" / Struct(
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / PascalString(4, "utf-8"), "bar" / Int32ul, rebuild_hack=True),
        "a" / Int32ul,
    )

    data = {"a": 1, "b": "test"}
    xml = b'<test foo="test" a="1" />'
    common_xml_test(s, xml, data)


def test_xml_ifthenelse_struct():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / Struct("bar" / Int32ul), "bar" / Struct("bar" / Int16ul))
    )

    data = {"a": 1, "b": {"bar": 3}}
    xml = b'<test a="1"><foo bar="3" /></test>'
    common_xml_test(s, xml, data)


def test_xml_ifthenelse_rebuildhack_struct():
    s = "test" / Struct(
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / Struct("bar" / Int32ul), "bar" / Struct("bar" / Int16ul), rebuild_hack=True),
        "a" / Int32ul,
    )

    data = {"a": 1, "b": {"bar": 3}}
    xml = b'<test a="1"><foo bar="3" /></test>'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_pass():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / Struct("bar" / Int32ul), Pass)
    )

    data = {"a": 1, "b": {"bar": 3}}
    xml = b'<test a="1"><foo bar="3" /></test>'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_pass_rebuildhack():
    s = "test" / Struct(
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / Struct("bar" / Int32ul), Pass, rebuild_hack=True),
        "a" / Int32ul,
    )

    data = {"a": 1, "b": {"bar": 3}}
    xml = b'<test a="1"><foo bar="3" /></test>'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_pass_unnamed_rebuildhack():
    s = "test" / Struct(
        "b" / IfThenElse(lambda obj: obj.a == 1, Struct("bar" / Int32ul), Pass, rebuild_hack=True),
        "a" / Int32ul,
        )

    data = {"a": 1, "b": {"bar": 3}}
    xml = b'<test a="1"><b bar="3" /></test>'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_pass_unnamed_rebuildhack_2():
    s = "test" / Struct(
        "b" / IfThenElse(lambda obj: obj.a == 1, Struct("bar" / Int32ul), Pass, rebuild_hack=True),
        "a" / Int32ul,
        )

    data = {"a": 0}
    xml = b'<test a="0" />'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_pass_2():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / IfThenElse(lambda obj: obj.a == 1, "foo" / Struct("bar" / Int32ul), Pass)
    )

    data = {"a": 0}
    xml = b'<test a="0" />'
    common_xml_test(s, xml, data)


def test_xml_ifthenelse_array():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / IfThenElse(lambda obj: obj.a == 1, Array(4, Int32ul), Pass)
    )

    data = {"a": 1, "b": [1,2,3,4]}
    xml = b'<test a="1" b="[1,2,3,4]" />'
    common_xml_test(s, xml, data)

def test_xml_ifthenelse_pass_unnamed_array_rebuildhack():
    s = "test" / Struct(
        "b" / IfThenElse(lambda obj: obj.a == 1, Array(4, Int32ul), Pass, rebuild_hack=True),
        "a" / Int32ul,
        )

    data = {"a": 1, "b": [1,2,3,4]}
    xml = b'<test b="[1,2,3,4]" a="1" />'
    common_xml_test(s, xml, data)

def test_xml_pass():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Pass,
        "c" / Int32ul,
        )

    data = {"a": 1, "c": 2}
    xml = b'<test a="1" c="2" />'
    common_xml_test(s, xml, data)
