import itertools
import math
import os
import random

from dingsda import Byte, Short, Int, Long, Int8ub, Int16ub, Int32ub, Int64ub, Int8sb, Int16sb, Int32sb, Int64sb, \
    Int8ul, Int16ul, Int32ul, Int64ul, Int8sl, Int16sl, Int32sl, Int64sl, Int24ub, Int24ul, Int24sb, Int24sl, Half, \
    Single, Double, FormatField, StreamError, FormatFieldError, BytesInteger, IntegerError, this, SizeofError, \
    BitsInteger, VarInt, Struct, Bytes, Container, Check, ZigZag
from dingsda.lib import int2byte, integertypes
from tests.declarativeunittest import common, raises, size_test

def test_ints():
    common(Byte, b"\xff", 255)
    common(Short, b"\x00\xff", 255)
    common(Int, b"\x00\x00\x00\xff", 255)
    common(Long, b"\x00\x00\x00\x00\x00\x00\x00\xff", 255)

    common(Int8ub, b"\x01", 0x01)
    common(Int16ub, b"\x01\x02", 0x0102)
    common(Int32ub, b"\x01\x02\x03\x04", 0x01020304)
    common(Int64ub, b"\x01\x02\x03\x04\x05\x06\x07\x08", 0x0102030405060708)

    common(Int8sb, b"\x01", 0x01)
    common(Int16sb, b"\x01\x02", 0x0102)
    common(Int32sb, b"\x01\x02\x03\x04", 0x01020304)
    common(Int64sb, b"\x01\x02\x03\x04\x05\x06\x07\x08", 0x0102030405060708)
    common(Int8sb, b"\xff", -1)
    common(Int16sb, b"\xff\xff", -1)
    common(Int32sb, b"\xff\xff\xff\xff", -1)
    common(Int64sb, b"\xff\xff\xff\xff\xff\xff\xff\xff", -1)

    common(Int8ul, b"\x01", 0x01)
    common(Int16ul, b"\x01\x02", 0x0201)
    common(Int32ul, b"\x01\x02\x03\x04", 0x04030201)
    common(Int64ul, b"\x01\x02\x03\x04\x05\x06\x07\x08", 0x0807060504030201)

    common(Int8sl, b"\x01", 0x01)
    common(Int16sl, b"\x01\x02", 0x0201)
    common(Int32sl, b"\x01\x02\x03\x04", 0x04030201)
    common(Int64sl, b"\x01\x02\x03\x04\x05\x06\x07\x08", 0x0807060504030201)
    common(Int8sl, b"\xff", -1)
    common(Int16sl, b"\xff\xff", -1)
    common(Int32sl, b"\xff\xff\xff\xff", -1)
    common(Int64sl, b"\xff\xff\xff\xff\xff\xff\xff\xff", -1)

    size_test(Int8ub, {}, 1, 1)
    size_test(Int8ul, {}, 1, 1)
    size_test(Int8sb, {}, 1, 1)
    size_test(Int8sl, {}, 1, 1)
    size_test(Int16ub, {}, 2, 2)
    size_test(Int16ul, {}, 2, 2)
    size_test(Int16sb, {}, 2, 2)
    size_test(Int16sl, {}, 2, 2)
    size_test(Int32ub, {}, 4, 4)
    size_test(Int32ul, {}, 4, 4)
    size_test(Int32sb, {}, 4, 4)
    size_test(Int32sl, {}, 4, 4)
    size_test(Int64ub, {}, 8, 8)
    size_test(Int64ul, {}, 8, 8)
    size_test(Int64sb, {}, 8, 8)
    size_test(Int64sl, {}, 8, 8)


def test_ints24():
    common(Int24ub, b"\x01\x02\x03", 0x010203)
    common(Int24ul, b"\x01\x02\x03", 0x030201)
    common(Int24sb, b"\xff\xff\xff", -1)
    common(Int24sl, b"\xff\xff\xff", -1)

    size_test(Int24ub, {}, 3, 3)
    size_test(Int24ul, {}, 3, 3)
    size_test(Int24sb, {}, 3, 3)
    size_test(Int24sl, {}, 3, 3)


def test_floats():
    common(Half, b"\x00\x00", 0., 2)
    common(Half, b"\x35\x55", 0.333251953125, 2)
    common(Single, b"\x00\x00\x00\x00", 0., 4)
    common(Single, b"?\x99\x99\x9a", 1.2000000476837158, 4)
    common(Double, b"\x00\x00\x00\x00\x00\x00\x00\x00", 0., 8)
    common(Double, b"?\xf3333333", 1.2, 8)


def test_formatfield():
    d = FormatField("<","L")
    common(d, b"\x01\x02\x03\x04", 0x04030201, 4)
    assert raises(d.parse, b"") == StreamError
    assert raises(d.parse, b"\x01\x02") == StreamError
    assert raises(d.build, 2**100) == FormatFieldError
    assert raises(d.build, 1e9999) == FormatFieldError
    assert raises(d.build, "string not int") == FormatFieldError


def test_formatfield_ints_randomized():
    for endianess,dtype in itertools.product("<>=","bhlqBHLQ"):
        d = FormatField(endianess, dtype)
        for i in range(100):
            obj = random.randrange(0, 256**d.static_sizeof()//2)
            assert d.parse(d.build(obj)) == obj
            data = os.urandom(d.static_sizeof())
            assert d.build(d.parse(data)) == data


def test_formatfield_floats_randomized():
    # there is a roundoff error because Python float is a C double
    # http://stackoverflow.com/questions/39619636/struct-unpackstruct-packfloat-has-roundoff-error
    # and analog although that was misplaced
    # http://stackoverflow.com/questions/39676482/struct-packstruct-unpackfloat-is-inconsistent-on-py3
    for endianess,dtype in itertools.product("<>=","fd"):
        d = FormatField(endianess, dtype)
        for i in range(100):
            x = random.random()*12345
            if dtype == "d":
                assert d.parse(d.build(x)) == x
            else:
                assert abs(d.parse(d.build(x)) - x) < 1e-3
        for i in range(100):
            b = os.urandom(d.static_sizeof())
            if not math.isnan(d.parse(b)):
                assert d.build(d.parse(b)) == b


def test_formatfield_bool_issue_901():
    d = FormatField(">","?")
    assert d.parse(b"\x01") == True
    assert d.parse(b"\xff") == True
    assert d.parse(b"\x00") == False
    assert d.build(True) == b"\x01"
    assert d.build(False) == b"\x00"
    assert d.static_sizeof() == 1


def test_bytesinteger():
    d = BytesInteger(0)
    assert raises(d.parse, b"") == IntegerError
    assert raises(d.build, 0) == IntegerError
    d = BytesInteger(4, signed=True, swapped=False)
    common(d, b"\x01\x02\x03\x04", 0x01020304)
    common(d, b"\xff\xff\xff\xff", -1)
    d = BytesInteger(4, signed=False, swapped=this.swapped)
    common(d, b"\x01\x02\x03\x04", 0x01020304, swapped=False)
    common(d, b"\x04\x03\x02\x01", 0x01020304, swapped=True)
    assert raises(BytesInteger(-1).parse, b"") == IntegerError
    assert raises(BytesInteger(-1).build, 0) == IntegerError
    assert raises(BytesInteger(8).build, None) == IntegerError
    assert raises(BytesInteger(8, signed=False).build, -1) == IntegerError
    assert raises(BytesInteger(8, True).build,  -2**64) == IntegerError
    assert raises(BytesInteger(8, True).build,   2**64) == IntegerError
    assert raises(BytesInteger(8, False).build, -2**64) == IntegerError
    assert raises(BytesInteger(8, False).build,  2**64) == IntegerError
    assert raises(BytesInteger(this.missing).static_sizeof) == SizeofError

    size_test(BytesInteger(4, signed=True, swapped=False), {}, 4, 4)
    size_test(BytesInteger(4, signed=False, swapped=this.swapped), {}, 4, 4)


def test_bitsinteger():
    d = BitsInteger(0)
    assert raises(d.parse, b"") == IntegerError
    assert raises(d.build, 0) == IntegerError
    d = BitsInteger(8)
    common(d, b"\x01\x01\x01\x01\x01\x01\x01\x01", 255)
    d = BitsInteger(8, signed=True)
    common(d, b"\x01\x01\x01\x01\x01\x01\x01\x01", -1, 8)
    d = BitsInteger(16, swapped=True)
    common(d, b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x01\x01\x01\x01\x01\x01\x01", 0xff00)
    d = BitsInteger(16, swapped=this.swapped)
    common(d, b"\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00", 0xff00, swapped=False)
    common(d, b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x01\x01\x01\x01\x01\x01\x01", 0xff00, swapped=True)
    assert raises(BitsInteger(-1).parse, b"") == IntegerError
    assert raises(BitsInteger(-1).build, 0) == IntegerError
    assert raises(BitsInteger(5, swapped=True).parse, bytes(5)) == IntegerError
    assert raises(BitsInteger(5, swapped=True).build, 0) == IntegerError
    assert raises(BitsInteger(8).build, None) == IntegerError
    assert raises(BitsInteger(8, signed=False).build, -1) == IntegerError
    assert raises(BitsInteger(8, True).build,  -2**64) == IntegerError
    assert raises(BitsInteger(8, True).build,   2**64) == IntegerError
    assert raises(BitsInteger(8, False).build, -2**64) == IntegerError
    assert raises(BitsInteger(8, False).build,  2**64) == IntegerError
    assert raises(BitsInteger(this.missing).static_sizeof) == SizeofError

    size_test(BitsInteger(8), {}, 8, 8)
    size_test(BitsInteger(8, swapped=True), {}, 8, 8)
    size_test(BitsInteger(16), {}, 16, 16)
    size_test(BitsInteger(16, swapped=True), {}, 16, 16)


def test_varint():
    d = VarInt
    common(d, b"\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x10", 2**123)
    for n in [0,1,5,100,255,256,65535,65536,2**32,2**100]:
        assert d.parse(d.build(n)) == n
    for n in range(0, 127):
        common(d, int2byte(n), n, SizeofError)
    assert raises(d.parse, b"") == StreamError
    assert raises(d.build, -1) == IntegerError
    assert raises(d.build, None) == IntegerError
    assert raises(d.static_sizeof) == SizeofError


def test_varint_issue_705():
    d = Struct('namelen' / VarInt, 'name' / Bytes(this.namelen))
    d.build(Container(namelen = 400, name = bytes(400)))
    d = Struct('namelen' / VarInt, Check(this.namelen == 400))
    d.build(dict(namelen=400))


def test_zigzag():
    d = ZigZag
    common(d, b"\x00", 0)
    common(d, b"\x05", -3)
    common(d, b"\x06", 3)
    for n in [0,1,5,100,255,256,65535,65536,2**32,2**100]:
        assert d.parse(d.build(n)) == n
    for n in range(0, 63):
        common(d, int2byte(n*2), n)
    assert raises(d.parse, b"") == StreamError
    assert raises(d.build, None) == IntegerError
    assert raises(d.static_sizeof) == SizeofError


def test_zigzag_regression():
    d = ZigZag
    assert isinstance(d.parse(b"\x05"), integertypes)
    assert isinstance(d.parse(b"\x06"), integertypes)
    d = Struct('namelen' / ZigZag, Check(this.namelen == 400))
    d.build(dict(namelen=400))
