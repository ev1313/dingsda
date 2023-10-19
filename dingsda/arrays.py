import itertools

from dingsda.core import Subconstruct, sizeof_decorator
from dingsda.errors import SizeofError, RangeError, StopFieldError, ExplicitError, RepeatError
from dingsda.lib.containers import Container, ListContainer, MetaInformation
from dingsda.helpers import evaluate, stream_seek, stream_tell
from typing import Any, Dict, Optional, Tuple


class Arrayconstruct(Subconstruct):
    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Optional[MetaInformation]]:
        # predicates don't need to be checked in preprocessing
        for i, e in enumerate(obj):
            obj._index = i
            child_obj, _ = self.subcon._preprocess(e, obj, path)
            obj[i] = child_obj
            assert(_ is None)

        return obj, None

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Optional[MetaInformation]]:
        # predicates don't need to be checked in preprocessing
        meta_info = MetaInformation(offset=offset, size=0, end_offset=0)
        size = 0
        for i, e in enumerate(obj):
            context._index = i
            child_obj, child_meta_info = self.subcon._preprocess_size(e, obj, path, offset)
            obj[i] = child_obj

            offset += child_meta_info.size
            size += child_meta_info.size
            obj.set_meta(i, child_meta_info)

        meta_info.size = size
        meta_info.end_offset = offset

        return obj, meta_info

    def _toET(self, parent, name, context, path):
        data = get_current_field(context, name)

        # Simple fields -> FormatFields and Strings
        if self.subcon._is_simple_type() and not self.subcon._is_array():
            arr = []
            for idx, item in enumerate(data):
                # create new context including the index
                ctx = create_parent_context(context)
                ctx._index = idx
                ctx[f"{name}_{idx}"] = data[idx]

                obj = self.subcon._toET(None, name, ctx, path)
                arr += [obj]
            parent.attrib[name] = "[" + list_to_string(arr) + "]"
        else:
            sc_names = self.subcon._names()
            if len(sc_names) == 0:
                sc_names = [self.subcon.__class__.__name__]
            for idx, item in enumerate(data):
                # create new context including the index
                ctx = create_parent_context(context)
                ctx._index = idx
                ctx[f"{sc_names[0]}_{idx}"] = data[idx]

                elem = self.subcon._toET(parent, sc_names[0], ctx, path)
                if elem is not None:
                    parent.append(elem)

        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        context[name] = []

        # Simple fields -> FormatFields and Strings
        if self.subcon._is_simple_type() and not self.subcon._is_array():
            data = parent.attrib[name]
            assert(data[0] == "[")
            assert(data[-1] == "]")
            arr = string_to_list(data[1:-1])

            for x in arr:
                self.subcon._fromET(x, name, context, path, is_root=True)
        else:
            items = []
            sc_names = self.subcon._names()
            if len(sc_names) == 0:
                sc_names = [self.subcon.__class__.__name__]

            for n in sc_names:
                items += parent.findall(n)

            for item in items:
                self.subcon._fromET(item, name, context, path, is_root=True)

            for n in sc_names:
                if context.get(n, 1) == None:
                    context.pop(n)

        return context

    @sizeof_decorator
    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        try:
            return self._static_sizeof(context, path)
        except SizeofError:
            pass

        if obj is None:
            return 0

        sum_size = 0
        for i, e in enumerate(obj):
            context._index = i
            sum_size += self.subcon._sizeof(e, context[i], path)
        return sum_size

    def _is_simple_type(self, context: Optional[Container] = None) -> bool:
        return self.subcon._is_simple_type(context=context)

    def _is_array(self, context: Optional[Container] = None) -> bool:
        return True

    def _is_struct(self, context: Optional[Container] = None) -> bool:
        return False

    def _names(self) -> list[int]:
        return self.subcon._names()


class Array(Arrayconstruct):
    r"""
    Homogenous array of elements, similar to C# generic T[].

    Parses into a ListContainer (a list). Parsing and building processes an exact amount of elements. If given list has more or less than count elements, raises RangeError. Size is defined as count multiplied by subcon size, but only if subcon is fixed size.

    Operator [] can be used to make Array instances (recommended syntax).

    :param count: integer or context lambda, strict amount of elements
    :param subcon: Construct instance, subcon to process individual elements
    :param discard: optional, bool, if set then parsing returns empty list

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises RangeError: specified count is not valid
    :raises RangeError: given object has different length than specified count

    Can propagate any exception from the lambdas, possibly non-ConstructError.

    Example::

        >>> d = Array(5, Byte) or Byte[5]
        >>> d.build(range(5))
        b'\x00\x01\x02\x03\x04'
        >>> d.parse(_)
        [0, 1, 2, 3, 4]
    """

    def __init__(self, count, subcon, discard=False):
        super().__init__(subcon)
        self.count = count
        self.discard = discard

    def _parse(self, stream, context, path):
        count = evaluate(self.count, context)
        if not 0 <= count:
            raise RangeError("invalid count %s" % (count,), path=path)
        discard = self.discard
        obj = ListContainer(parent=context)
        for i in range(count):
            if self.subcon._is_struct(context=obj):
                ctx = Container(parent=obj)
            else:
                ctx = obj
            ctx._index = i
            obj._index = i
            e = self.subcon._parsereport(stream, ctx, path)
            if not discard:
                obj.append(e)
        return obj

    def _build(self, obj: Any, stream, context: Container, path: str):
        count = evaluate(self.count, context)
        if not 0 <= count:
            raise RangeError("invalid count %s" % (count,), path=path)
        if not len(obj) == count:
            raise RangeError("expected %d elements, found %d" % (count, len(obj)), path=path)
        for i,e in enumerate(obj):
            context._index = i
            self.subcon._build(e, stream, context, path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        try:
            count = evaluate(self.count, context, recurse=True)
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)
        return count * self.subcon._static_sizeof(context, path)


class GreedyRange(Subconstruct):
    r"""
    Homogenous array of elements, similar to C# generic IEnumerable<T>, but works with unknown count of elements by parsing until end of stream.

    Parses into a ListContainer (a list). Parsing stops when an exception occured when parsing the subcon, either due to EOF or subcon format not being able to parse the data. Either way, when GreedyRange encounters either failure it seeks the stream back to a position after last successful subcon parsing. Builds from enumerable, each element as-is. Size is undefined.

    This class supports stopping. If :class:`~dingsda.core.StopIf` field is a member, and it evaluates its lambda as positive, this class ends parsing or building as successful without processing further fields.

    :param subcon: Construct instance, subcon to process individual elements
    :param discard: optional, bool, if set then parsing returns empty list

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises StreamError: stream is not seekable and tellable

    Can propagate any exception from the lambdas, possibly non-ConstructError.

    Example::

        >>> d = GreedyRange(Byte)
        >>> d.build(range(8))
        b'\x00\x01\x02\x03\x04\x05\x06\x07'
        >>> d.parse(_)
        [0, 1, 2, 3, 4, 5, 6, 7]
    """

    def __init__(self, subcon, discard=False):
        super().__init__(subcon)
        self.discard = discard

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Optional[MetaInformation]]:
        # predicates don't need to be checked in preprocessing
        retlist = ListContainer(parent=context)
        for i, e in enumerate(obj):
            context._index = i
            obj, _ = self.subcon._preprocess(e, context, path)
            assert(_ is None)
            retlist.append(obj)

        return retlist, None

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Optional[MetaInformation]]:
        # predicates don't need to be checked in preprocessing
        retlist = ListContainer(parent=context)
        meta_info = MetaInformation(offset=offset, size=0, end_offset=0)
        size = 0
        for i,e in enumerate(obj):
            context._index = i
            obj, child_meta_info = self.subcon._preprocess_size(e, context, path, offset)
            retlist.append(obj)

            offset += child_meta_info.size
            size += child_meta_info.size
            retlist.set_meta(i, child_meta_info)

        meta_info.size = size
        meta_info.end_offset = offset

        return retlist, meta_info

    def _parse(self, stream, context, path):
        discard = self.discard
        obj = ListContainer(parent=context)
        try:
            for i in itertools.count():
                fallback = stream_tell(stream, path)
                if self.subcon._is_struct(context=obj):
                    ctx = Container(parent=obj)
                else:
                    ctx = obj
                ctx._index = i
                obj._index = i
                e = self.subcon._parsereport(stream, ctx, path)
                if not discard:
                    obj.append(e)
        except StopFieldError:
            pass
        except ExplicitError:
            raise
        except Exception:
            stream_seek(stream, fallback, 0, path)
        return obj

    def _build(self, obj: Any, stream, context: Container, path: str):
        try:
            for i,e in enumerate(obj):
                context._index = i
                self.subcon._build(e, stream, context, path)
        except StopFieldError:
            pass

    def _static_sizeof(self, context: Container, path: str) -> int:
        raise SizeofError("GreedyRange cannot calculate size statically", path)


class RepeatUntil(Arrayconstruct):
    r"""
    Homogenous array of elements, similar to C# generic IEnumerable<T>, that repeats until the predicate indicates it to stop. Note that the last element (that predicate indicated as True) is included in the return list.

    Parse iterates indefinately until last element passed the predicate. Build iterates indefinately over given list, until an element passed the precicate (or raises RepeatError if no element passed it). Size is undefined.

    :param predicate: lambda that takes (obj, list, context) and returns True to break or False to continue (or a truthy value)
    :param subcon: Construct instance, subcon used to parse and build each element
    :param discard: optional, bool, if set then parsing returns empty list
    :param check_predicate: optional, bool, if set then the predicate is checked when building. Defaults to True.

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises RepeatError: consumed all elements in the stream but neither passed the predicate

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = RepeatUntil(lambda x,lst,ctx: x > 7, Byte)
        >>> d.build(range(20))
        b'\x00\x01\x02\x03\x04\x05\x06\x07\x08'
        >>> d.parse(b"\x01\xff\x02")
        [1, 255]

        >>> d = RepeatUntil(lambda x,lst,ctx: lst[-2:] == [0,0], Byte)
        >>> d.parse(b"\x01\x00\x00\xff")
        [1, 0, 0]
    """

    def __init__(self, predicate, subcon, discard=False, check_predicate=True):
        super().__init__(subcon)
        self.predicate = predicate
        self.discard = discard
        self.check_predicate = check_predicate

    def _parse(self, stream, context, path):
        predicate = self.predicate
        discard = self.discard
        if not callable(predicate):
            predicate = lambda _1,_2,_3: predicate
        obj = ListContainer(parent=context)
        for i in itertools.count():
            obj._index = i
            e = self.subcon._parsereport(stream, obj, path)
            if not discard:
                obj.append(e)
            if predicate(e, obj, obj):
                return obj
        assert(False)

    def _build(self, obj: Any, stream, context: Container, path: str):
        predicate = self.predicate
        if not callable(predicate):
            predicate = lambda _1,_2,_3: predicate
        for i,e in enumerate(obj):
            context._index = i
            self.subcon._build(e, stream, context, path)
            if self.check_predicate and predicate(e, obj[:i+1], context):
                break
        else:
            raise RepeatError("expected any item to match predicate, when building", path=path)

    def _names(self) -> list[str]:
        sc_names = [self.name]
        sc_names += self.subcon._names()
        return sc_names

    def _static_sizeof(self, context: Container, path: str) -> int:
        raise SizeofError("cannot calculate size of RepeatUntil", path=path)
