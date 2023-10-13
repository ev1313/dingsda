from typing import Any

from dingsda.core import Subconstruct, Container, Pass
from dingsda.errors import PaddingError, SizeofError
from dingsda.helpers import bytestringtype, evaluate, stream_tell, stream_read, stream_write


def Padding(length, pattern=b"\x00"):
    r"""
    Appends null bytes.

    Parsing consumes specified amount of bytes and discards it. Building writes specified pattern byte multiplied into specified length. Size is same as specified.

    :param length: integer or context lambda, length of the padding
    :param pattern: b-character, padding pattern, default is \\x00

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises PaddingError: length was negative
    :raises PaddingError: pattern was not bytes (b-character)

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Padding(4) or Padded(4, Pass)
        >>> d.build(None)
        b'\x00\x00\x00\x00'
        >>> d.parse(b"****")
        None
        >>> d.sizeof()
        4
    """
    macro = Padded(length, Pass, pattern=pattern)
    return macro


class Padded(Subconstruct):
    r"""
    Appends additional null bytes to achieve a length.

    Parsing first parses the subcon, then uses stream.tell() to measure how many bytes were read and consumes additional bytes accordingly. Building first builds the subcon, then uses stream.tell() to measure how many bytes were written and produces additional bytes accordingly. Size is same as `length`, but negative amount results in error. Note that subcon can actually be variable size, it is the eventual amount of bytes that is read or written during parsing or building that determines actual padding.

    :param length: integer or context lambda, length of the padding
    :param subcon: Construct instance
    :param pattern: optional, b-character, padding pattern, default is \\x00

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises PaddingError: length is negative
    :raises PaddingError: subcon read or written more than the length (would cause negative pad)
    :raises PaddingError: pattern is not bytes of length 1

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Padded(4, Byte)
        >>> d.build(255)
        b'\xff\x00\x00\x00'
        >>> d.parse(_)
        255
        >>> d.sizeof()
        4

        >>> d = Padded(4, VarInt)
        >>> d.build(1)
        b'\x01\x00\x00\x00'
        >>> d.build(70000)
        b'\xf0\xa2\x04\x00'
    """

    def __init__(self, length, subcon, pattern=b"\x00"):
        if not isinstance(pattern, bytestringtype) or len(pattern) != 1:
            raise PaddingError("pattern expected to be bytes of length 1")
        super().__init__(subcon)
        self.length = length
        self.pattern = pattern

    def _parse(self, stream, context, path):
        length = evaluate(self.length, context)
        if length < 0:
            raise PaddingError("length cannot be negative", path=path)
        position1 = stream_tell(stream, path)
        obj = self.subcon._parsereport(stream, context, path)
        position2 = stream_tell(stream, path)
        pad = length - (position2 - position1)
        if pad < 0:
            raise PaddingError("subcon parsed %d bytes but was allowed only %d" % (position2 - position1, length), path=path)
        stream_read(stream, pad, path)
        return obj

    def _build(self, obj, stream, context, path):
        length = evaluate(self.length, context)
        if length < 0:
            raise PaddingError("length cannot be negative", path=path)
        position1 = stream_tell(stream, path)
        buildret = self.subcon._build(obj, stream, context, path)
        position2 = stream_tell(stream, path)
        pad = length - (position2 - position1)
        if pad < 0:
            raise PaddingError("subcon build %d bytes but was allowed only %d" % (position2 - position1, length), path=path)
        stream_write(stream, self.pattern * pad, pad, path)
        return buildret

    def _static_sizeof(self, context, path):
        try:
            length = evaluate(self.length, context)
            if length < 0:
                raise PaddingError("length cannot be negative", path=path)
            return length
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _sizeof(self, obj: Any, context: Container, path: str):
        try:
            length = evaluate(self.length, context)
            if length < 0:
                raise PaddingError("length cannot be negative", path=path)
            return length
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _toET(self, parent, name, context, path):
        return self.subcon._toET(context=context, name=name, parent=parent, path=f"{path} -> {name}")


    def _fromET(self, parent, name, context, path, is_root=False):
        return self.subcon._fromET(context=context, parent=parent, name=name, path=f"{path} -> {name}", is_root=is_root)


class Aligned(Subconstruct):
    r"""
    Appends additional null bytes to achieve a length that is shortest multiple of a modulus.

    Note that subcon can actually be variable size, it is the eventual amount of bytes that is read or written during parsing or building that determines actual padding.

    Parsing first parses subcon, then consumes an amount of bytes to sum up to specified length, and discards it. Building first builds subcon, then writes specified pattern byte to sum up to specified length. Size is subcon size plus modulo remainder, unless SizeofError was raised.

    :param modulus: integer or context lambda, modulus to final length
    :param subcon: Construct instance
    :param pattern: optional, b-character, padding pattern, default is \\x00

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises PaddingError: modulus was less than 2
    :raises PaddingError: pattern was not bytes (b-character)

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Aligned(4, Int16ub)
        >>> d.parse(b'\x00\x01\x00\x00')
        1
        >>> d.sizeof()
        4
    """

    def __init__(self, modulus, subcon, pattern=b"\x00"):
        if not isinstance(pattern, bytestringtype) or len(pattern) != 1:
            raise PaddingError("pattern expected to be bytes character")
        super().__init__(subcon)
        self.modulus = modulus
        self.pattern = pattern

    def _parse(self, stream, context, path):
        modulus = evaluate(self.modulus, context)
        if modulus < 2:
            raise PaddingError("expected modulo 2 or greater", path=path)
        position1 = stream_tell(stream, path)
        obj = self.subcon._parsereport(stream, context, path)
        position2 = stream_tell(stream, path)
        pad = -(position2 - position1) % modulus
        stream_read(stream, pad, path)
        return obj

    def _build(self, obj, stream, context, path):
        modulus = evaluate(self.modulus, context)
        if modulus < 2:
            raise PaddingError("expected modulo 2 or greater", path=path)
        position1 = stream_tell(stream, path)
        buildret = self.subcon._build(obj, stream, context, path)
        position2 = stream_tell(stream, path)
        pad = -(position2 - position1) % modulus
        stream_write(stream, self.pattern * pad, pad, path)
        return buildret

    def _static_sizeof(self, context, path):
        try:
            modulus = evaluate(self.modulus, context)
            if modulus < 2:
                raise PaddingError("expected modulo 2 or greater", path=path)
            subconlen = self.subcon._static_sizeof(context, path)
            return subconlen + (-subconlen % modulus)
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        try:
            modulus = evaluate(self.modulus, context)
            if modulus < 2:
                raise PaddingError("expected modulo 2 or greater", path=path)
            subconlen = self.subcon._sizeof(obj, context, path)
            return subconlen + (-subconlen % modulus)
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _toET(self, parent, name, context, path):
        return self.subcon._toET(context=context, name=name, parent=parent, path=f"{path} -> {name}")

    def _fromET(self, parent, name, context, path, is_root=False):
        return self.subcon._fromET(context=context, parent=parent, name=name, path=f"{path} -> {name}", is_root=is_root)

