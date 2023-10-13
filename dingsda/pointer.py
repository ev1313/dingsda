import itertools
from typing import Tuple, Any, Dict

from dingsda import Subconstruct, MetaInformation, evaluate, stream_tell, stream_seek, Container, ListContainer
from dingsda.arrays import Arrayconstruct


class Pointer(Subconstruct):
    r"""
    Jumps in the stream forth and back for one field.

    Parsing and building seeks the stream to new location, processes subcon, and seeks back to original location. Size is defined as 0 but that does not mean no bytes are written into the stream.

    Offset can be positive, indicating a position from stream beginning forward, or negative, indicating a position from EOF backwards.

    :param offset: integer or context lambda, positive or negative
    :param subcon: Construct instance
    :param stream: None to use original stream (default), or context lambda to provide a different stream

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises StreamError: stream is not seekable and tellable

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Pointer(8, Bytes(1))
        >>> d.parse(b"abcdefghijkl")
        b'i'
        >>> d.build(b"Z")
        b'\x00\x00\x00\x00\x00\x00\x00\x00Z'
    """

    def __init__(self, offset, subcon, stream=None):
        super().__init__(subcon)
        self.offset = offset
        self.stream = stream


    def _preprocess_size(self, obj, context, path, offset=0):
        # the offset doesn't change, because the pointer itself has no size
        # therefor just generate relative offsets from here
        obj, child_extra_info = self.subcon._preprocess_size(obj, context, path, offset=0)

        meta_info = MetaInformation(offset=offset, size=0, end_offset=offset, ptr_size = child_extra_info.size)

        return obj, meta_info

    def _parse(self, stream, context, path):
        offset = evaluate(self.offset, context)
        stream = evaluate(self.stream, context) or stream
        fallback = stream_tell(stream, path)
        stream_seek(stream, offset, 2 if offset < 0 else 0, path)
        obj = self.subcon._parsereport(stream, context, path)
        stream_seek(stream, fallback, 0, path)
        return obj

    def _build(self, obj, stream, context, path):
        offset = evaluate(self.offset, context)
        stream = evaluate(self.stream, context) or stream
        fallback = stream_tell(stream, path)
        stream_seek(stream, offset, 2 if offset < 0 else 0, path)
        buildret = self.subcon._build(obj, stream, context, path)
        stream_seek(stream, fallback, 0, path)
        return buildret


    def _toET(self, parent, name, context, path):
        return self.subcon._toET(context=context, name=name, parent=parent, path=f"{path} -> {name}")


    def _fromET(self, parent, name, context, path, is_root=False):
        return self.subcon._fromET(context=context, parent=parent, name=name, path=f"{path} -> {name}", is_root=is_root)

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 0


class Area(Arrayconstruct):
    r"""
    Area is designed to be used in file formats, that specify an offset and size for an field array.
    The wrapper takes the offset like a pointer and parses subcons until the size is reached.

    When preprocessing it sets the size variable in the context, the offset is untouched.

    When building it checks for nothing and just builds the subcon.

    _sizeof returns 0, as it is essentially a fancy pointer.

    :param subcon: Construct instance
    :param offset: int or lambda, offset to start reading from, may be negative
    :param size: int or lambda, size of the objects, checked vs stream position if check_stream_pos=True
    :param stream: stream instance to read from, else normal parsing stream is used.
    :param check_stream_pos: bool, if True, offset+size is checked vs stream position in the end, if False only parsed_size <= size is checked

    Example::
        Struct(
            "header1" / Struct(
                "offset" / Rebuild(Int32ul, lambda ctx: ctx._.get_meta("header1").end_offset),
                "size" / Rebuild(Int32ul, lambda ctx: ctx.get_meta("data1").size),
                "data1" / Area(Int32ul, this.offset, this.size),
            ),
            "header2" / Struct(
                "offset" / Rebuild(Int32ul, lambda ctx: ctx._.get_meta("header1").offset + ctx._.get_meta("header1").size),
                "size" / Rebuild(Int32ul, lambda ctx: ctx.get_meta("data2").size),
                "data2" / Area(Int8ul, this.offset, this.size),
            )
        )
    """

    def __init__(self, subcon, offset, size, stream=None, check_stream_pos=True, count=None):
        super().__init__(subcon)
        self.size = size
        self.offset = offset
        # if check_stream_pos is True, this is always == size or an error is raised when parsing
        # if check_stream_pos is False, this is the real size of the parsed data
        self.parsed_size = 0
        self.check_stream_pos = check_stream_pos
        self.stream = stream
        self.count = count

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        retlist = ListContainer()
        # this is essentially a fancy pointer, so no size (instead we use _ptr_size)
        meta_info = MetaInformation(offset=offset, size=0, end_offset=offset)
        ptrsize = 0
        for i, e in enumerate(obj):
            context._index = i
            obj, child_meta_info = self.subcon._preprocess_size(e, context, path, offset)
            retlist.append(obj)

            ptrsize += child_meta_info.size
            retlist.set_meta(i, child_meta_info)

        meta_info.ptr_size = ptrsize

        return retlist, meta_info

    def _parse(self, stream, context: Container, path: str):
        offset = evaluate(self.offset, context)
        size = evaluate(self.size, context)
        stream = evaluate(self.stream, context) or stream
        fallback = stream_tell(stream, path)

        assert(size >= 0)
        if size == 0:
            return []

        stream_seek(stream, offset, 2 if offset < 0 else 0, path)
        obj = ListContainer()
        for i in itertools.count():
            context._index = i
            e = self.subcon._parsereport(stream, context, path)
            obj.append(e)
            self.parsed_size = stream_tell(stream, path)
            if self.parsed_size >= offset + size:
                break

        if self.check_stream_pos:
            assert(self.parsed_size == offset + size)
        else:
            assert(self.parsed_size <= offset + size)

        if self.count is not None:
            count = evaluate(self.count, context)
            assert(len(obj) == count)

        stream_seek(stream, fallback, 0, path)
        return obj

    def _build(self, obj: Any, stream, context: Container, path: str):
        offset = evaluate(self.offset, context)
        size = evaluate(self.size, context)
        stream = evaluate(self.stream, context) or stream
        fallback = stream_tell(stream, path)

        stream_seek(stream, offset, 2 if offset < 0 else 0, path)
        for i,e in enumerate(obj):
            context._index = i
            self.subcon._build(e, stream, context, path)

        if self.check_stream_pos:
            assert(stream_tell(stream, path) == offset + size)
        else:
            assert(stream_tell(stream, path) <= offset + size)

        stream_seek(stream, fallback, 0, path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 0

