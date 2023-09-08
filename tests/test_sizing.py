# -*- coding: utf-8 -*-
import hashlib
from tests.declarativeunittest import *
from dingsda import *
from dingsda.numbers import *
from dingsda.string import *
from dingsda.lazy import *
from dingsda.lib import *
from dingsda.date import Timestamp

def test_size_array_different():
    # test elements with differing sizes like Switch
    d = Array(3, Struct("test" / Byte, "x" / Switch(this.test, {1: "a" / Byte, 2: "b" / Int16ub, 3: "c" / Int32ub})))
    size_test(d, [{"test": 1, "x": 1},{"test": 1, "x": 2},{"test": 1, "x": 3}], size=6)
    size_test(d, [{"test": 1, "x": 1},{"test": 2, "x": 2},{"test": 1, "x": 3}], size=7)
    size_test(d, [{"test": 1, "x": 1},{"test": 2, "x": 2},{"test": 3, "x": 3}], size=10)

def test_size_pascalstring():
    # PascalString is a macro using GreedyBytes
    d = PascalString(Byte, "utf8")
    size_test(d, "test", size=5)

def test_size_prefixedarray():
    d = PrefixedArray(Byte, Byte)
    size_test(d, [1,2,3], size=4)

def test_size_rebuild_array():
    d = Rebuild(Array(3, Byte), lambda x: [1,2,3])
    size_test(d, [1,2, 3], size=3)

    d = Struct("asd" / Int32ul,
                "foo" / Rebuild(Int32ul, lambda ctx: 4),
               "test" / Rebuild(Array(this.foo, Byte), lambda x: [1,2,3,4]))
    obj, extra_info = d.preprocess({"asd": 12})

    assert(extra_info["_size"] == 12)

    size_test(d, obj, size=12)

    d = Struct("asd" / Int32ul,
               "foo" / Rebuild(Int32ul, lambda ctx: len(ctx.test)),
               "test" / Rebuild(Array(this.foo, Byte), lambda x: [1,2,3,4]))
    obj, extra_info = d.preprocess({"asd": 12})

    assert(extra_info["_size"] == 12)

    size_test(d, obj, size=12)

def test_size_utf16_string():
    d = PascalString(Int32ul, "utf-8")
    size_test(d, "test", size=8)
    d = PascalString(Int32ul, "utf-16-le")
    size_test(d, "test", size=12)

def test_size_impr():
    IMPR = Struct(
        "tranIndex" / Int32ul,
        "objectIndex" / Int32ul,
        "count" / Rebuild(Int32ul, lambda ctx: len(ctx.imprs)),
        # sizes of following IMPR
        "imprsizes" / Rebuild(Array(this.count, Int32ul), lambda ctx: [4] if ctx.objectIndex == 0xFFFFFFFF and ctx.count == 1 else [12 + sum(x.imprsizes) for x in ctx.imprs]),
        "imprs" / Array(this.count, LazyBound(lambda: IMPR))
    )

    data = b"\x00\x00\x00\x00\xFF\xFF\xFF\xFF\x01\x00\x00\x00\x04\x00\x00\x00\x01\x00\x00\x00\xFF\xFF\xFF\xFF\x01\x00\x00\x00\x04\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    d = IMPR.parse(data)
    obj, extra_info = IMPR.preprocess(d)
    assert(extra_info["_size"] == len(data))
    built_data = IMPR.build(obj)

    assert(built_data == data)

