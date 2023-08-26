from dingsda.core import Adapter, Prefixed, GreedyBytes, FixedSized, NullStripped, NullTerminated
from dingsda.helpers import *
from dingsda.errors import *
from dingsda.lib import unicodestringtype

#: Explicitly supported encodings (by PaddedString and CString classes).
#:
possiblestringencodings = dict(
    ascii=1,
    utf8=1, utf_8=1, u8=1,
    utf16=2, utf_16=2, u16=2, utf_16_be=2, utf_16_le=2,
    utf32=4, utf_32=4, u32=4, utf_32_be=4, utf_32_le=4,
)


def encodingunit(encoding):
    """Used internally."""
    encoding = encoding.replace("-","_").lower()
    if encoding not in possiblestringencodings:
        raise StringError("encoding %r not found among %r" % (encoding, possiblestringencodings,))
    return bytes(possiblestringencodings[encoding])


def PaddedString(length, encoding):
    r"""
    Configurable, fixed-length or variable-length string field.

    When parsing, the byte string is stripped of null bytes (per encoding unit), then decoded. Length is an integer or context lambda. When building, the string is encoded and then padded to specified length. If encoded string is larger than the specified length, it fails with PaddingError. Size is same as length parameter.

    .. warning:: PaddedString and CString only support encodings explicitly listed in :class:`~dingsda.core.possiblestringencodings` .

    :param length: integer or context lambda, length in bytes (not unicode characters)
    :param encoding: string like: utf8 utf16 utf32 ascii

    :raises StringError: building a non-unicode string
    :raises StringError: selected encoding is not on supported list

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = PaddedString(10, "utf8")
        >>> d.build(u"Афон")
        b'\xd0\x90\xd1\x84\xd0\xbe\xd0\xbd\x00\x00'
        >>> d.parse(_)
        u'Афон'
    """
    macro = StringEncoded(FixedSized(length, NullStripped(GreedyBytes, pad=encodingunit(encoding))), encoding)
    return macro


def PascalString(lengthfield, encoding):
    r"""
    Length-prefixed string. The length field can be variable length (such as VarInt) or fixed length (such as Int64ub). :class:`~dingsda.core.VarInt` is recommended when designing new protocols. Stored length is in bytes, not characters. Size is not defined.

    :param lengthfield: Construct instance, field used to parse and build the length (like VarInt Int64ub)
    :param encoding: string like: utf8 utf16 utf32 ascii

    :raises StringError: building a non-unicode string

    Example::

        >>> d = PascalString(VarInt, "utf8")
        >>> d.build(u"Афон")
        b'\x08\xd0\x90\xd1\x84\xd0\xbe\xd0\xbd'
        >>> d.parse(_)
        u'Афон'
    """
    macro = StringEncoded(Prefixed(lengthfield, GreedyBytes), encoding)

    return macro


def CString(encoding):
    r"""
    String ending in a terminating null byte (or null bytes in case of UTF16 UTF32).

    .. warning:: String and CString only support encodings explicitly listed in :class:`~dingsda.core.possiblestringencodings` .

    :param encoding: string like: utf8 utf16 utf32 ascii

    :raises StringError: building a non-unicode string
    :raises StringError: selected encoding is not on supported list

    Example::

        >>> d = CString("utf8")
        >>> d.build(u"Афон")
        b'\xd0\x90\xd1\x84\xd0\xbe\xd0\xbd\x00'
        >>> d.parse(_)
        u'Афон'
    """
    macro = StringEncoded(NullTerminated(GreedyBytes, term=encodingunit(encoding)), encoding)
    return macro


def GreedyString(encoding):
    r"""
    String that reads entire stream until EOF, and writes a given string as-is. Analog to :class:`~dingsda.core.GreedyBytes` but also applies unicode-to-bytes encoding.

    :param encoding: string like: utf8 utf16 utf32 ascii

    :raises StringError: building a non-unicode string
    :raises StreamError: stream failed when reading until EOF

    Example::

        >>> d = GreedyString("utf8")
        >>> d.build(u"Афон")
        b'\xd0\x90\xd1\x84\xd0\xbe\xd0\xbd'
        >>> d.parse(_)
        u'Афон'
    """
    macro = StringEncoded(GreedyBytes, encoding)
    return macro


class StringEncoded(Adapter):
    """Used internally."""

    def __init__(self, subcon, encoding):
        super().__init__(subcon)
        if not encoding:
            raise StringError("String* classes require explicit encoding")
        self.encoding = encoding

    def _decode(self, obj, context, path):
        return obj.decode(self.encoding)

    def _encode(self, obj, context, path):
        if not isinstance(obj, unicodestringtype):
            raise StringError("string encoding failed, expected unicode string", path=path)
        if obj == u"":
            return b""
        return obj.encode(self.encoding)

    def _toET(self, parent, name, context, path):
        assert (name is not None)

        data = str(get_current_field(context, name))
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

        insert_or_append_field(context, name, elem)
        return context

    def _is_simple_type(self):
        return True
