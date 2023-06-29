# -*- coding: utf-8 -*-

from tests.declarativeunittest import *
from dingsda import *
from dingsda.lib import *
from dingsda.core import list_to_string, string_to_list

from xml.etree import ElementTree as ET

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

    data = {"a": [1,2], "b": 2}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test a="[1,2]" b="2" />')

def test_fromET_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Int32ul),
        "b" / Array(3, Int32ul),
        )

    xml = ET.fromstring(b'<test a="[1,1,1,1]" b="[1,2,2]" />')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [1,1,1,1], "b": [1,2,2]})

def test_toET_struct_unnamed_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Struct("value" / Int32ul)),
        "b" / Array(3, Int32ul),
        )

    obj = {"a": [{"value": 1}], "b": [1,2,2]}
    xml = s.toET(obj=obj, name="test")
    assert(ET.tostring(xml) == b'<test b="[1,2,2]"><Struct value="1" /></test>')

def test_fromET_struct_unnamed_struct_array():
    s = "test" / Struct(
        "a" / Array(4, Struct("value" / Int32ul)),
        "b" / Array(3, Int32ul),
        )

    xml = ET.fromstring(b'<test b="[1,2,2]"><Struct value="1"/></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [{"value": 1}], "b": [1,2,2]})

def test_fromET_struct_named_struct_array():
    s = "test" / Struct(
        "a" / Array(4, "Foo" / Struct("value" / Int32ul)),
        "b" / Array(3, Int32ul),
        )

    xml = ET.fromstring(b'<test b="[1,2,2]"><Foo value="1"/></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [{"value": 1}], "b": [1,2,2]})

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

def test_toET_String_array():
    s = "test" / Struct(
        "a" / Array(2, CString("utf-8")),
        "b" / Int32ul,
        )

    data = {"a": ["foo","bar"], "b": 2}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test a="[foo,bar]" b="2" />')

def test_toET_nested_String_array():
    s = "test" / Struct(
        "a" / Array(2, Array(2, CString("utf-8"))),
        "b" / Int32ul,
        )

    data = {"a": [["foo", "bar"],["baz", "foobar"]], "b": 2}
    xml = s.toET(obj=data, name="test")

    assert (ET.tostring(xml) == b'<test b="2"><a>[foo,bar]</a><a>[baz,foobar]</a></test>')


def test_toET_rebuild():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Rebuild(Int32ul, lambda ctx: ctx.a + 1),
        )

    data = {"a": 1}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test a="1" />')


def test_fromET_rebuild():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Rebuild(Int32ul, lambda ctx: ctx.a + 1),
        )

    xml = ET.fromstring(b'<test a="1" />')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": 1, "b": None})

def test_toET_switch():
    s = "test" / Struct(
        "type" / Rebuild(Int8ul, lambda ctx: ctx._switchid_data),
        "data" / Switch(this.type, {
            1: "b32bit" / Struct("value" / Int32ul),
            2: "b16bit" / Struct("value" / Int16ul),
            3: "test" / Struct("a" / Int32ul, "b" / Int32ul),
        }),
        )
    data = {"type": 1, "data": {"value": 32}}
    xml = s.toET(obj=data, name="test")

    assert (ET.tostring(xml) == b'<test><b32bit value="32" /></test>')

def test_toET_switch_array():
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
    obj = {"a": [{"type": 1, "data": {"value": 32}}, {"type": 2, "data": {"value": 16}}], "b": [1,2,2]}
    xml = s.toET(obj=obj, name="test")
    assert(ET.tostring(xml) == b'<test b="[1,2,2]"><foo><b32bit value="32" /></foo><foo><b16bit value="16" /></foo></test>')


def test_fromET_switch():
    s = "test" / Struct(
        "type" / Rebuild(Int8ul, lambda ctx: ctx._switchid_data),
        "data" / Switch(this.type, {
            1: "b32bit" / Struct("value" / Int32ul),
            2: "b16bit" / Struct("value" / Int16ul),
            3: "test2" / Struct("a" / Int32ul, "b" / Int32ul),
            }),
    )
    xml = ET.fromstring(b'<test><b32bit value="32" /></test>')
    obj = s.fromET(xml=xml)

def test_toET_switch_2():
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
    xml = s.toET(obj=data, name="test")

    assert (ET.tostring(xml) == b'<test><b32bit value="32" /><foo value="32" /></test>')


def test_fromET_switch_array():
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

    xml = ET.fromstring(b'<test b="[1,2,2]"><foo><b32bit value="32" /></foo><foo><b16bit value="16" /></foo></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [{"type": None, "b32bit": None, "data": {"value": 32}}, {"type": None, "b16bit": None, "data": {"value": 16}}], "b": [1,2,2]})


def test_toET_focusedseq():
    s = FocusedSeq("b",
        "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
        "b" / Struct("value" / Int32ul),
        "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
        )

    data = {"value": 2}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test value="2" />')


def test_fromET_focusedseq():
    s = "test" / FocusedSeq("b",
                   "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                   "b" / Struct("value" / Int32ul),
                   "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                   )
    xml = ET.fromstring(b'<test value="2" />')
    obj = s.fromET(xml=xml)

    data = {"value": 2}
    assert(obj == data)

def test_toET_focusedseq_struct():
    s = Struct("a" / FocusedSeq("b",
                   "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                   "b" / Struct("value" / Int32ul),
                   "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                ))

    data = {"a": {"value": 2}}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test><a value="2" /></test>')


def test_fromET_focusedseq_struct():
    s = "test" / Struct( "a" / FocusedSeq("b",
                            "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                            "b" / Struct("value" / Int32ul),
                            "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                          ))
    xml = ET.fromstring(b'<test><a value="2" /></test>')
    obj = s.fromET(xml=xml)

    data = {"b": None, "a": {"value": 2}}
    assert(obj == data)

def test_toET_focusedseq_array():
    s = Struct("arr" / Array(2, "a" / FocusedSeq("b",
                                "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                "b" / Struct("value" / Int32ul),
                                "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                )))

    data = {"arr": [{"value": 4}, {"value": 2}]}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test><a value="4" /><a value="2" /></test>')


def test_fromET_focusedseq_array():
    s = "test" / Struct( "arr" / Array(2, "a" / FocusedSeq("b",
                                          "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                          "b" / Struct("value" / Int32ul),
                                          "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                                   )))
    xml = ET.fromstring(b'<test><a value="4" /><a value="2" /></test>')
    obj = s.fromET(xml=xml)

    data = {"arr": [{"value": 4}, {"value": 2}]}
    assert(obj == data)


def test_toET_focusedseq_unnamed_array():
    s = Struct("arr" / Array(2, FocusedSeq("b",
                                                 "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                                 "b" / Struct("value" / Int32ul),
                                                 "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                                 )))

    data = {"arr": [{"value": 4}, {"value": 2}]}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test><b value="4" /><b value="2" /></test>')


def test_fromET_focusedseq_unnamed_array():
    s = "test" / Struct( "arr" / Array(2, FocusedSeq("b",
                                                           "a" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                                           "b" / Struct("value" / Int32ul),
                                                           "c" / Rebuild(Int32ul, lambda ctx: ctx._.b.value),
                                                           )))
    xml = ET.fromstring(b'<test><b value="4" /><b value="2" /></test>')
    obj = s.fromET(xml=xml)

    data = {"arr": [{"value": 4}, {"value": 2}]}
    assert(obj == data)

def test_toET_switch_focusedseq():
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
    elem = s.toET(obj=obj, name="test")
    xml = ET.tostring(elem)
    assert(xml == b'<test b="[1,2,2]"><b32bit value="32" /><b32bit value="16" /></test>')

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

def test_toET_repeatuntil():
    s = Struct(
        "a" / RepeatUntil(lambda obj, lst, ctx: obj.x == 0x4, "Property" / Struct("x" / Int32ul)),
        "b" / Int32ul,
        )

    data = {"a": [{"x": 0}, {"x": 1}, {"x": 4}], "b": 2}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test b="2"><Property x="0" /><Property x="1" /><Property x="4" /></test>')

def test_fromET_repeatuntil():
    s = "test" / Struct(
        "a" / RepeatUntil(lambda obj, lst, ctx: obj.x == 0x4, "Property" / Struct("x" / Int32ul)),
        "b" / Int32ul,
        )

    xml = ET.fromstring(b'<test b="2"><Property x="0" /><Property x="1" /><Property x="4" /></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": [{"x": 0}, {"x": 1}, {"x": 4}], "b": 2})

def test_toET_pointer():
    s = Struct(
        "b" / Int32ul,
        "a" / Pointer(lambda obj: int(obj.x), "Property" / Struct("x" / Int32ul)),
        )

    data = {"b": 2, "a": {"x": 0}}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test b="2"><Property x="0" /></test>')


def test_fromET_pointer():
    s = "test" / Struct(
        "b" / Int32ul,
        "a" / Pointer(lambda obj: int(obj.x), "Property" / Struct("x" / Int32ul)),
        )

    xml = ET.fromstring(b'<test b="2"><Property x="4" /></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"b": 2, "Property": None, "a": {"x": 4}})

def test_toET_lazy():
    s = Struct(
        "b" / Int32ul,
        "a" / Lazy("Property" / Struct("x" / Int32ul)),
        )

    data = {"b": 2, "a": {"x": 0}}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test b="2"><Property x="0" /></test>')


def test_fromET_lazy():
    s = Struct(
        "b" / Int32ul,
        "a" / Lazy("Property" / Struct("x" / Int32ul)),
        )

    xml = ET.fromstring(b'<test b="2"><Property x="4" /></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"b": 2, "Property": None, "a": {"x": 4}})

def test_toET_lazybound():
    p = "Property" / Struct("x" / Int32ul)
    s = Struct(
        "b" / Int32ul,
        "a" / LazyBound(lambda: p),
        )

    data = {"b": 2, "a": {"x": 0}}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test b="2"><Property x="0" /></test>')


def test_fromET_lazybound():
    p = "Property" / Struct("x" / Int32ul)
    s = Struct(
        "b" / Int32ul,
        "a" / LazyBound(lambda: p),
        )

    xml = ET.fromstring(b'<test b="2"><Property x="4" /></test>')
    obj = s.fromET(xml=xml)

    assert(obj == {"b": 2, "Property": None, "a": {"x": 4}})

def test_toET_const():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Const(b"test"),
        )

    data = {"a": 1}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test a="1" />')


def test_fromET_const():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Const(b"test"),
        )

    xml = ET.fromstring(b'<test a="1" />')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": 1, "b": None})


def test_toET_enum():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Enum(Int32ul, test=1, foo=2, bar=3),
        )

    data = {"a": 1, "b": 2}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test a="1" b="foo" />')


def test_fromET_enum():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Enum(Int32ul, test=1, foo=2, bar=3),
        )

    xml = ET.fromstring(b'<test a="1" b="foo"/>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": 1, "b": "foo"})

def test_toET_bytes():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Bytes(4),
        )

    data = {"a": 1, "b": b"fooo"}
    xml = s.toET(obj=data, name="test")

    assert(ET.tostring(xml) == b'<test a="1" b="666f6f6f" />')


def test_fromET_bytes():
    s = "test" / Struct(
        "a" / Int32ul,
        "b" / Bytes(4),
        )

    xml = ET.fromstring(b'<test a="1" b="666f6f6f"/>')
    obj = s.fromET(xml=xml)

    assert(obj == {"a": 1, "b": b"fooo"})
