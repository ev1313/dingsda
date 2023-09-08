from dingsda import Struct, Lazy, Computed, this, Byte, Prefixed, Int8ub, Bytes, Int16ub, LazyStruct, BytesInteger, \
    PrefixedArray, Container, SizeofError, LazyArray, ListContainer, VarInt, LazyBound, If, GreedyBytes
from tests.declarativeunittest import raises, common


def test_lazy():
    d = Struct(
        'dup' / Lazy(Computed(this.exists)),
        'exists' / Computed(1),
    )
    obj = d.parse(b'')
    assert(obj.dup == 1)

    d = Lazy(Byte)
    x = d.parse(b'\x00')
    assert x() == 0
    assert d.build(0) == b'\x00'
    assert d.build(x) == b'\x00'
    assert d.static_sizeof() == 1


def test_lazy_issue_938():
    d = Lazy(Prefixed(Byte, Byte))
    func = d.parse(b'\x01\x02')
    assert func() == 2


def test_lazy_seek():
    d = Struct(
        "a" / Int8ub,
        "b" / Lazy(Bytes(2)),
        "c" / Int16ub,
        "d" / Lazy(Bytes(4))
    )
    obj = d.parse(b"\x01\x02\x03\x04\x05\x06\x07\x08\x09")

    assert obj.a == 0x01
    assert obj.b == b'\x02\x03'
    assert obj.c == 0x0405
    assert obj.d == b'\x06\x07\x08\x09'


def test_lazystruct():
    d = LazyStruct(
        "num1" / Int8ub,
        "num2" / BytesInteger(1),
        "prefixed1" / Prefixed(Byte, Byte),
        "prefixed2" / Prefixed(Byte, Byte, includelength=True),
        "prefixedarray" / PrefixedArray(Byte, Byte),
    )
    obj = d.parse(b"\x00\x00\x01\x00\x02\x00\x01\x00")
    assert obj.num1 == obj["num1"] == obj[0] == 0
    assert obj.num2 == obj["num2"] == obj[1] == 0
    assert obj.prefixed1 == obj["prefixed1"] == obj[2] == 0
    assert obj.prefixed2 == obj["prefixed2"] == obj[3] == 0
    assert obj.prefixedarray == obj["prefixedarray"] == obj[4] == [0]
    assert len(obj) == 5
    assert list(obj.keys()) == ['num1', 'num2', 'prefixed1', 'prefixed2', 'prefixedarray']
    assert list(obj.values()) == [0, 0, 0, 0, [0]]
    assert list(obj.items()) == [('num1', 0), ('num2', 0), ('prefixed1', 0), ('prefixed2', 0), ('prefixedarray', [0])]
    assert repr(obj) == "<LazyContainer: 5 items cached, 5 subcons>"
    assert str(obj) == "<LazyContainer: 5 items cached, 5 subcons>"
    assert d.build(obj) == b"\x00\x00\x01\x00\x02\x00\x01\x00"
    assert d.build(Container(obj)) == b"\x00\x00\x01\x00\x02\x00\x01\x00"
    assert raises(d.static_sizeof) == SizeofError


def test_lazyarray():
    d = LazyArray(5, Int8ub)
    obj = d.parse(b"\x00\x01\x02\x03\x04")
    assert repr(obj) == "<LazyListContainer: 0 of 5 items cached>"
    for i in range(5):
        assert obj[i] == i
    assert obj[:] == [0,1,2,3,4]
    assert obj == [0,1,2,3,4]
    assert list(obj) == [0,1,2,3,4]
    assert len(obj) == 5
    assert repr(obj) == "<LazyListContainer: 5 of 5 items cached>"
    assert str(obj) == "<LazyListContainer: 5 of 5 items cached>"
    assert d.build([0,1,2,3,4]) == b"\x00\x01\x02\x03\x04"
    assert d.build(ListContainer([0,1,2,3,4])) == b"\x00\x01\x02\x03\x04"
    assert d.build(obj) == b"\x00\x01\x02\x03\x04"
    assert d.build(obj[:]) == b"\x00\x01\x02\x03\x04"
    assert d.static_sizeof() == 5

    d = LazyArray(5, VarInt)
    obj = d.parse(b"\x00\x01\x02\x03\x04")
    assert repr(obj) == "<LazyListContainer: 5 of 5 items cached>"
    for i in range(5):
        assert obj[i] == i
    assert obj[:] == [0,1,2,3,4]
    assert obj == [0,1,2,3,4]
    assert list(obj) == [0,1,2,3,4]
    assert len(obj) == 5
    assert repr(obj) == "<LazyListContainer: 5 of 5 items cached>"
    assert str(obj) == "<LazyListContainer: 5 of 5 items cached>"
    assert d.build([0,1,2,3,4]) == b"\x00\x01\x02\x03\x04"
    assert d.build(ListContainer([0,1,2,3,4])) == b"\x00\x01\x02\x03\x04"
    assert d.build(obj) == b"\x00\x01\x02\x03\x04"
    assert d.build(obj[:]) == b"\x00\x01\x02\x03\x04"
    assert raises(d.static_sizeof) == SizeofError


def test_lazybound():
    d = LazyBound(lambda: Byte)
    common(d, b"\x01", 1)

    d = Struct(
        "value" / Byte,
        "next" / If(this.value > 0, LazyBound(lambda: d)),
    )
    common(d, b"\x05\x09\x00", Container(value=5, next=Container(value=9, next=Container(value=0, next=None))))

    d = Struct(
        "value" / Byte,
        "next" / GreedyBytes,
    )
    data = b"\x05\x09\x00"
    while data:
        x = d.parse(data)
        data = x.next
        print(x)
