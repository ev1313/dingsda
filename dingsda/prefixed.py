import io
from typing import Any, Tuple, Dict

from dingsda.core import Construct, Subconstruct
from dingsda.helpers import stream_read, stream_write, stream_tell
from dingsda.lib.containers import Container, MetaInformation
from dingsda.struct import FocusedSeq

from dingsda import  len_, this, Rebuild


class Prefixed(Subconstruct):
    r"""
    Prefixes a field with byte count.

    Parses the length field. Then reads that amount of bytes, and parses subcon using only those bytes. Constructs that consume entire remaining stream are constrained to consuming only the specified amount of bytes (a substream). When building, data gets prefixed by its length. Optionally, length field can include its own size. Size is the sum of both fields sizes, unless either raises SizeofError.

    Analog to :class:`~dingsda.core.PrefixedArray` which prefixes with an element count, instead of byte count. Semantics is similar but implementation is different.

    :class:`~dingsda.core.VarInt` is recommended for new protocols, as it is more compact and never overflows.

    :param lengthfield: Construct instance, field used for storing the length
    :param subcon: Construct instance, subcon used for storing the value
    :param includelength: optional, bool, whether length field should include its own size, default is False

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes

    Example::

        >>> d = Prefixed(VarInt, GreedyRange(Int32ul))
        >>> d.parse(b"\x08abcdefgh")
        [1684234849, 1751606885]

        >>> d = PrefixedArray(VarInt, Int32ul)
        >>> d.parse(b"\x02abcdefgh")
        [1684234849, 1751606885]
    """

    def __init__(self, lengthfield, subcon, includelength=False):
        super().__init__(subcon)
        self.lengthfield = lengthfield
        self.includelength = includelength

    def _parse(self, stream, context, path):
        length = self.lengthfield._parsereport(stream, context, path)
        if self.includelength:
            length -= self.lengthfield._static_sizeof(context, path)
        data = stream_read(stream, length, path)
        return self.subcon._parsereport(io.BytesIO(data), context, path)

    def _build(self, obj, stream, context, path):
        stream2 = io.BytesIO()
        buildret = self.subcon._build(obj, stream2, context, path)
        data = stream2.getvalue()
        length = len(data)
        if self.includelength:
            length += self.lengthfield._static_sizeof(context, path)
        self.lengthfield._build(length, stream, context, path)
        stream_write(stream, data, len(data), path)
        return buildret

    def _static_sizeof(self, context, path):
        return self.lengthfield._static_sizeof(context, path) + self.subcon._static_sizeof(context, path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return self.lengthfield._sizeof(len(obj), context, path) + self.subcon._sizeof(obj, context, path)

    def _expected_size(self, stream, context, path):
        position1 = stream_tell(stream, path)
        length = self.lengthfield._parse(stream, context, path)
        if self.includelength:
            length -= self.lengthfield._sizeof(context, path)
        position2 = stream_tell(stream, path)
        return (position2-position1) + length


def PrefixedArray(countfield, subcon):
    r"""
    Prefixes an array with item count (as opposed to prefixed by byte count, see :class:`~dingsda.core.Prefixed`).

    :class:`~dingsda.core.VarInt` is recommended for new protocols, as it is more compact and never overflows.

    :param countfield: Construct instance, field used for storing the element count
    :param subcon: Construct instance, subcon used for storing each element

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises RangeError: consumed or produced too little elements

    Example::

        >>> d = Prefixed(VarInt, GreedyRange(Int32ul))
        >>> d.parse(b"\x08abcdefgh")
        [1684234849, 1751606885]

        >>> d = PrefixedArray(VarInt, Int32ul)
        >>> d.parse(b"\x02abcdefgh")
        [1684234849, 1751606885]
    """
    macro = FocusedSeq("items",
                       "count" / Rebuild(countfield, len_(this.items)),
                       "items" / subcon[this.count],
                       )

    # FIXME: FocusedSeq needs to be fixed, it should not be necessary to override these methods
    def _preprocess_size(obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        count_size = countfield._static_sizeof(context, path)
        meta_info = MetaInformation(offset=offset, size=0, end_offset=0)
        obj, child_meta_info = subcon._preprocess_size(obj=obj, context=context, path=path, offset=offset+count_size)
        meta_info.size = count_size + child_meta_info.size
        meta_info.end_offset = meta_info.offset + meta_info.size
        return obj, meta_info
    macro._preprocess_size = _preprocess_size

    def _expected_size(self, stream, context, path):
        position1 = stream_tell(stream, path)
        count = countfield._parse(stream, context, path)
        position2 = stream_tell(stream, path)
        return (position2-position1) + count * subcon._sizeof(context, path)
    macro._expected_size = _expected_size

    return macro
