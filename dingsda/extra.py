import binascii

from dingsda import singleton, stream_read, stream_write, evaluate, bytestringtype, ChecksumError, RebufferedBytesIO
from dingsda.core import Construct, Subconstruct
from dingsda.lib.containers import Container
from typing import Any
import io


@singleton
class Flag(Construct):
    r"""
    One byte (or one bit) field that maps to True or False. Other non-zero bytes are also considered True. Size is defined as 1.

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes

    Example::

        >>> Flag.parse(b"\x01")
        True
        >>> Flag.build(True)
        b'\x01'
    """

    def _parse(self, stream, context, path):
        return stream_read(stream, 1, path) != b"\x00"

    def _build(self, obj, stream, context, path):
        stream_write(stream, b"\x01" if obj else b"\x00", 1, path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 1


class RestreamData(Subconstruct):
    r"""
    Parses a field on external data (but does not build).

    Parsing defers to subcon, but provides it a separate BytesIO stream based on data provided by datafunc
    (a bytes literal or another BytesIO stream or Construct instances that returns bytes or context lambda).
    Building does nothing. Size is 0 because as far as other fields see it, this field does not produce or consume
    any bytes from the stream.

    :param datafunc: bytes or BytesIO or Construct instance (that parses into bytes) or context lambda, provides data for subcon to parse from
    :param subcon: Construct instance

    Can propagate any exception from the lambdas, possibly non-ConstructError.

    Example::

        >>> d = RestreamData(b"\x01", Int8ub)
        >>> d.parse(b"")
        1
        >>> d.build(0)
        b''

        >>> d = RestreamData(NullTerminated(GreedyBytes), Int16ub)
        >>> d.parse(b"\x01\x02\x00")
        0x0102
        >>> d = RestreamData(FixedSized(2, GreedyBytes), Int16ub)
        >>> d.parse(b"\x01\x02\x00")
        0x0102
    """

    def __init__(self, datafunc, subcon):
        super().__init__(subcon)
        self.datafunc = datafunc
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        data = evaluate(self.datafunc, context)
        if isinstance(data, bytestringtype):
            stream2 = io.BytesIO(data)
        if isinstance(data, io.BytesIO):
            stream2 = data
        if isinstance(data, Construct):
            stream2 = io.BytesIO(data._parsereport(stream, context, path))
        return self.subcon._parsereport(stream2, context, path)

    def _build(self, obj, stream, context, path):
        return obj

    def _static_sizeof(self, context, path):
        return 0

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return 0


class Checksum(Construct):
    r"""
    Field that is build or validated by a hash of a given byte range. Usually used with :class:`~dingsda.core.RawCopy` .

    Parsing compares parsed subcon `checksumfield` with a context entry provided by `bytesfunc` and transformed by `hashfunc`. Building fetches the contect entry, transforms it, then writes is using subcon. Size is same as subcon.

    :param checksumfield: a subcon field that reads the checksum, usually Bytes(int)
    :param hashfunc: function that takes bytes and returns whatever checksumfield takes when building, usually from hashlib module
    :param bytesfunc: context lambda that returns bytes (or object) to be hashed, usually like this.rawcopy1.data

    :raises ChecksumError: parsing and actual checksum does not match actual data

    Can propagate any exception from the lambdas, possibly non-ConstructError.

    Example::

        import hashlib
        d = Struct(
            "fields" / RawCopy(Struct(
                Padding(1000),
            )),
            "checksum" / Checksum(Bytes(64),
                lambda data: hashlib.sha512(data).digest(),
                this.fields.data),
        )
        d.build(dict(fields=dict(value={})))

    ::

        import hashlib
        d = Struct(
            "offset" / Tell,
            "checksum" / Padding(64),
            "fields" / RawCopy(Struct(
                Padding(1000),
            )),
            "checksum" / Pointer(this.offset, Checksum(Bytes(64),
                lambda data: hashlib.sha512(data).digest(),
                this.fields.data)),
        )
        d.build(dict(fields=dict(value={})))
    """

    def __init__(self, checksumfield, hashfunc, bytesfunc):
        super().__init__()
        self.checksumfield = checksumfield
        self.hashfunc = hashfunc
        self.bytesfunc = bytesfunc
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        hash1 = self.checksumfield._parsereport(stream, context, path)
        hash2 = self.hashfunc(self.bytesfunc(context))
        if hash1 != hash2:
            raise ChecksumError(
                "wrong checksum, read %r, computed %r" % (
                    hash1 if not isinstance(hash1,bytestringtype) else binascii.hexlify(hash1),
                    hash2 if not isinstance(hash2,bytestringtype) else binascii.hexlify(hash2), ),
                path=path
            )
        return hash1

    def _build(self, obj, stream, context, path):
        hash2 = self.hashfunc(self.bytesfunc(context))
        self.checksumfield._build(hash2, stream, context, path)
        return hash2

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return self.checksumfield._sizeof(obj, context, path)


@singleton
class Numpy(Construct):
    r"""
    Preserves numpy arrays (both shape, dtype and values).

    Parses using `numpy.load() <https://docs.scipy.org/doc/numpy/reference/generated/numpy.load.html#numpy.load>`_ and builds using `numpy.save() <https://docs.scipy.org/doc/numpy/reference/generated/numpy.save.html#numpy.save>`_ functions, using Numpy binary protocol. Size is undefined.

    :raises ImportError: numpy could not be imported during parsing or building
    :raises ValueError: could not read enough bytes, or so

    Can propagate numpy.load() and numpy.save() exceptions.

    Example::

        >>> import numpy
        >>> a = numpy.asarray([1,2,3])
        >>> Numpy.build(a)
        b"\x93NUMPY\x01\x00F\x00{'descr': '<i8', 'fortran_order': False, 'shape': (3,), }            \n\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00"
        >>> Numpy.parse(_)
        array([1, 2, 3])
    """

    def _parse(self, stream, context: Container, path: str):
        import numpy
        return numpy.load(stream)

    def _build(self, obj: Any, stream, context: Container, path: str):
        import numpy
        numpy.save(stream, obj)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        data = self.build(obj, False)
        return len(data)


class Rebuffered(Subconstruct):
    r"""
    Caches bytes from underlying stream, so it becomes seekable and tellable, and also becomes blocking on reading. Useful for processing non-file streams like pipes, sockets, etc.

    .. warning:: Experimental implementation. May not be mature enough.

    :param subcon: Construct instance, subcon which will operate on the buffered stream
    :param tailcutoff: optional, integer, amount of bytes kept in buffer, by default buffers everything

    Can also raise arbitrary exceptions in its implementation.

    Example::

        Rebuffered(..., tailcutoff=1024).parse_stream(nonseekable_stream)
    """

    def __init__(self, subcon, tailcutoff=None):
        super().__init__(subcon)
        self.stream2 = RebufferedBytesIO(None, tailcutoff=tailcutoff)

    def _parse(self, stream, context, path):
        self.stream2.substream = stream
        return self.subcon._parsereport(self.stream2, context, path)

    def _build(self, obj, stream, context, path):
        self.stream2.substream = stream
        return self.subcon._build(obj, self.stream2, context, path)
