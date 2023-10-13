import io
from typing import Any, Optional

from dingsda.core import Construct, Subconstruct
from dingsda.errors import SizeofError, StreamError
from dingsda.helpers import stream_read, stream_write, stream_read_entire, evaluate, singleton
from dingsda.lib import integer2bytes, bits2bytes, bytes2bits, RestreamedBytesIO, swapbytes, swapbitsinbytes, \
    integertypes
from dingsda.lib.containers import Container
from dingsda.struct import Struct


class Bytes(Construct):
    r"""
    Field consisting of a specified number of bytes.

    Parses into a bytes (of given length). Builds into the stream directly (but checks that given object matches specified length). Can also build from an integer for convenience (although BytesInteger should be used instead). Size is the specified length.

    Can also build from a bytearray.

    :param length: integer or context lambda

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises StringError: building from non-bytes value, perhaps unicode

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Bytes(4)
        >>> d.parse(b'beef')
        b'beef'
        >>> d.build(b'beef')
        b'beef'
        >>> d.build(0)
        b'\x00\x00\x00\x00'
        >>> d.sizeof()
        4

        >>> d = Struct(
        ...     "length" / Int8ub,
        ...     "data" / Bytes(this.length),
        ... )
        >>> d.parse(b"\x04beef")
        Container(length=4, data=b'beef')
        >>> d.sizeof()
        dingsda.core.SizeofError: cannot calculate size, key not found in context
    """

    def __init__(self, length):
        super().__init__()
        self.length = length

    def _parse(self, stream, context, path):
        length = self.length(context) if callable(self.length) else self.length
        return stream_read(stream, length, path)

    def _build(self, obj, stream, context, path):
        length = self.length(context) if callable(self.length) else self.length
        data = integer2bytes(obj, length) if isinstance(obj, int) else obj
        data = bytes(data) if type(data) is bytearray else data
        stream_write(stream, data, length, path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        try:
            return evaluate(self.length, context)
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        # FIXME: this should use not the length field but the actual data
        # FIXME: add preprocess so the length field can be rebuild from the length of the actual data
        try:
            return evaluate(self.length, context)
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _toET(self, parent, name, context, path):
        assert (name is not None)

        f = get_current_field(context, name)
        assert (isinstance(f, bytes))
        data = f.hex()
        if parent is None:
            return data
        else:
            parent.attrib[name] = data
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        assert(parent is not None)
        assert(name is not None)

        if isinstance(parent, str):
            elem = parent
        else:
            elem = parent.attrib[name]

        elem = b"".fromhex(elem)
        insert_or_append_field(context, name, elem)
        return context

    def _is_simple_type(self, context: Optional[Container] = None):
        return True


@singleton
class GreedyBytes(Construct):
    r"""
    Field consisting of unknown number of bytes.

    Parses the stream to the end. Builds into the stream directly (without checks). Size is undefined.

    Can also build from a bytearray.

    :raises StreamError: stream failed when reading until EOF
    :raises StringError: building from non-bytes value, perhaps unicode

    Example::

        >>> GreedyBytes.parse(b"asislight")
        b'asislight'
        >>> GreedyBytes.build(b"asislight")
        b'asislight'
    """

    def _parse(self, stream, context, path):
        return stream_read_entire(stream, path)

    def _build(self, obj, stream, context, path):
        data = bytes(obj) if type(obj) is bytearray else obj
        stream_write(stream, data, len(data), path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return len(obj)

    def _toET(self, parent, name, context, path):
        assert (name is not None)

        f = get_current_field(context, name)
        assert (isinstance(f, bytes))
        data = f.hex()
        if parent is None:
            return data
        else:
            parent.attrib[name] = data
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        assert(parent is not None)
        assert(name is not None)

        if isinstance(parent, str):
            elem = parent
        else:
            elem = parent.attrib[name]

        elem = b"".fromhex(elem)
        insert_or_append_field(context, name, elem)
        return context

    def _is_simple_type(self, context: Optional[Container] = None):
        return True


class Transformed(Subconstruct):
    r"""
    Transforms bytes between the underlying stream and the (fixed-sized) subcon.

    Parsing reads a specified amount (or till EOF), processes data using a bytes-to-bytes decoding function, then parses subcon using those data. Building does build subcon into separate bytes, then processes it using encoding bytes-to-bytes function, then writes those data into main stream. Size is reported as `decodeamount` or `encodeamount` if those are equal, otherwise its SizeofError.

    Used internally to implement :class:`~dingsda.core.Bitwise` :class:`~dingsda.core.Bytewise` :class:`~dingsda.core.ByteSwapped` :class:`~dingsda.core.BitsSwapped` .

    Possible use-cases include encryption, obfuscation, byte-level encoding.

    .. warning:: Remember that subcon must consume (or produce) an amount of bytes that is same as `decodeamount` (or `encodeamount`).

    .. warning:: Do NOT use seeking/telling classes inside Transformed context.

    :param subcon: Construct instance
    :param decodefunc: bytes-to-bytes function, applied before parsing subcon
    :param decodeamount: integer, amount of bytes to read
    :param encodefunc: bytes-to-bytes function, applied after building subcon
    :param encodeamount: integer, amount of bytes to write

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises StreamError: subcon build and encoder transformed more or less than `encodeamount` bytes, if amount is specified
    :raises StringError: building from non-bytes value, perhaps unicode

    Can propagate any exception from the lambdas, possibly non-ConstructError.

    Example::

        >>> d = Transformed(Bytes(16), bytes2bits, 2, bits2bytes, 2)
        >>> d.parse(b"\x00\x00")
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

        >>> d = Transformed(GreedyBytes, bytes2bits, None, bits2bytes, None)
        >>> d.parse(b"\x00\x00")
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    """

    def __init__(self, subcon, decodefunc, decodeamount, encodefunc, encodeamount):
        super().__init__(subcon)
        self.decodefunc = decodefunc
        self.decodeamount = decodeamount
        self.encodefunc = encodefunc
        self.encodeamount = encodeamount

    def _parse(self, stream, context, path):
        if isinstance(self.decodeamount, type(None)):
            data = stream_read_entire(stream, path)
        if isinstance(self.decodeamount, integertypes):
            data = stream_read(stream, self.decodeamount, path)
        data = self.decodefunc(data)
        return self.subcon._parsereport(io.BytesIO(data), context, path)

    def _build(self, obj, stream, context, path):
        stream2 = io.BytesIO()
        buildret = self.subcon._build(obj, stream2, context, path)
        data = stream2.getvalue()
        data = self.encodefunc(data)
        if isinstance(self.encodeamount, integertypes):
            if len(data) != self.encodeamount:
                raise StreamError("encoding transformation produced wrong amount of bytes, %s instead of expected %s" % (len(data), self.encodeamount,), path=path)
        stream_write(stream, data, len(data), path)
        return buildret

    def _static_sizeof(self, context: Container, path: str):
        if self.decodeamount is None or self.encodeamount is None:
            raise SizeofError(path=path)
        if self.decodeamount == self.encodeamount:
            return self.encodeamount
        raise SizeofError(path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return self._static_sizeof(context, path)


class Restreamed(Subconstruct):
    r"""
    Transforms bytes between the underlying stream and the (variable-sized) subcon.

    Used internally to implement :class:`~dingsda.core.Bitwise` :class:`~dingsda.core.Bytewise` :class:`~dingsda.core.ByteSwapped` :class:`~dingsda.core.BitsSwapped` .

    .. warning:: Remember that subcon must consume or produce an amount of bytes that is a multiple of encoding or decoding units. For example, in a Bitwise context you should process a multiple of 8 bits or the stream will fail during parsing/building.

    .. warning:: Do NOT use seeking/telling classes inside Restreamed context.

    :param subcon: Construct instance
    :param decoder: bytes-to-bytes function, used on data chunks when parsing
    :param decoderunit: integer, decoder takes chunks of this size
    :param encoder: bytes-to-bytes function, used on data chunks when building
    :param encoderunit: integer, encoder takes chunks of this size
    :param sizecomputer: function that computes amount of bytes outputed

    Can propagate any exception from the lambda, possibly non-ConstructError.
    Can also raise arbitrary exceptions in RestreamedBytesIO implementation.

    Example::

        Bitwise  <--> Restreamed(subcon, bits2bytes, 8, bytes2bits, 1, lambda n: n//8)
        Bytewise <--> Restreamed(subcon, bytes2bits, 1, bits2bytes, 8, lambda n: n*8)
    """

    def __init__(self, subcon, decoder, decoderunit, encoder, encoderunit, sizecomputer):
        super().__init__(subcon)
        self.decoder = decoder
        self.decoderunit = decoderunit
        self.encoder = encoder
        self.encoderunit = encoderunit
        self.sizecomputer = sizecomputer

    def _parse(self, stream, context, path):
        stream2 = RestreamedBytesIO(stream, self.decoder, self.decoderunit, self.encoder, self.encoderunit)
        obj = self.subcon._parsereport(stream2, context, path)
        stream2.close()
        return obj

    def _build(self, obj, stream, context, path):
        stream2 = RestreamedBytesIO(stream, self.decoder, self.decoderunit, self.encoder, self.encoderunit)
        buildret = self.subcon._build(obj, stream2, context, path)
        stream2.close()
        return obj

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        if self.sizecomputer is None:
            raise SizeofError("Restreamed cannot calculate size without a sizecomputer", path=path)
        else:
            return self.sizecomputer(self.subcon._sizeof(obj, context, path))


def ByteSwapped(subcon):
    r"""
    Swaps the byte order within boundaries of given subcon. Requires a fixed sized subcon.

    :param subcon: Construct instance, subcon on top of byte swapped bytes

    :raises SizeofError: ctor or compiler could not compute subcon size

    See :class:`~dingsda.core.Transformed` and :class:`~dingsda.core.Restreamed` for raisable exceptions.

    Example::

        Int24ul <--> ByteSwapped(Int24ub) <--> BytesInteger(3, swapped=True) <--> ByteSwapped(BytesInteger(3))
    """

    size = subcon.static_sizeof()
    return Transformed(subcon, swapbytes, size, swapbytes, size)


def BitsSwapped(subcon):
    r"""
    Swaps the bit order within each byte within boundaries of given subcon. Does NOT require a fixed sized subcon.

    :param subcon: Construct instance, subcon on top of bit swapped bytes

    :raises SizeofError: compiler could not compute subcon size

    See :class:`~dingsda.core.Transformed` and :class:`~dingsda.core.Restreamed` for raisable exceptions.

    Example::

        >>> d = Bitwise(Bytes(8))
        >>> d.parse(b"\x01")
        '\x00\x00\x00\x00\x00\x00\x00\x01'
        >>>> BitsSwapped(d).parse(b"\x01")
        '\x01\x00\x00\x00\x00\x00\x00\x00'
    """

    try:
        size = subcon.static_sizeof()
        return Transformed(subcon, swapbitsinbytes, size, swapbitsinbytes, size)
    except SizeofError:
        return Restreamed(subcon, swapbitsinbytes, 1, swapbitsinbytes, 1, lambda n: n)


def Bitwise(subcon):
    r"""
    Converts the stream from bytes to bits, and passes the bitstream to underlying subcon. Bitstream is a stream that contains 8 times as many bytes, and each byte is either \\x00 or \\x01 (in documentation those bytes are called bits).

    Parsing building and size are deferred to subcon, although size gets divided by 8 (therefore the subcon's size must be a multiple of 8).

    Note that by default the bit ordering is from MSB to LSB for every byte (ie. bit-level big-endian). If you need it reversed, wrap this subcon with :class:`dingsda.core.BitsSwapped`.

    :param subcon: Construct instance, any field that works with bits (like BitsInteger) or is bit-byte agnostic (like Struct or Flag)

    See :class:`~dingsda.core.Transformed` and :class:`~dingsda.core.Restreamed` for raisable exceptions.

    Example::

        >>> d = Bitwise(Struct(
        ...     'a' / Nibble,
        ...     'b' / Bytewise(Float32b),
        ...     'c' / Padding(4),
        ... ))
        >>> d.parse(bytes(5))
        Container(a=0, b=0.0, c=None)
        >>> d.sizeof()
        5

    Obtaining other byte or bit orderings::

        >>> d = Bitwise(Bytes(16))
        >>> d.parse(b'\x01\x03')
        b'\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x01'
        >>> d = BitsSwapped(Bitwise(Bytes(16)))
        >>> d.parse(b'\x01\x03')
        b'\x01\x00\x00\x00\x00\x00\x00\x00\x01\x01\x00\x00\x00\x00\x00\x00'
    """

    try:
        size = subcon.static_sizeof()
        macro = Transformed(subcon, bytes2bits, size//8, bits2bytes, size//8)
    except SizeofError:
        macro = Restreamed(subcon, bytes2bits, 1, bits2bytes, 8, lambda n: n//8)
    return macro


def Bytewise(subcon):
    r"""
    Converts the bitstream back to normal byte stream. Must be used within :class:`~dingsda.core.Bitwise`.

    Parsing building and size are deferred to subcon, although size gets multiplied by 8.

    :param subcon: Construct instance, any field that works with bytes or is bit-byte agnostic

    See :class:`~dingsda.core.Transformed` and :class:`~dingsda.core.Restreamed` for raisable exceptions.

    Example::

        >>> d = Bitwise(Struct(
        ...     'a' / Nibble,
        ...     'b' / Bytewise(Float32b),
        ...     'c' / Padding(4),
        ... ))
        >>> d.parse(bytes(5))
        Container(a=0, b=0.0, c=None)
        >>> d.sizeof()
        5
    """

    try:
        size = subcon.static_sizeof()
        macro = Transformed(subcon, bits2bytes, size*8, bytes2bits, size*8)
    except SizeofError:
        macro = Restreamed(subcon, bits2bytes, 8, bytes2bits, 1, lambda n: n*8)
    return macro


def BitStruct(*subcons, **subconskw):
    r"""
    Makes a structure inside a Bitwise.

    See :class:`~dingsda.core.Bitwise` and :class:`~dingsda.core.Struct` for semantics and raisable exceptions.

    :param \*subcons: Construct instances, list of members, some can be anonymous
    :param \*\*subconskw: Construct instances, list of members (requires Python 3.6)

    Example::

        BitStruct  <-->  Bitwise(Struct(...))

        >>> d = BitStruct(
        ...     "a" / Flag,
        ...     "b" / Nibble,
        ...     "c" / BitsInteger(10),
        ...     "d" / Padding(1),
        ... )
        >>> d.parse(b"\xbe\xef")
        Container(a=True, b=7, c=887, d=None)
        >>> d.sizeof()
        2
    """
    return Bitwise(Struct(*subcons, **subconskw))


