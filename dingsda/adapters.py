from typing import Any, Optional, Tuple
from dingsda.errors import MappingError
from dingsda.lib import HexDumpDisplayedBytes, bytestringtype, HexDumpDisplayedDict, HexDisplayedInteger, integertypes, \
    HexDisplayedBytes, HexDisplayedDict
from dingsda.lib.containers import Container, MetaInformation
from dingsda.core import Subconstruct


class Adapter(Subconstruct):
    r"""
    Abstract adapter class.

    Needs to implement `_decode()` for parsing and `_encode()` for building.

    :param subcon: Construct instance
    """

    def _parse(self, stream, context, path):
        obj = self.subcon._parsereport(stream, context, path)
        return self._decode(obj, context, path)

    def _build(self, obj, stream, context, path):
        obj2 = self._encode(obj, context, path)
        self.subcon._build(obj2, stream, context, path)

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Optional[MetaInformation]]:
        obj2 = self._encode(obj, context, path)
        obj2, meta_data = self.subcon._preprocess(obj2, context, path)
        return self._decode(obj2, context, path), meta_data

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Optional[MetaInformation]]:
        obj2 = self._encode(obj, context, path)
        obj2, meta_data = self.subcon._preprocess_size(obj2, context, path)
        return self._decode(obj2, context, path), meta_data

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        obj2 = self._encode(obj, context, path)
        return self.subcon._sizeof(obj2, context, path)

    def _decode(self, obj, context, path):
        raise NotImplementedError

    def _encode(self, obj, context, path):
        raise NotImplementedError


class SymmetricAdapter(Adapter):
    r"""
    Abstract adapter class.

    Needs to implement `_decode()` only, for both parsing and building.

    :param subcon: Construct instance
    """
    def _encode(self, obj, context, path):
        return self._decode(obj, context, path)


class Mapping(Adapter):
    r"""
    Adapter that maps objects to other objects. Translates objects after parsing and before building. Can for example, be used to translate between enum34 objects and strings, but Enum class supports enum34 already and is recommended.

    :param subcon: Construct instance
    :param mapping: dict, for encoding (building) mapping, the reversed is used for parsing mapping

    :raises MappingError: parsing or building but no mapping found

    Example::

        >>> x = object
        >>> d = Mapping(Byte, {x:0})
        >>> d.parse(b"\x00")
        x
        >>> d.build(x)
        b'\x00'
    """

    def __init__(self, subcon, mapping):
        super().__init__(subcon)
        self.decmapping = {v:k for k,v in mapping.items()}
        self.encmapping = mapping

    def _decode(self, obj, context, path):
        try:
            return self.decmapping[obj] # KeyError
        except (KeyError, TypeError):
            raise MappingError("parsing failed, no decoding mapping for %r" % (obj,), path=path)

    def _encode(self, obj, context, path):
        try:
            return self.encmapping[obj] # KeyError
        except (KeyError, TypeError):
            raise MappingError("building failed, no encoding mapping for %r" % (obj,), path=path)


class Hex(Adapter):
    r"""
    Adapter for displaying hexadecimal/hexlified representation of integers/bytes/RawCopy dictionaries.

    Parsing results in int-alike bytes-alike or dict-alike object, whose only difference from original is pretty-printing. If you look at the result, you will be presented with its `repr` which remains as-is. If you print it, then you will see its `str` whic is a hexlified representation. Building and sizeof defer to subcon.

    To obtain a hexlified string (like before Hex HexDump changed semantics) use binascii.(un)hexlify on parsed results.

    Example::

        >>> d = Hex(Int32ub)
        >>> obj = d.parse(b"\x00\x00\x01\x02")
        >>> obj
        258
        >>> print(obj)
        0x00000102

        >>> d = Hex(GreedyBytes)
        >>> obj = d.parse(b"\x00\x00\x01\x02")
        >>> obj
        b'\x00\x00\x01\x02'
        >>> print(obj)
        unhexlify('00000102')

        >>> d = Hex(RawCopy(Int32ub))
        >>> obj = d.parse(b"\x00\x00\x01\x02")
        >>> obj
        {'data': b'\x00\x00\x01\x02',
         'length': 4,
         'offset1': 0,
         'offset2': 4,
         'value': 258}
        >>> print(obj)
        unhexlify('00000102')
    """
    def _decode(self, obj, context, path):
        if isinstance(obj, integertypes):
            return HexDisplayedInteger.new(obj, "0%sX" % (2 * self.subcon._static_sizeof(context, path)))
        if isinstance(obj, bytestringtype):
            return HexDisplayedBytes(obj)
        if isinstance(obj, dict):
            return HexDisplayedDict(obj)
        return obj

    def _encode(self, obj, context, path):
        return obj


class HexDump(Adapter):
    r"""
    Adapter for displaying hexlified representation of bytes/RawCopy dictionaries.

    Parsing results in bytes-alike or dict-alike object, whose only difference from original is pretty-printing. If you look at the result, you will be presented with its `repr` which remains as-is. If you print it, then you will see its `str` whic is a hexlified representation. Building and sizeof defer to subcon.

    To obtain a hexlified string (like before Hex HexDump changed semantics) use dingsda.lib.hexdump on parsed results.

    Example::

        >>> d = HexDump(GreedyBytes)
        >>> obj = d.parse(b"\x00\x00\x01\x02")
        >>> obj
        b'\x00\x00\x01\x02'
        >>> print(obj)
        hexundump('''
        0000   00 00 01 02                                       ....
        ''')

        >>> d = HexDump(RawCopy(Int32ub))
        >>> obj = d.parse(b"\x00\x00\x01\x02")
        >>> obj
        {'data': b'\x00\x00\x01\x02',
         'length': 4,
         'offset1': 0,
         'offset2': 4,
         'value': 258}
        >>> print(obj)
        hexundump('''
        0000   00 00 01 02                                       ....
        ''')
    """
    def _decode(self, obj, context, path):
        if isinstance(obj, bytestringtype):
            return HexDumpDisplayedBytes(obj)
        if isinstance(obj, dict):
            return HexDumpDisplayedDict(obj)
        return obj

    def _encode(self, obj, context, path):
        return obj


class ExprAdapter(Adapter):
    r"""
    Generic adapter that takes `decoder` and `encoder` lambdas as parameters. You can use ExprAdapter instead of writing a full-blown class deriving from Adapter when only a simple lambda is needed.

    :param subcon: Construct instance, subcon to adapt
    :param decoder: lambda that takes (obj, context, path) and returns an decoded version of obj
    :param encoder: lambda that takes (obj, context, path) and returns an encoded version of obj

    Example::

        >>> d = ExprAdapter(Byte, obj_+1, obj_-1)
        >>> d.parse(b'\x04')
        5
        >>> d.build(5)
        b'\x04'
    """
    def __init__(self, subcon, decoder, encoder):
        super().__init__(subcon)
        self._decode = lambda obj,ctx,path: decoder(obj,ctx)
        self._encode = lambda obj,ctx,path: encoder(obj,ctx)


class ExprSymmetricAdapter(ExprAdapter):
    """
    Macro around :class:`~dingsda.core.ExprAdapter`.

    :param subcon: Construct instance, subcon to adapt
    :param encoder: lambda that takes (obj, context, path) and returns both encoded version and decoded version of obj

    Example::

        >>> d = ExprSymmetricAdapter(Byte, obj_ & 0b00001111)
        >>> d.parse(b"\xff")
        15
        >>> d.build(255)
        b'\x0f'
    """
    def __init__(self, subcon, encoder):
        super().__init__(subcon, encoder, encoder)
