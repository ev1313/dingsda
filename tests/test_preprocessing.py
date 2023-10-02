from dingsda import Struct, Switch, Rebuild, Array, RepeatUntil, GreedyRange, Pointer
from dingsda.numbers import Int8ul, Int16ul, Int32ul
from tests.declarativeunittest import *

def test_preprocess_rebuild_chained():
    d = Struct(
        "foo" / Int32ul,
        "asd" / Struct(
            "bar" / Rebuild(Int32ul, lambda ctx: ctx.baz),
            "baz" / Rebuild(Int32ul, lambda ctx: ctx._.foo),
        )
    )
    obj = {"foo": 4}
    # the preprocessing adds the lambdas to the dictionary, so building is possible without the values
    preprocessed_ctx, meta = d.preprocess(obj=obj)
    res = d.build(preprocessed_ctx)
    assert(res == b'\x04\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00')
    assert(meta.size == len(res))


def test_preprocess_int():
    d = Int32ul
    obj = 4
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    assert(preprocessed_ctx == obj)
    assert(meta_info.offset == 0)
    assert(meta_info.size == 4)
    assert(meta_info.end_offset == 4)


def test_preprocess_struct():
    d = Struct(
        "foo" / Int32ul,
        "anon" / Struct(
            "bar" / Rebuild(Int32ul, lambda ctx: ctx.baz),
            "baz" / Rebuild(Int32ul, lambda ctx: ctx._.foo),
            )
    )
    obj = {"foo": 4}
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    assert(meta_info.size == 12)
    assert(meta_info.offset == 0)
    assert(preprocessed_ctx.get_meta("anon").offset == 4)
    assert(preprocessed_ctx.get_meta("anon").size == 8)
    assert(preprocessed_ctx.get_meta("anon").end_offset == 12)
    assert(preprocessed_ctx["anon"].get_meta("bar").size == 4)
    assert(preprocessed_ctx["anon"].get_meta("baz").size == 4)

    res = d.build(preprocessed_ctx)
    assert(res == b'\x04\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00')
    assert(meta_info.offset == 0)
    assert(meta_info.size == len(res))
    assert(meta_info.end_offset == len(res))


def test_preprocess_array():
    d = Array(3, Int32ul)
    obj = [4,4,4]
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    assert(meta_info.offset == 0)
    assert(preprocessed_ctx.get_meta(0).offset == 0)
    assert(preprocessed_ctx.get_meta(1).offset == 4)
    assert(preprocessed_ctx.get_meta(2).offset == 8)
    assert(preprocessed_ctx.get_meta(0).size == 4)
    assert(preprocessed_ctx.get_meta(1).size == 4)
    assert(preprocessed_ctx.get_meta(2).size == 4)
    assert(preprocessed_ctx.get_meta(0).end_offset == 4)
    assert(preprocessed_ctx.get_meta(1).end_offset == 8)
    assert(preprocessed_ctx.get_meta(2).end_offset == 12)
    assert(meta_info.size == 12)
    assert(meta_info.end_offset == 12)
    res = d.build(preprocessed_ctx)
    assert(res == b'\x04\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00')


def test_preprocess_repeatuntil():
    d = Struct(
        "foo" / Int32ul,
        "bar" / RepeatUntil(lambda obj, lst, ctx: obj == 4, Int32ul),
    )
    obj = {"foo": 1, "bar": [2,3,4]}
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    assert(meta_info.offset == 0)
    assert(preprocessed_ctx.get_meta("foo").offset == 0)
    assert(preprocessed_ctx.get_meta("foo").size == 4)
    assert(preprocessed_ctx.get_meta("foo").end_offset == 4)
    assert(preprocessed_ctx["bar"].get_meta(0).offset == 4)
    assert(preprocessed_ctx["bar"].get_meta(1).offset == 8)
    assert(preprocessed_ctx["bar"].get_meta(2).offset == 12)
    assert(preprocessed_ctx["bar"].get_meta(0).size == 4)
    assert(preprocessed_ctx["bar"].get_meta(1).size == 4)
    assert(preprocessed_ctx["bar"].get_meta(2).size == 4)
    assert(preprocessed_ctx["bar"].get_meta(0).end_offset == 8)
    assert(preprocessed_ctx["bar"].get_meta(1).end_offset == 12)
    assert(preprocessed_ctx["bar"].get_meta(2).end_offset == 16)
    assert(meta_info.size == 16)
    assert(meta_info.end_offset == 16)
    res = d.build(preprocessed_ctx)
    assert(res == b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00')


def test_preprocess_greedyrange():
    d = GreedyRange(Int32ul)
    obj = [1,2,3,4]
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    assert(meta_info.offset == 0)
    assert(preprocessed_ctx.get_meta(0).offset == 0)
    assert(preprocessed_ctx.get_meta(1).offset == 4)
    assert(preprocessed_ctx.get_meta(2).offset == 8)
    assert(preprocessed_ctx.get_meta(3).offset == 12)
    assert(preprocessed_ctx.get_meta(0).size == 4)
    assert(preprocessed_ctx.get_meta(1).size == 4)
    assert(preprocessed_ctx.get_meta(2).size == 4)
    assert(preprocessed_ctx.get_meta(3).size == 4)
    assert(preprocessed_ctx.get_meta(0).end_offset == 4)
    assert(preprocessed_ctx.get_meta(1).end_offset == 8)
    assert(preprocessed_ctx.get_meta(2).end_offset == 12)
    assert(preprocessed_ctx.get_meta(3).end_offset == 16)
    assert(meta_info.size == 16)
    assert(meta_info.end_offset == 16)
    res = d.build(preprocessed_ctx)
    assert(res == b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00')


def test_preprocess_rebuild():
    d = Struct(
        "foo" / Int32ul,
        "bar" / Rebuild(Int32ul, lambda ctx: ctx.baz),
        "baz" / Rebuild(Int32ul, lambda ctx: ctx.foo),
        )
    obj = {"foo": 4}
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    assert(meta_info.offset == 0)
    assert(meta_info.size == 12)
    assert(meta_info.end_offset == 12)
    res = d.build(preprocessed_ctx)
    assert(res == b'\x04\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00')


def test_preprocess_pointer():
    d = Struct(
        "foo" / Array(4, Int32ul),
        "bar" / Pointer(2, Int32ul),
        "baz" / Array(4, Int32ul),
        )
    obj = {"foo": [1,2,3,4], "bar": 2, "baz": [5,6,7,8]}
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    #assert(preprocessed_ctx.get_meta("bar_meta")._ptr_offset == 0)
    assert(preprocessed_ctx.get_meta("bar").ptr_size == 4)
    #assert(preprocessed_ctx.get_meta("bar_meta")._ptr_endoffset == 4)
    res = d.build(preprocessed_ctx)

def test_preprocess_switch():
    s = "test" / Struct(
        "type" / Rebuild(Int8ul, lambda ctx: ctx._switch_id_data),
        "data" / Switch(this.type, {
            1: "b32bit" / Struct("value" / Int32ul),
            2: "b16bit" / Struct("value" / Int16ul),
            3: "test" / Struct("a" / Int32ul, "b" / Int32ul),
        }),
        )
    obj = {"_switch_id_data": 1, "data": {"value": 256}}
    preprocessed_ctx, meta_info = s.preprocess(obj=obj)
    assert(meta_info.offset == 0)
    assert(meta_info.size == 5)
    assert(meta_info.end_offset == 5)


def test_preprocess_ifthenelse():
    d = Struct(
        "foo" / Int32ul,
        "asd" / If(lambda ctx: ctx.foo == 4, Struct("bar" / Int32ul)),
        "test" / Int32ul,
    )
    obj = {"foo": 4, "asd": {"bar": 4}, "test": 4}
    # the preprocessing adds the lambdas to the dictionary, so building is possible without the values
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    res = d.build(preprocessed_ctx)
    assert(res == b'\x04\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00')
    assert(meta_info.size == len(res))

def test_preprocess_ifthenelse_nested():
    # sizeof has two different paths for static and non static values
    d = Struct(
        "foo" / Int32ul,
        "asd" / If(lambda ctx: ctx.foo == 4, Struct("bar" / Int32ul, "test" / If(lambda ctx: ctx.bar == 4, Struct("baz" / Int32ul)))),
        )
    obj = {"foo": 4, "asd": {"bar": 4, "test": {"baz": 4}}}
    # the preprocessing adds the lambdas to the dictionary, so building is possible without the values
    preprocessed_ctx, meta_info = d.preprocess(obj=obj)
    res = d.build(preprocessed_ctx)
    assert(res == b'\x04\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00')
    assert(meta_info.size == len(res))
