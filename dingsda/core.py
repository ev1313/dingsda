# -*- coding: utf-8 -*-
import pdb
import io, binascii, itertools, collections, os

from typing import Tuple, Dict, Any

from dingsda.errors import *
from dingsda.lib import *
from dingsda.expr import *
from dingsda.helpers import *

import xml.etree.ElementTree as ET

class Construct(object):
    r"""
    The mother of all constructs.

    This object is generally not directly instantiated, and it does not directly implement parsing and building, so it is largely only of interest to subclass implementors. There are also other abstract classes sitting on top of this one.

    The external user API:

    * `parse`
    * `parse_stream`
    * `parse_file`
    * `preprocess`
    * `build`
    * `build_stream`
    * `build_file`
    * `toET`
    * `fromET`
    * `static_sizeof`
    * `sizeof`
    * `full_sizeof`

    Subclass authors should not override the external methods. Instead, another API is available:

    * `_parse`
    * `_preprocess`
    * `_build`
    * `_toET`
    * `_fromET`
    * `_static_sizeof`
    * `_sizeof`
    * `_full_sizeof`
    * `_expected_sizeof`
    * `__getstate__`
    * `__setstate__`

    Attributes and Inheritance:

    All constructs have a name and flags. The name is used for naming struct members and context dictionaries. Note that the name can be a string, or None by default. A single underscore "_" is a reserved name, used as up-level in nested containers. The name should be descriptive, short, and valid as a Python identifier, although these rules are not enforced. The flags specify additional behavioral information about this construct. Flags are used by enclosing constructs to determine a proper course of action. Flags are often inherited from inner subconstructs but that depends on each class.
    """
    def __init__(self):
        self.name = None
        self.docs = ""
        self.flagbuildnone = False
        self.parsed = None

    def __repr__(self):
        return "<%s%s%s%s>" % (self.__class__.__name__, " "+self.name if self.name else "", " +nonbuild" if self.flagbuildnone else "", " +docs" if self.docs else "", )

    def __getstate__(self):
        attrs = {}
        if hasattr(self, "__dict__"):
            attrs.update(self.__dict__)
        slots = []
        c = self.__class__
        while c is not None:
            if hasattr(c, "__slots__"):
                slots.extend(c.__slots__)
            c = c.__base__
        for name in slots:
            if hasattr(self, name):
                attrs[name] = getattr(self, name)
        return attrs

    def __setstate__(self, attrs):
        for name, value in attrs.items():
            setattr(self, name, value)

    def __copy__(self):
        self2 = object.__new__(self.__class__)
        self2.__setstate__(self.__getstate__())
        return self2

    def parse(self, data: bytes, **contextkw):
        r"""
        Parse an in-memory buffer (often bytes object). Strings, buffers, memoryviews, and other complete buffers can be parsed with this method.

        Whenever data cannot be read, ConstructError or its derivative is raised. This method is NOT ALLOWED to raise any other exceptions although (1) user-defined lambdas can raise arbitrary exceptions which are propagated (2) external libraries like numpy can raise arbitrary exceptions which are propagated (3) some list and dict lookups can raise IndexError and KeyError which are propagated.

        Context entries are passed only as keyword parameters \*\*contextkw.

        :param \*\*contextkw: contcore.pyext entries, usually empty

        :returns: some value, usually based on bytes read from the stream but sometimes it is computed from nothing or from the context dictionary, sometimes its non-deterministic

        :raises ConstructError: raised for any reason
        """
        return self.parse_stream(io.BytesIO(data), **contextkw)

    def parse_stream(self, stream, **contextkw):
        r"""
        Parse a stream. Files, pipes, sockets, and other streaming sources of data are handled by this method. See parse().
        """
        context = Container(**contextkw)
        context._preprocessing = False
        context._parsing = True
        context._building = False
        context._sizing = False
        context._params = context
        try:
            return self._parsereport(stream, context, "(parsing)")
        except CancelParsing:
            pass

    def parse_file(self, filename, **contextkw):
        r"""
        Parse a closed binary file. See parse().
        """
        with open(filename, 'rb') as f:
            return self.parse_stream(f, **contextkw)

    def _parsereport(self, stream, context, path):
        obj = self._parse(stream, context, path)
        if self.parsed is not None:
            self.parsed(obj, context)
        return obj

    def _parse(self, stream, context, path):
        """Override in your subclass."""
        raise NotImplementedError

    def _toET(self, parent, name, context, path):
        raise NotImplementedError

    def _fromET(self, parent, name, context, path, is_root=False):
        raise NotImplementedError

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        r"""
           Preprocess an object before building or sizing, called by the preprocess function.

            The basic preprocess function just returns the object and an empty dictionary.

            :param obj: the object to preprocess
            :param context: the context dictionary
            :param path: the path to the construct

            :return obj: the preprocessed object
            :return extra_info: a dictionary containing extra information regarding offset, size, etc.
        """
        return obj, {}


    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        r"""
           Preprocess an object before building or sizing, called by the preprocess function.

            The extended preprocess function just returns the object and calls the
            standard _sizeof function. This doesn't work for all constructs, so
            these need to implement their own _preprocess_size function for correct _sizeof.

            This function is called after the basic _preprocess function was evaluated for the whole context, so
            it may access all Rebuilds for sizing.

            :param obj: the object to preprocess
            :param context: the context dictionary
            :param path: the path to the construct

            :return obj: the preprocessed object
            :return extra_info: a dictionary containing extra information regarding offset, size, etc.
        """
        ctx = Container(**context)
        # FIXME: i do not know a better solution for this yet
        if isinstance(obj, dict) or isinstance(obj, Container):
            ctx.update(obj)
        size = self._sizeof(obj, ctx, path)
        return obj, {"_offset": offset, "_size": size, "_endoffset": offset + size}

    def build(self, obj, **contextkw):
        r"""
        Build an object in memory (a bytes object).

        Whenever data cannot be written, ConstructError or its derivative is raised. This method is NOT ALLOWED to raise any other exceptions although (1) user-defined lambdas can raise arbitrary exceptions which are propagated (2) external libraries like numpy can raise arbitrary exceptions which are propagated (3) some list and dict lookups can raise IndexError and KeyError which are propagated.

        Context entries are passed only as keyword parameters \*\*contextkw.

        :param \*\*contextkw: context entries, usually empty

        :returns: bytes

        :raises ConstructError: raised for any reason
        """
        stream = io.BytesIO()
        self.build_stream(obj, stream, **contextkw)
        return stream.getvalue()

    def build_stream(self, obj, stream, **contextkw):
        r"""
        Build an object directly into a stream. See build().
        """
        context = Container(**contextkw)
        context._parsing = False
        context._preprocessing = False
        context._building = True
        context._sizing = False
        context._params = context
        self._build(obj, stream, context, "(building)")

    def build_file(self, obj, filename, **contextkw):
        r"""
        Build an object into a closed binary file. See build().
        """
        # Open the file for reading as well as writing. This allows builders to
        # read back the stream just written. For example. RawCopy does this.
        # See issue #888.
        with open(filename, 'w+b') as f:
            self.build_stream(obj, f, **contextkw)

    def _build(self, obj, stream, context, path):
        """Override in your subclass."""
        raise NotImplementedError

    def toET(self, obj, name="Root", **contextkw):
        r"""
            Convert a parsed construct to a XML ElementTree.

            This method creates the root node for the following _toET calls, so
            even FormatFields can attach their values to an attrib.

        :param obj: The object
        :param contextkw: further arguments, passed directly into the context
        :returns: an ElementTree
        """

        context = Container(**contextkw)
        context._preprocessing = False
        context._parsing = False
        context._building = False
        context._sizing = False
        context._params = context
        context[name] = obj
        # create root node
        xml = ET.Element(name)
        return self._toET(parent=xml, context=context, name=name, path="(toET)")

    def fromET(self, xml, **contextkw):
        r"""
            Convert an XML ElementTree to a construct.

        :param xml: The ElementTree
        :param contextkw: further arguments, passed directly into the context
        :returns: a Container
        """

        context = Container(**contextkw)
        context._preprocessing = False
        context._parsing = False
        context._building = False
        context._sizing = False
        context._params = context
        # create root node
        parent = ET.Element("Root")
        parent.append(xml)
        result = self._fromET(parent=parent, name=xml.tag, context=context, path="(fromET)")

        return result.get(xml.tag)

    def preprocess(self, obj: Any, sizing: bool = True, **contextkw) -> Tuple[Any, Dict[str, Any]]:
        r"""
            Preprocess an object before building.

            The basic preprocessing step adds for some special Constructs like Rebuilds lambdas or other
            values to the construct, so especially Rebuilds can use them in the build step afterwards.

            After the basic preprocessing, if the sizing parameter is set, the size of the construct and
            all subconstructs is added to the context. This adds attributes like _size and _ptrsize.

            :param obj: the object to preprocess
            :param sizing: whether to size the object after the first preprocessing step.
            :return obj: the preprocessed object
            :return extra_info: the dictionary containing extra information for the *current* object, like offset, size, etc.
        """
        context = Container(**contextkw)
        context._preprocessing = True
        context._parsing = False
        context._building = False
        context._sizing = False
        context._params = context

        obj, extra_info = self._preprocess(obj=obj, context=context, path="(preprocess)")

        if sizing:
            return self._preprocess_size(obj=obj, context=context, path="(preprocess_size)", offset=0)

        return obj, extra_info

    def static_sizeof(self, **contextkw):
        r"""
        Calculate the size of this object without the use of an already parsed object.

        This always works for Constructs with static sizes like FormatFields, but doesn't for Constructs
        with dynamic length like Strings or RepeatUntil.

        Whenever size cannot be determined, a SizeofError is raised.

        :returns: integer if computable, raises SizeofError otherwise

        :raises SizeofError: size could not be determined in current context, or is impossible to be determined
        """
        context = Container(**contextkw)
        context._preprocessing = False
        context._parsing = False
        context._building = False
        context._sizing = True
        context._params = context
        return self._static_sizeof(context, "(static_sizeof)")

    def sizeof(self, obj: Container, **contextkw) -> int:
        r"""
        Calculate the size of this object using a parsed object as context.

        This always works for Constructs with static sizes, but as the actual data is given with obj,
        it also works for Constructs with variable lengths like Strings.

        If _sizeof is not implemented, _static_sizeof is returned instead by default.

        Whenever size cannot be determined, a SizeofError is raised.

        :param: obj the parsed object for that the sizes of the fields shall be determined
        :returns: integer if computable, raises SizeofError otherwise

        :raises SizeofError: size could not be determined in current context, or is impossible to be determined
        """
        context = Container(**contextkw)
        context._preprocessing = False
        context._parsing = False
        context._building = False
        context._sizing = True
        context._params = context
        if isinstance(obj, dict) or isinstance(obj, Container):
            context.update(obj)

        return self._sizeof(obj, context, "(sizeof)")

    def full_sizeof(self, obj: Container, **contextkw) -> int:
        r"""
        Calculate the full size of this object using a parsed object as context.

        The full size is only relevant for Pointer types - these return for sizeof usually 0, because they only
        point to other data. However sometimes it can be useful to know the actual size of the Pointer.

        The full size of Structs will include the sum of the sizes of all fields, and the sizes of the referenced
        Pointer data.

        Note this can not be used to determine the end of a buffer / the full size of a buffer, as empty places
        between mapped Constructs and the Pointer data will not be accounted for. Usually just use this on
        Pointertypes, so you don't have to search for the _ptrsize attribute.

        This function is experimental!

        If _full_sizeof is not implemented, _sizeof is returned instead by default.

        Whenever size cannot be determined, a SizeofError is raised.

        :param: obj the parsed object for that the sizes of the fields shall be determined
        :returns: integer if computable, raises SizeofError otherwise

        :raises SizeofError: size could not be determined in current context, or is impossible to be determined
        """
        context = Container(**contextkw)
        context._preprocessing = False
        context._parsing = False
        context._building = False
        context._sizing = True
        context._params = context
        context.update(obj)
        return self._full_sizeof(obj, context, "(full_sizeof)")

    def _static_sizeof(self, context: Container, path: str) -> int:
        """Override in your subclass."""
        raise SizeofError(path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        """Override in your subclass."""
        return self._static_sizeof(context, path)

    def _full_sizeof(self, obj: Any, context: Container, path: str) -> int:
        """Override in your subclass."""
        return self._sizeof(obj, context, path)

    def _expected_size(self, stream, context: Container, path: str) -> int:
        r"""
        This is a special function for length prefixed objects. LazyStruct and LazyArray use this, to
        skip parsing wherever possible.

        Default is just returning the static size of the object.

        Whenever size cannot be determined, a SizeofError is raised.

        :param: stream the stream the length is read from. It needs to be advanced to the end of the data after reading the length.
        :param: context the current context
        :param: path the current path
        :returns: integer if computable, raises SizeofError otherwise

        :raises SizeofError: size could not be determined in current context, or is impossible to be determined
        """
        return self._static_sizeof(context, path)

    def _names(self) -> list:
        """
        determines the name of the XML tag, normal classes just return an empty list,
        however Renamed, FocusedSeq, and Switch override this, because they use these names for
        identification
        """
        return []

    def _is_simple_type(self) -> bool:
        """ is used by Array to determine, whether the type can be stored in a string array as XML attribute """
        return False;

    def _is_array(self) -> bool:
        """ is used by Array to detect nested arrays (is a problem with Array of Array of simple type) """
        return False;

    def __rtruediv__(self, name):
        """
        Used for renaming subcons, usually part of a Struct, like Struct("index" / Byte).
        """
        return Renamed(self, newname=name)

    __rdiv__ = __rtruediv__

    def __mul__(self, other):
        """
        Used for adding docstrings and parsed hooks to subcons, like "field" / Byte * "docstring" * processfunc.
        """
        if isinstance(other, stringtypes):
            return Renamed(self, newdocs=other)
        if callable(other):
            return Renamed(self, newparsed=other)
        raise ConstructError("operator * can only be used with string or lambda")

    def __rmul__(self, other):
        """
        Used for adding docstrings and parsed hooks to subcons, like "field" / Byte * "docstring" * processfunc.
        """
        if isinstance(other, stringtypes):
            return Renamed(self, newdocs=other)
        if callable(other):
            return Renamed(self, newparsed=other)
        raise ConstructError("operator * can only be used with string or lambda")

    def __add__(self, other):
        """
        Used for making Struct like ("index"/Byte + "prefix"/Byte).
        """
        lhs = self.subcons  if isinstance(self,  Struct) else [self]
        rhs = other.subcons if isinstance(other, Struct) else [other]
        return Struct(*(lhs + rhs))

    def __rshift__(self, other):
        """
        Used for making Sequences like (Byte >> Short).
        """
        lhs = self.subcons  if isinstance(self,  Sequence) else [self]
        rhs = other.subcons if isinstance(other, Sequence) else [other]
        return Sequence(*(lhs + rhs))

    def __getitem__(self, count):
        """
        Used for making Arrays like Byte[5] and Byte[this.count].
        """
        if isinstance(count, slice):
            raise ConstructError("subcon[N] syntax can only be used for Arrays, use GreedyRange(subcon) instead?")
        if isinstance(count, int) or callable(count):
            return Array(count, self)
        raise ConstructError("subcon[N] syntax expects integer or context lambda")


class Subconstruct(Construct):
    r"""
    Abstract subconstruct (wraps an inner construct, inheriting its name and flags). Parsing and building is by default deferred to subcon, same as sizeof.

    :param subcon: Construct instance
    """
    def __init__(self, subcon):
        if not isinstance(subcon, Construct):
            raise TypeError("subcon should be a Construct field")
        super().__init__()
        self.subcon = subcon
        self.flagbuildnone = subcon.flagbuildnone

    def __repr__(self):
        return "<%s%s%s%s %s>" % (self.__class__.__name__, " "+self.name if self.name else "", " +nonbuild" if self.flagbuildnone else "", " +docs" if self.docs else "", repr(self.subcon), )

    def _parse(self, stream, context, path):
        return self.subcon._parsereport(stream, context, path)

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        return self.subcon._preprocess(obj, context, path)

    def _build(self, obj, stream, context, path):
        return self.subcon._build(obj, stream, context, path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        return self.subcon._static_sizeof(context, path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return self.subcon._sizeof(obj, context, path)

    def _full_sizeof(self, obj: Any, context: Container, path: str) -> int:
        return self.subcon._full_sizeof(obj, context, path)


class Structconstruct(Construct):
    def _is_simple_type(self) -> bool:
        return False

    def _static_sizeof(self, context: Container, path: str) -> int:
        try:
            return sum(sc._static_sizeof(context, path) for sc in self.subcons)
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        try:
            return self._static_sizeof(context, path)
        except SizeofError:
            pass
        try:
            size_sum = 0
            for sc in self.subcons:
                try:
                    size_sum += sc._static_sizeof(context, path)
                except SizeofError:
                    if not sc._is_array():
                        ctx = create_child_context(context, obj)
                    else:
                        ctx = create_child_context(context, {})

                    for name in sc._names():
                        child_obj = context.get(name, None)
                        if child_obj is not None:
                            break

                    size_sum += sc._sizeof(child_obj, ctx, path)

            return size_sum
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)
        assert(0)


class Arrayconstruct(Subconstruct):
    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        # predicates don't need to be checked in preprocessing
        retlist = ListContainer()
        extra_info = {}
        for i, e in enumerate(obj):
            context._index = i
            child_obj, child_extra_info = self.subcon._preprocess(e, context, path)
            retlist.append(child_obj)

            extra = {f"_{i}{k}": v for k, v in child_extra_info.items()}
            extra_info.update(extra)

            context.update(extra_info)

        return retlist, extra_info

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        # predicates don't need to be checked in preprocessing
        retlist = ListContainer()
        extra_info = {"_offset": offset}
        size = 0
        for i, e in enumerate(obj):
            context._index = i
            child_obj, child_extra_info = self.subcon._preprocess_size(e, context, path, offset)
            retlist.append(child_obj)

            extra = {f"_{i}{k}": v for k, v in child_extra_info.items()}
            extra_info.update(extra)
            offset += child_extra_info["_size"]
            size += child_extra_info["_size"]

            context.update(extra_info)

        extra_info["_size"] = size
        extra_info["_endoffset"] = offset

        return retlist, extra_info

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
            sum_size += self.subcon._sizeof(e, context, path)
        return sum_size

    def _is_simple_type(self) -> bool:
        return self.subcon._is_simple_type()

    def _is_array(self) -> bool:
        return True

    def _names(self) -> list[int]:
        return self.subcon._names()


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
        buildret = self.subcon._build(obj2, stream, context, path)
        # FIXME: is this a bug?
        return obj

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


class Validator(SymmetricAdapter):
    r"""
    Abstract class that validates a condition on the encoded/decoded object.

    Needs to implement `_validate()` that returns a bool (or a truthy value)

    :param subcon: Construct instance
    """
    def _decode(self, obj, context, path):
        if not self._validate(obj, context, path):
            raise ValidationError("object failed validation: %s" % (obj,), path=path)
        return obj

    def _validate(self, obj, context, path):
        raise NotImplementedError


class Tunnel(Subconstruct):
    r"""
    Abstract class that allows other constructs to read part of the stream as if they were reading the entire stream. See Prefixed for example.

    Needs to implement `_decode()` for parsing and `_encode()` for building.
    """
    def _parse(self, stream, context, path):
        data = stream_read_entire(stream, path)  # reads entire stream
        data = self._decode(data, context, path)
        return self.subcon.parse(data, **context)

    def _build(self, obj, stream, context, path):
        stream2 = io.BytesIO()
        buildret = self.subcon._build(obj, stream2, context, path)
        data = stream2.getvalue()
        data = self._encode(data, context, path)
        stream_write(stream, data, len(data), path)
        return obj

    def _static_sizeof(self, context, path):
        raise SizeofError(path=path)

    def _sizeof(self, obj, context, path):
        raise SizeofError(path=path)

    def _full_sizeof(self, obj, context, path):
        raise SizeofError(path=path)

    def _decode(self, data, context, path):
        raise NotImplementedError

    def _encode(self, data, context, path):
        raise NotImplementedError


#===============================================================================
# bytes and bits
#===============================================================================
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
        return data

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

    def _is_simple_type(self):
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
        return data

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

    def _is_simple_type(self):
        return True


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


#===============================================================================
# mappings
#===============================================================================
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
        return obj

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 1

class EnumInteger(int):
    """Used internally."""
    pass


class EnumIntegerString(str):
    """Used internally."""

    def __repr__(self):
        return "EnumIntegerString.new(%s, %s)" % (self.intvalue, str.__repr__(self), )

    def __int__(self):
        return self.intvalue

    @staticmethod
    def new(intvalue, stringvalue):
        ret = EnumIntegerString(stringvalue)
        ret.intvalue = intvalue
        return ret


class Enum(Adapter):
    r"""
    Translates unicode label names to subcon values, and vice versa.

    Parses integer subcon, then uses that value to lookup mapping dictionary. Returns an integer-convertible string (if mapping found) or an integer (otherwise). Building is a reversed process. Can build from an integer flag or string label. Size is same as subcon, unless it raises SizeofError.

    There is no default parameter, because if no mapping is found, it parses into an integer without error.

    This class supports enum34 module. See examples.

    This class supports exposing member labels as attributes, as integer-convertible strings. See examples.

    :param subcon: Construct instance, subcon to map to/from
    :param \*merge: optional, list of enum.IntEnum and enum.IntFlag instances, to merge labels and values from
    :param \*\*mapping: dict, mapping string names to values

    :raises MappingError: building from string but no mapping found

    Example::

        >>> d = Enum(Byte, one=1, two=2, four=4, eight=8)
        >>> d.parse(b"\x01")
        'one'
        >>> int(d.parse(b"\x01"))
        1
        >>> d.parse(b"\xff")
        255
        >>> int(d.parse(b"\xff"))
        255

        >>> d.build(d.one or "one" or 1)
        b'\x01'
        >>> d.one
        'one'

        import enum
        class E(enum.IntEnum or enum.IntFlag):
            one = 1
            two = 2

        Enum(Byte, E) <--> Enum(Byte, one=1, two=2)
        FlagsEnum(Byte, E) <--> FlagsEnum(Byte, one=1, two=2)
    """

    def __init__(self, subcon, *merge, **mapping):
        super().__init__(subcon)
        for enum in merge:
            for enumentry in enum:
                mapping[enumentry.name] = enumentry.value
        self.encmapping = {EnumIntegerString.new(v, k): v for k, v in mapping.items()}
        self.decmapping = {v: EnumIntegerString.new(v, k) for k, v in mapping.items()}

    def __getattr__(self, name):
        if name in self.encmapping:
            return self.decmapping[self.encmapping[name]]
        raise AttributeError

    def _decode(self, obj, context, path):
        try:
            return self.decmapping[obj]
        except KeyError:
            return EnumInteger(obj)

    def _encode(self, obj, context, path):
        try:
            if isinstance(obj, integertypes):
                return obj
            return self.encmapping[obj]
        except KeyError:
            raise MappingError("building failed, no mapping for %r" % (obj,), path=path)


    def _toET(self, parent, name, context, path):
        mapping = self.decmapping.get(context[name], None)
        if mapping is None:
            return self.subcon._toET(context=context, name=name, parent=parent, path=f"{path} -> {name}")
        else:
            # FIXME: only works for FormatFields (/ Strings)
            parent.attrib[name] = mapping
            return None


    def _fromET(self, parent, name, context, path, is_root=False):
        # FIXME: only works for FormatFields (/ Strings)
        elem = parent.attrib[name]

        mapping = self.encmapping.get(elem, None)

        if mapping is None:
            return self.subcon._fromET(context=context, parent=parent, name=name, path=f"{path} -> {name}", is_root=is_root)
        else:
            context[name] = elem
            return context


class BitwisableString(str):
    """Used internally."""

    # def __repr__(self):
    #     return "BitwisableString(%s)" % (str.__repr__(self), )

    def __or__(self, other):
        return BitwisableString("{}|{}".format(self, other))


class FlagsEnum(Adapter):
    r"""
    Translates unicode label names to subcon integer (sub)values, and vice versa.

    Parses integer subcon, then creates a Container, where flags define each key. Builds from a container by bitwise-oring of each flag if it matches a set key. Can build from an integer flag or string label directly, as well as | concatenations thereof (see examples). Size is same as subcon, unless it raises SizeofError.

    This class supports enum34 module. See examples.

    This class supports exposing member labels as attributes, as bitwisable strings. See examples.

    :param subcon: Construct instance, must operate on integers
    :param \*merge: optional, list of enum.IntEnum and enum.IntFlag instances, to merge labels and values from
    :param \*\*flags: dict, mapping string names to integer values

    :raises MappingError: building from object not like: integer string dict
    :raises MappingError: building from string but no mapping found

    Can raise arbitrary exceptions when computing | and & and value is non-integer.

    Example::

        >>> d = FlagsEnum(Byte, one=1, two=2, four=4, eight=8)
        >>> d.parse(b"\x03")
        Container(one=True, two=True, four=False, eight=False)
        >>> d.build(dict(one=True,two=True))
        b'\x03'

        >>> d.build(d.one|d.two or "one|two" or 1|2)
        b'\x03'

        import enum
        class E(enum.IntEnum or enum.IntFlag):
            one = 1
            two = 2

        Enum(Byte, E) <--> Enum(Byte, one=1, two=2)
        FlagsEnum(Byte, E) <--> FlagsEnum(Byte, one=1, two=2)
    """

    def __init__(self, subcon, *merge, **flags):
        super().__init__(subcon)
        for enum in merge:
            for enumentry in enum:
                flags[enumentry.name] = enumentry.value
        self.flags = flags
        self.reverseflags = {v:k for k,v in flags.items()}

    def __getattr__(self, name):
        if name in self.flags:
            return BitwisableString(name)
        raise AttributeError

    def _decode(self, obj, context, path):
        obj2 = Container()
        obj2._flagsenum = True
        for name,value in self.flags.items():
            obj2[BitwisableString(name)] = (obj & value == value)
        return obj2

    def _encode(self, obj, context, path):
        try:
            if isinstance(obj, integertypes):
                return obj
            if isinstance(obj, stringtypes):
                flags = 0
                for name in obj.split("|"):
                    name = name.strip()
                    if name:
                        flags |= self.flags[name] # KeyError
                return flags
            if isinstance(obj, dict):
                flags = 0
                for name,value in obj.items():
                    if not name.startswith("_"): # assumes key is a string
                        if value:
                            flags |= self.flags[name] # KeyError
                return flags
            raise MappingError("building failed, unknown object: %r" % (obj,), path=path)
        except KeyError:
            raise MappingError("building failed, unknown label: %r" % (obj,), path=path)


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


#===============================================================================
# structures and sequences
#===============================================================================
class Struct(Structconstruct):
    r"""
    Sequence of usually named constructs, similar to structs in C. The members are parsed and build in the order they are defined. If a member is anonymous (its name is None) then it gets parsed and the value discarded, or it gets build from nothing (from None).

    Some fields do not need to be named, since they are built without value anyway. See: Const Padding Check Error Pass Terminated Seek Tell for examples of such fields.

    Operator + can also be used to make Structs (although not recommended).

    Parses into a Container (dict with attribute and key access) where keys match subcon names. Builds from a dict (not necessarily a Container) where each member gets a value from the dict matching the subcon name. If field has build-from-none flag, it gets build even when there is no matching entry in the dict. Size is the sum of all subcon sizes, unless any subcon raises SizeofError.

    This class does context nesting, meaning its members are given access to a new dictionary where the "_" entry points to the outer context. When parsing, each member gets parsed and subcon parse return value is inserted into context under matching key only if the member was named. When building, the matching entry gets inserted into context before subcon gets build, and if subcon build returns a new value (not None) that gets replaced in the context.

    This class exposes subcons as attributes. You can refer to subcons that were inlined (and therefore do not exist as variable in the namespace) by accessing the struct attributes, under same name. Also note that compiler does not support this feature. See examples.

    This class exposes subcons in the context. You can refer to subcons that were inlined (and therefore do not exist as variable in the namespace) within other inlined fields using the context. Note that you need to use a lambda (`this` expression is not supported). Also note that compiler does not support this feature. See examples.

    This class supports stopping. If :class:`~dingsda.core.StopIf` field is a member, and it evaluates its lambda as positive, this class ends parsing or building as successful without processing further fields.

    :param \*subcons: Construct instances, list of members, some can be anonymous
    :param \*\*subconskw: Construct instances, list of members (requires Python 3.6)

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises KeyError: building a subcon but found no corresponding key in dictionary

    Example::

        >>> d = Struct("num"/Int8ub, "data"/Bytes(this.num))
        >>> d.parse(b"\x04DATA")
        Container(num=4, data=b"DATA")
        >>> d.build(dict(num=4, data=b"DATA"))
        b"\x04DATA"

        >>> d = Struct(Const(b"MZ"), Padding(2), Pass, Terminated)
        >>> d.build({})
        b'MZ\x00\x00'
        >>> d.parse(_)
        Container()
        >>> d.sizeof()
        4

        >>> d = Struct(
        ...     "animal" / Enum(Byte, giraffe=1),
        ... )
        >>> d.animal.giraffe
        'giraffe'
        >>> d = Struct(
        ...     "count" / Byte,
        ...     "data" / Bytes(lambda this: this.count - this._subcons.count.sizeof()),
        ... )
        >>> d.build(dict(count=3, data=b"12"))
        b'\x0312'

        Alternative syntax (not recommended):
        >>> ("a"/Byte + "b"/Byte + "c"/Byte + "d"/Byte)

        Alternative syntax, but requires Python 3.6 or any PyPy:
        >>> Struct(a=Byte, b=Byte, c=Byte, d=Byte)
    """

    def __init__(self, *subcons, **subconskw):
        super().__init__()
        self.subcons = list(subcons) + list(k/v for k,v in subconskw.items())
        self._subcons = Container((sc.name,sc) for sc in self.subcons if sc.name)
        self.flagbuildnone = all(sc.flagbuildnone for sc in self.subcons)

    def __getattr__(self, name):
        if name in self._subcons:
            return self._subcons[name]
        raise AttributeError

    def _parse(self, stream, context, path):
        obj = Container()
        obj._io = stream
        ctx = create_child_context(context, obj)
        ctx["_subcons"] = self._subcons
        for sc in self.subcons:
            try:
                subobj = sc._parsereport(stream, ctx, path)
                if sc.name:
                    obj[sc.name] = subobj
                    ctx[sc.name] = subobj

                # this adds the objects to the root of the context, if this struct is the root
                if context.get("_root", None) is None:
                    ctx["_root"].update(obj)
                    ctx["_root"].update(ctx)

            except StopFieldError:
                break

        return obj

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        extra_info = {}

        if obj is None:
            obj = Container()
        ctx = create_child_context(context, obj)

        for sc in self.subcons:
            subobj = obj.get(sc.name, None)

            if sc.name:
                ctx[sc.name] = subobj

            preprocessret, child_extra_info = sc._preprocess(subobj, ctx, path)
            # put named extra info to the context
            #extra = {f"_{sc.name}{k}": v for k, v in child_extra_info.items()}
            #extra_info.update(extra)

            if sc.name:
                ctx[sc.name] = preprocessret

            # add current extra_info to context, so e.g. lambdas can use them already
            #ctx.update(extra_info)
            ctx[f"_{sc.name}_meta"] = Container(child_extra_info)

        return ctx, extra_info

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        size = 0
        extra_info = {}
        if obj is None:
            obj = Container()
        ctx = create_child_context(context, obj)
        extra_info["_offset"] = offset
        for sc in self.subcons:
            subobj = obj.get(sc.name, None)

            if sc.name:
                ctx[sc.name] = subobj

            preprocessret, child_extra_info = sc._preprocess_size(subobj, ctx, path, offset=offset)
            # put named extra info to the context
            #extra = {f"_{sc.name}{k}": v for k, v in child_extra_info.items()}
            #extra_info.update(extra)

            # update offset & size
            retsize = child_extra_info["_size"]
            offset += retsize
            size += retsize
            if sc.name:
                ctx[sc.name] = preprocessret

            # add current extra_info to context, so e.g. lambdas can use them already
            ctx[f"_{sc.name}_meta"] = Container(child_extra_info)

        extra_info["_size"] = size
        extra_info["_endoffset"] = offset
        ctx.update(extra_info)

        return ctx, extra_info

    def _build(self, obj: Any, stream, context: Container, path: str) -> Container:
        if obj is None:
            obj = Container()

        ctx = create_child_context(context, obj)
        ctx["_subcons"] = self._subcons
        for sc in self.subcons:
            try:
                if sc.flagbuildnone:
                    subobj = obj.get(sc.name, None)
                else:
                    subobj = obj[sc.name] # raises KeyError

                if sc.name:
                    ctx[sc.name] = subobj

                buildret = sc._build(subobj, stream, ctx, path)
                if sc.name:
                    ctx[sc.name] = buildret
            except StopFieldError:
                break
        return ctx

    def _toET(self, parent, name, context, path):
        assert(name is not None)
        assert(parent is not None)

        # FIXME: replace this with create_child_context if possible
        ctx = create_child_context_2(context, name)

        elem = ET.Element(name)
        for sc in self.subcons:
            if sc.name is None or sc.name.startswith("_"):
                continue

            child = sc._toET(context=ctx, name=sc.name, parent=elem, path=f"{path} -> {name}")
            if child is not None:
                elem.append(child)

        return elem

    def _fromET(self, parent, name, context, path, is_root=False):
        # we go down one layer
        ctx = create_parent_context(context)

        # get the xml element
        if not is_root:
            elem = parent.findall(name)
            if len(elem) == 1:
                elem = elem[0]
        else:
            elem = parent

        assert(elem is not None)

        for sc in self.subcons:
            ctx = sc._fromET(context=ctx, parent=elem, name=sc.name, path=f"{path} -> {name}")

        # remove _, because rebuild will fail otherwise
        if "_" in ctx.keys():
            ctx.pop("_")

        # now we have to go back up
        ret_ctx = context
        insert_or_append_field(ret_ctx, name, ctx)

        return ret_ctx


class Sequence(Structconstruct):
    r"""
    Sequence of usually un-named constructs. The members are parsed and build in the order they are defined. If a member is named, its parsed value gets inserted into the context. This allows using members that refer to previous members.

    Operator >> can also be used to make Sequences (although not recommended).

    Parses into a ListContainer (list with pretty-printing) where values are in same order as subcons. Builds from a list (not necessarily a ListContainer) where each subcon is given the element at respective position. Size is the sum of all subcon sizes, unless any subcon raises SizeofError.

    This class does context nesting, meaning its members are given access to a new dictionary where the "_" entry points to the outer context. When parsing, each member gets parsed and subcon parse return value is inserted into context under matching key only if the member was named. When building, the matching entry gets inserted into context before subcon gets build, and if subcon build returns a new value (not None) that gets replaced in the context.

    This class exposes subcons as attributes. You can refer to subcons that were inlined (and therefore do not exist as variable in the namespace) by accessing the struct attributes, under same name. Also note that compiler does not support this feature. See examples.

    This class exposes subcons in the context. You can refer to subcons that were inlined (and therefore do not exist as variable in the namespace) within other inlined fields using the context. Note that you need to use a lambda (`this` expression is not supported). Also note that compiler does not support this feature. See examples.

    This class supports stopping. If :class:`~dingsda.core.StopIf` field is a member, and it evaluates its lambda as positive, this class ends parsing or building as successful without processing further fields.

    :param \*subcons: Construct instances, list of members, some can be named
    :param \*\*subconskw: Construct instances, list of members (requires Python 3.6)

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises KeyError: building a subcon but found no corresponding key in dictionary

    Example::

        >>> d = Sequence(Byte, Float32b)
        >>> d.build([0, 1.23])
        b'\x00?\x9dp\xa4'
        >>> d.parse(_)
        [0, 1.2300000190734863] # a ListContainer

        >>> d = Sequence(
        ...     "animal" / Enum(Byte, giraffe=1),
        ... )
        >>> d.animal.giraffe
        'giraffe'
        >>> d = Sequence(
        ...     "count" / Byte,
        ...     "data" / Bytes(lambda this: this.count - this._subcons.count.sizeof()),
        ... )
        >>> d.build([3, b"12"])
        b'\x0312'

        Alternative syntax, but requires Python 3.6 or any PyPy:
        >>> Sequence(a=Byte, b=Byte, c=Byte, d=Byte)
    """

    def __init__(self, *subcons, **subconskw):
        super().__init__()
        self.subcons = list(subcons) + list(k/v for k,v in subconskw.items())
        self._subcons = Container((sc.name,sc) for sc in self.subcons if sc.name)
        self.flagbuildnone = all(sc.flagbuildnone for sc in self.subcons)

    def __getattr__(self, name):
        if name in self._subcons:
            return self._subcons[name]
        raise AttributeError

    def _parse(self, stream, context, path):
        obj = ListContainer()
        context = Container(_ = context, _params = context._params, _root = None, _parsing = context._parsing, _building = context._building, _sizing = context._sizing, _subcons = self._subcons, _io = stream, _index = context.get("_index", None))
        context._root = context._.get("_root", context)
        for sc in self.subcons:
            try:
                subobj = sc._parsereport(stream, context, path)
                obj.append(subobj)
                if sc.name:
                    context[sc.name] = subobj
            except StopFieldError:
                break
        return obj

    def _build(self, obj, stream, context, path):
        if obj is None:
            obj = ListContainer([None for sc in self.subcons])
        context = Container(_ = context, _params = context._params, _root = None, _parsing = context._parsing, _building = context._building, _sizing = context._sizing, _subcons = self._subcons, _io = stream, _index = context.get("_index", None))
        context._root = context._.get("_root", context)
        objiter = iter(obj)
        retlist = ListContainer()
        for i,sc in enumerate(self.subcons):
            try:
                subobj = next(objiter)
                if sc.name:
                    context[sc.name] = subobj

                buildret = sc._build(subobj, stream, context, path)
                retlist.append(buildret)

                if sc.name:
                    context[sc.name] = buildret
            except StopFieldError:
                break
        return retlist

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        raise NotImplementedError

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        raise NotImplementedError


#===============================================================================
# arrays ranges and repeaters
#===============================================================================
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
        obj = ListContainer()
        for i in range(count):
            context._index = i
            e = self.subcon._parsereport(stream, context, path)
            if not discard:
                obj.append(e)
        return obj

    def _build(self, obj, stream, context, path):
        count = evaluate(self.count, context)
        if not 0 <= count:
            raise RangeError("invalid count %s" % (count,), path=path)
        if not len(obj) == count:
            raise RangeError("expected %d elements, found %d" % (count, len(obj)), path=path)
        discard = self.discard
        retlist = ListContainer()
        for i,e in enumerate(obj):
            context._index = i
            buildret = self.subcon._build(e, stream, context, path)
            if not discard:
                retlist.append(buildret)
        return retlist

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

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        # predicates don't need to be checked in preprocessing
        retlist = ListContainer()
        extra_info = {}
        for i,e in enumerate(obj):
            context._index = i
            obj, child_extra_info = self.subcon._preprocess(e, context, path)
            retlist.append(obj)

            extra = {f"_{i}{k}": v for k, v in child_extra_info.items()}
            extra_info.update(extra)
            context.update(extra_info)

        return retlist, extra_info

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        # predicates don't need to be checked in preprocessing
        retlist = ListContainer()
        extra_info = {"_offset": offset}
        size = 0
        for i,e in enumerate(obj):
            context._index = i
            obj, child_extra_info = self.subcon._preprocess_size(e, context, path, offset)
            retlist.append(obj)

            extra = {f"_{i}{k}": v for k, v in child_extra_info.items()}
            extra_info.update(extra)
            offset += child_extra_info["_size"]
            size += child_extra_info["_size"]

            context.update(extra_info)

        extra_info["_size"] = size
        extra_info["_endoffset"] = offset

        return retlist, extra_info

    def _parse(self, stream, context, path):
        discard = self.discard
        obj = ListContainer()
        try:
            for i in itertools.count():
                context._index = i
                fallback = stream_tell(stream, path)
                e = self.subcon._parsereport(stream, context, path)
                if not discard:
                    obj.append(e)
        except StopFieldError:
            pass
        except ExplicitError:
            raise
        except Exception:
            stream_seek(stream, fallback, 0, path)
        return obj

    def _build(self, obj, stream, context, path):
        discard = self.discard
        try:
            retlist = ListContainer()
            for i,e in enumerate(obj):
                context._index = i
                buildret = self.subcon._build(e, stream, context, path)
                if not discard:
                    retlist.append(buildret)
            return retlist
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
        obj = ListContainer()
        for i in itertools.count():
            context._index = i
            e = self.subcon._parsereport(stream, context, path)
            if not discard:
                obj.append(e)
            if predicate(e, obj, context):
                return obj

    def _build(self, obj, stream, context, path):
        predicate = self.predicate
        discard = self.discard
        if not callable(predicate):
            predicate = lambda _1,_2,_3: predicate
        partiallist = ListContainer()
        retlist = ListContainer()
        for i,e in enumerate(obj):
            context._index = i
            buildret = self.subcon._build(e, stream, context, path)
            if not discard:
                retlist.append(buildret)
                partiallist.append(buildret)
            if self.check_predicate and predicate(e, partiallist, context):
                break
        else:
            raise RepeatError("expected any item to match predicate, when building", path=path)
        return retlist

    def _names(self):
        sc_names = [self.name]
        sc_names += self.subcon._names()
        return sc_names

    def _static_sizeof(self, context: Container, path: str) -> int:
        raise SizeofError("cannot calculate size of RepeatUntil", path=path)


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
                "offset" / Rebuild(Int32ul, lambda ctx: ctx._._header2_endoffset),
                "size" / Rebuild(Int32ul, lambda ctx: ctx._data1_size),
                "data1" / Area(Int32ul, this.offset, this.size),
            ),
            "header2" / Struct(
                "offset" / Rebuild(Int32ul, lambda ctx: ctx._.header1.offset + ctx._.header1.size),
                "size" / Rebuild(Int32ul, lambda ctx: ctx._data2_size),
                "data2" / Area(Int8ul, this.offset, this.size),
            )
        )
    """

    def __init__(self, subcon, offset, size, stream=None, check_stream_pos=True):
        super().__init__(subcon)
        self.size = size
        self.offset = offset
        # if check_stream_pos is True, this is always == size or an error is raised when parsing
        # if check_stream_pos is False, this is the real size of the parsed data
        self.parsed_size = 0
        self.check_stream_pos = check_stream_pos
        self.stream = stream

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        retlist = ListContainer()
        # this is essentially a fancy pointer, so no size (instead we use _ptrsize)
        extra_info = {"_offset": offset, "_size": 0, "_endoffset": offset}
        ptrsize = 0
        for i, e in enumerate(obj):
            context._index = i
            obj, child_extra_info = self.subcon._preprocess_size(e, context, path, offset)
            retlist.append(obj)

            extra = {f"_ptr_{i}{k}": v for k, v in child_extra_info.items()}
            extra_info.update(extra)
            ptrsize += child_extra_info["_size"]

            #context.update(extra_info)

        extra_info["_ptrsize"] = ptrsize

        return retlist, extra_info

    def _parse(self, stream, context, path):
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

        stream_seek(stream, fallback, 0, path)
        return obj

    def _build(self, obj, stream, context, path):
        offset = evaluate(self.offset, context)
        size = evaluate(self.size, context)
        stream = evaluate(self.stream, context) or stream
        fallback = stream_tell(stream, path)

        stream_seek(stream, offset, 2 if offset < 0 else 0, path)
        retlist = ListContainer()
        for i,e in enumerate(obj):
            context._index = i
            buildret = self.subcon._build(e, stream, context, path)
            retlist.append(buildret)

        if self.check_stream_pos:
            assert(stream_tell(stream, path) == offset + size)
        else:
            assert(stream_tell(stream, path) <= offset + size)

        stream_seek(stream, fallback, 0, path)
        return retlist

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 0

#===============================================================================
# specials
#===============================================================================
class Renamed(Subconstruct):
    r"""
    Special wrapper that allows a Struct (or other similar class) to see a field as having a name (or a different name) or having a parsed hook. Library classes do not have names (its None). Renamed does not change a field, only wraps it like a candy with a label. Used internally by / and * operators.

    Also this wrapper is responsible for building a path info (a chain of names) that gets attached to error message when parsing, building, or sizeof fails. Fields that are not named do not appear in the path string.

    Parsing building and size are deferred to subcon.

    :param subcon: Construct instance
    :param newname: optional, string
    :param newdocs: optional, string
    :param newparsed: optional, lambda

    Example::

        >>> "number" / Int32ub
        <Renamed: number>
    """

    def __init__(self, subcon, newname=None, newdocs=None, newparsed=None):
        super().__init__(subcon)
        self.name = newname if newname else subcon.name
        self.docs = newdocs if newdocs else subcon.docs
        self.parsed = newparsed if newparsed else subcon.parsed

    def __getattr__(self, name):
        return getattr(self.subcon, name)

    def _parse(self, stream, context, path):
        path += " -> %s" % (self.name,)
        return self.subcon._parsereport(stream, context, path)

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        path += " -> %s" % (self.name,)
        return self.subcon._preprocess(obj, context, path)

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        path += " -> %s" % (self.name,)
        return self.subcon._preprocess_size(obj=obj, context=context, path=path, offset=offset)

    def _build(self, obj, stream, context, path):
        path += " -> %s" % (self.name,)
        return self.subcon._build(obj, stream, context, path)

    def _toET(self, parent, name, context, path):
        ctx = context

        # corner case with Switch e.g.
        if name != self.name:
            ctx = rename_in_context(context=context, name=name, new_name=self.name)

        return self.subcon._toET(context=ctx, name=self.name, parent=parent, path=f"{path} -> {name}")

    def _fromET(self, parent, name, context, path, is_root=False):
        ctx = context

        # this renaming is necessary e.g. for GenericList,
        # because it creates a list which needs to be renamed accordingly, so the following objects
        # can append themselves to the list
        if name != self.name and name in ctx.keys():
            ctx = rename_in_context(context=context, name=name, new_name=self.name)

        ctx = self.subcon._fromET(context=ctx, parent=parent, name=self.name, path=f"{path} -> {name}", is_root=is_root)

        if name != self.name:
            ctx = rename_in_context(context=ctx, name=self.name, new_name=name)

        #  requires when rebuilding, else key error is raised
        if not self.name in ctx.keys():
            ctx.pop(self.name, None)

        return ctx

    def _is_simple_type(self):
        return self.subcon._is_simple_type()

    def _is_array(self):
        return self.subcon._is_array()

    def _names(self):
        sc_names = [self.name]
        sc_names += self.subcon._names()
        return sc_names


#===============================================================================
# miscellaneous
#===============================================================================
class Const(Subconstruct):
    r"""
    Field enforcing a constant. It is used for file signatures, to validate that the given pattern exists. Data in the stream must strictly match the specified value.

    Note that a variable sized subcon may still provide positive verification. Const does not consume a precomputed amount of bytes, but depends on the subcon to read the appropriate amount (eg. VarInt is acceptable). Whatever subcon parses into, gets compared against the specified value.

    Parses using subcon and return its value (after checking). Builds using subcon from nothing (or given object, if not None). Size is the same as subcon, unless it raises SizeofError.

    :param value: expected value, usually a bytes literal
    :param subcon: optional, Construct instance, subcon used to build value from, assumed to be Bytes if value parameter was a bytes literal

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises ConstError: parsed data does not match specified value, or building from wrong value
    :raises StringError: building from non-bytes value, perhaps unicode

    Example::

        >>> d = Const(b"IHDR")
        >>> d.build(None)
        b'IHDR'
        >>> d.parse(b"JPEG")
        dingsda.core.ConstError: expected b'IHDR' but parsed b'JPEG'

        >>> d = Const(255, Int32ul)
        >>> d.build(None)
        b'\xff\x00\x00\x00'
    """

    def __init__(self, value, subcon=None):
        if subcon is None:
            if not isinstance(value, bytestringtype):
                raise StringError(f"given non-bytes value {repr(value)}, perhaps unicode?")
            subcon = Bytes(len(value))
        super().__init__(subcon)
        self.value = value
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        obj = self.subcon._parsereport(stream, context, path)
        if not obj == self.value:
            raise ConstError(f"parsing expected {repr(self.value)} but parsed {repr(obj)}", path=path)
        return obj

    def _build(self, obj, stream, context, path):
        if obj not in (None, self.value):
            raise ConstError(f"building expected None or {repr(self.value)} but got {repr(obj)}", path=path)
        return self.subcon._build(self.value, stream, context, path)

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context


Magic = Const


class Computed(Construct):
    r"""
    Field computing a value from the context dictionary or some outer source like os.urandom or random module. Underlying byte stream is unaffected. The source can be non-deterministic.

    Parsing and Building return the value returned by the context lambda (although a constant value can also be used). Size is defined as 0 because parsing and building does not consume or produce bytes into the stream.

    :param func: context lambda or constant value

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::
        >>> d = Struct(
        ...     "width" / Byte,
        ...     "height" / Byte,
        ...     "total" / Computed(this.width * this.height),
        ... )
        >>> d.build(dict(width=4,height=5))
        b'\x04\x05'
        >>> d.parse(b"12")
        Container(width=49, height=50, total=2450)

        >>> d = Computed(7)
        >>> d.parse(b"")
        7
        >>> d = Computed(lambda ctx: 7)
        >>> d.parse(b"")
        7

        >>> import os
        >>> d = Computed(lambda ctx: os.urandom(10))
        >>> d.parse(b"")
        b'\x98\xc2\xec\x10\x07\xf5\x8e\x98\xc2\xec'
    """

    def __init__(self, func):
        super().__init__()
        self.func = func
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        return evaluate(self.func, context)

    def _build(self, obj, stream, context, path):
        return evaluate(self.func, context)

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        return self.func, {}

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 0

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context


@singleton
class Index(Construct):
    r"""
    Indexes a field inside outer :class:`~dingsda.core.Array` :class:`~dingsda.core.GreedyRange` :class:`~dingsda.core.RepeatUntil` context.

    Note that you can use this class, or use `this._index` expression instead, depending on how its used. See the examples.

    Parsing and building pulls _index key from the context. Size is 0 because stream is unaffected.

    :raises IndexFieldError: did not find either key in context

    Example::

        >>> d = Array(3, Index)
        >>> d.parse(b"")
        [0, 1, 2]
        >>> d = Array(3, Struct("i" / Index))
        >>> d.parse(b"")
        [Container(i=0), Container(i=1), Container(i=2)]

        >>> d = Array(3, Computed(this._index+1))
        >>> d.parse(b"")
        [1, 2, 3]
        >>> d = Array(3, Struct("i" / Computed(this._._index+1)))
        >>> d.parse(b"")
        [Container(i=1), Container(i=2), Container(i=3)]
    """

    def __init__(self):
        super().__init__()
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        return context.get("_index", None)

    def _build(self, obj, stream, context, path):
        return context.get("_index", None)

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 0

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context


class Rebuild(Subconstruct):
    r"""
    Field where building does not require a value, because the value gets recomputed when needed. Comes handy when building a Struct from a dict with missing keys. Useful for length and count fields when :class:`~dingsda.core.Prefixed` and :class:`~dingsda.core.PrefixedArray` cannot be used.

    Parsing defers to subcon. Building is defered to subcon, but it builds from a value provided by the context lambda (or constant). Size is the same as subcon, unless it raises SizeofError.

    Difference between Default and Rebuild, is that in first the build value is optional and in second the build value is ignored.

    :param subcon: Construct instance
    :param func: context lambda or constant value

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Struct(
        ...     "count" / Rebuild(Byte, len_(this.items)),
        ...     "items" / Byte[this.count],
        ... )
        >>> d.build(dict(items=[1,2,3]))
        b'\x03\x01\x02\x03'
    """

    def __init__(self, subcon, func):
        super().__init__(subcon)
        self.func = func
        self.flagbuildnone = True

    def _build(self, obj, stream, context, path):
        obj = evaluate(self.func, context)
        return self.subcon._build(obj, stream, context, path)

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        return self.func, {}

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        try:
            size = self.subcon._static_sizeof(context, path)
            return self.func, {"_offset": offset, "_size": size, "_endoffset": offset + size}
        except SizeofError:
            pass
        ev_obj = evaluate(self.func, context)
        size = self.subcon.sizeof(ev_obj, context, path)
        return self.func, {"_offset": offset, "_size": size, "_endoffset": offset + size}

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context

    def _is_array(self) -> bool:
        return self.subcon._is_array()

    def _is_simple_type(self) -> bool:
        return self.subcon._is_simple_type()


class Default(Subconstruct):
    r"""
    Field where building does not require a value, because the value gets taken from default.
    Comes handy when building a Struct from a dict with missing keys.

    Parsing defers to subcon. Building is deferred to subcon, but it builds from a default (if given object is None) or
    from given object. Building does not require a value, but can accept one. Size is the same as subcon.

    Difference between Default and Rebuild, is that in first the build value is optional and in second the build value
    is ignored.

    :param subcon: Construct instance
    :param value: context lambda or constant value

    :raises StreamError: requested reading negative amount, could not read enough bytes,
    requested writing different amount than actual data, or could not write all bytes

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Struct(
        ...     "a" / Default(Byte, 0),
        ... )
        >>> d.build(dict(a=1))
        b'\x01'
        >>> d.build(dict())
        b'\x00'
    """

    def __init__(self, subcon, value):
        super().__init__(subcon)
        self.value = value
        self.flagbuildnone = True

    def _build(self, obj, stream, context, path):
        obj = evaluate(self.value, context) if obj is None else obj
        return self.subcon._build(obj, stream, context, path)

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context


class Check(Construct):
    r"""
    Checks for a condition, and raises CheckError if the check fails.

    Parsing and building return nothing (but check the condition). Size is 0 because stream is unaffected.

    :param func: bool or context lambda, that gets run on parsing and building

    :raises CheckError: lambda returned false

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        Check(lambda ctx: len(ctx.payload.data) == ctx.payload_len)
        Check(len_(this.payload.data) == this.payload_len)
    """

    def __init__(self, func):
        super().__init__()
        self.func = func
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        passed = evaluate(self.func, context)
        if not passed:
            raise CheckError("check failed during parsing", path=path)

    def _build(self, obj, stream, context, path):
        passed = evaluate(self.func, context)
        if not passed:
            raise CheckError("check failed during building", path=path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 0

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context


@singleton
class Error(Construct):
    r"""
    Raises ExplicitError, unconditionally.

    Parsing and building always raise ExplicitError. Size is undefined.

    :raises ExplicitError: unconditionally, on parsing and building

    Example::

        >>> d = Struct("num"/Byte, Error)
        >>> d.parse(b"data...")
        dingsda.core.ExplicitError: Error field was activated during parsing
    """

    def __init__(self):
        super().__init__()
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        raise ExplicitError("Error field was activated during parsing", path=path)

    def _build(self, obj, stream, context, path):
        raise ExplicitError("Error field was activated during building", path=path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        raise SizeofError("Error does not have size, because it interrupts parsing and building", path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        raise SizeofError("Error does not have size, because it interrupts parsing and building", path=path)


class FocusedSeq(Construct):
    r"""
    Allows constructing more elaborate "adapters" than Adapter class.

    Parse does parse all subcons in sequence, but returns only the element that was selected (discards other values). Build does build all subcons in sequence, where each gets build from nothing (except the selected subcon which is given the object). Size is the sum of all subcon sizes, unless any subcon raises SizeofError.

    This class does context nesting, meaning its members are given access to a new dictionary where the "_" entry points to the outer context. When parsing, each member gets parsed and subcon parse return value is inserted into context under matching key only if the member was named. When building, the matching entry gets inserted into context before subcon gets build, and if subcon build returns a new value (not None) that gets replaced in the context.

    This class exposes subcons as attributes. You can refer to subcons that were inlined (and therefore do not exist as variable in the namespace) by accessing the struct attributes, under same name. Also note that compiler does not support this feature. See examples.

    This class exposes subcons in the context. You can refer to subcons that were inlined (and therefore do not exist as variable in the namespace) within other inlined fields using the context. Note that you need to use a lambda (`this` expression is not supported). Also note that compiler does not support this feature. See examples.

    This class is used internally to implement :class:`~dingsda.core.PrefixedArray`.

    :param parsebuildfrom: string name or context lambda, selects a subcon
    :param \*subcons: Construct instances, list of members, some can be named
    :param \*\*subconskw: Construct instances, list of members (requires Python 3.6)

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises UnboundLocalError: selector does not match any subcon

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Excample::

        >>> d = FocusedSeq("num", Const(b"SIG"), "num"/Byte, Terminated)
        >>> d.parse(b"SIG\xff")
        255
        >>> d.build(255)
        b'SIG\xff'

        >>> d = FocusedSeq("animal",
        ...     "animal" / Enum(Byte, giraffe=1),
        ... )
        >>> d.animal.giraffe
        'giraffe'
        >>> d = FocusedSeq("count",
        ...     "count" / Byte,
        ...     "data" / Padding(lambda this: this.count - this._subcons.count.sizeof()),
        ... )
        >>> d.build(4)
        b'\x04\x00\x00\x00'

        PrefixedArray <--> FocusedSeq("items",
            "count" / Rebuild(lengthfield, len_(this.items)),
            "items" / subcon[this.count],
        )
    """

    def __init__(self, parsebuildfrom, *subcons, **subconskw):
        super().__init__()
        self.parsebuildfrom = parsebuildfrom
        self.subcons = list(subcons) + list(k/v for k,v in subconskw.items())
        self._subcons = Container((sc.name,sc) for sc in self.subcons if sc.name)

    def __getattr__(self, name):
        if name in self._subcons:
            return self._subcons[name]
        raise AttributeError

    def _parse(self, stream, context, path):
        context = Container(_ = context, _params = context._params, _root = None, _parsing = context._parsing, _building = context._building, _sizing = context._sizing, _subcons = self._subcons, _io = stream, _index = context.get("_index", None))
        context._root = context._.get("_root", context)
        parsebuildfrom = evaluate(self.parsebuildfrom, context)
        for i,sc in enumerate(self.subcons):
            parseret = sc._parsereport(stream, context, path)
            if sc.name:
                context[sc.name] = parseret
            if sc.name == parsebuildfrom:
                finalret = parseret
        return finalret

    def _build(self, obj, stream, context, path):
        context = Container(_ = context, _params = context._params, _root = None, _parsing = context._parsing, _building = context._building, _sizing = context._sizing, _subcons = self._subcons, _io = stream, _index = context.get("_index", None))
        context._root = context._.get("_root", context)
        parsebuildfrom = evaluate(self.parsebuildfrom, context)
        context[parsebuildfrom] = obj
        for i,sc in enumerate(self.subcons):
            buildret = sc._build(obj if sc.name == parsebuildfrom else None, stream, context, path)
            if sc.name:
                context[sc.name] = buildret
            if sc.name == parsebuildfrom:
                finalret = buildret
        return finalret

    def _toET(self, parent, name, context, path):
        assert (isinstance(self.parsebuildfrom, str))
        for sc in self.subcons:
            if sc.name == self.parsebuildfrom:
                # FocusedSeq has to ignore the Rename
                # because e.g. PrefixedArray adds custom names
                if sc.__class__.__name__ == "Renamed":
                    sc = sc.subcon
                else:
                    raise NotImplementedError
                elem = sc._toET(parent, name, context, path)

                return elem

        raise NotImplementedError

    def _fromET(self, parent, name, context, path, is_root=False):
        parse_sc = None
        for sc in self.subcons:
            if sc.name == self.parsebuildfrom:
                parse_sc = sc
                # Necessary to find the sc in the parent
                assert (sc.__class__.__name__ == "Renamed")
        assert(parse_sc is not None)

        # get the xml element
        if not is_root and not parse_sc._is_array():
            elem = parent.findall(name)
            # at this point, we should have only one element
            if len(elem) == 1:
                elem = elem[0]
            else:
                assert(False)
        else:
            elem = parent

        assert(elem is not None)

        return parse_sc._fromET(context=context, parent=elem, name=name, path=f"{path} -> {name}", is_root=True)

        assert(False)

    def _get_main_sc(self):
        sc = None
        for s in self.subcons:
            if s.name == self.parsebuildfrom:
                sc = s
                break
        assert(sc is not None)
        return sc

    def _static_sizeof(self, context: Container, path: str) -> int:
        try:
            return sum(sc._static_sizeof(context, path) for sc in self.subcons)
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        # FIXME: this should be incorporated in an extra _sizeof, which is called before by sizeof(), which first tries to call _static_sizeof
        try:
            return self._static_sizeof(context, path)
        except SizeofError:
            pass
        try:
            size_sum = 0
            for sc in self.subcons:
                if sc.name == self.parsebuildfrom:
                    size_sum += sc._sizeof(obj, context, path)
                else:
                    size_sum += sc._static_sizeof(context, path)

            return size_sum
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)
        assert(0)

    def _names(self):
        return self._get_main_sc()._names()

    def _is_simple_type(self):
        return self._get_main_sc()._is_simple_type()

    def _is_array(self):
        return self._get_main_sc()._is_array()


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

    def _parse(self, stream, context, path):
        import numpy
        return numpy.load(stream)

    def _build(self, obj, stream, context, path):
        import numpy
        numpy.save(stream, obj)
        return obj


class NamedTuple(Adapter):
    r"""
    Both arrays, structs, and sequences can be mapped to a namedtuple from `collections module <https://docs.python.org/3/library/collections.html#collections.namedtuple>`_. To create a named tuple, you need to provide a name and a sequence of fields, either a string with space-separated names or a list of string names, like the standard namedtuple.

    Parses into a collections.namedtuple instance, and builds from such instance (although it also builds from lists and dicts). Size is undefined.

    :param tuplename: string
    :param tuplefields: string or list of strings
    :param subcon: Construct instance, either Struct Sequence Array GreedyRange

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises NamedTupleError: subcon is neither Struct Sequence Array GreedyRange

    Can propagate collections exceptions.

    Example::

        >>> d = NamedTuple("coord", "x y z", Byte[3])
        >>> d = NamedTuple("coord", "x y z", Byte >> Byte >> Byte)
        >>> d = NamedTuple("coord", "x y z", "x"/Byte + "y"/Byte + "z"/Byte)
        >>> d.parse(b"123")
        coord(x=49, y=50, z=51)
    """

    def __init__(self, tuplename, tuplefields, subcon):
        if not isinstance(subcon, (Struct,Sequence,Array,GreedyRange)):
            raise NamedTupleError("subcon is neither Struct Sequence Array GreedyRange")
        super().__init__(subcon)
        self.tuplename = tuplename
        self.tuplefields = tuplefields
        self.factory = collections.namedtuple(tuplename, tuplefields)

    def _decode(self, obj, context, path):
        if isinstance(self.subcon, Struct):
            del obj["_io"]
            return self.factory(**obj)
        if isinstance(self.subcon, (Sequence,Array,GreedyRange)):
            return self.factory(*obj)
        raise NamedTupleError("subcon is neither Struct Sequence Array GreedyRangeGreedyRange", path=path)

    def _encode(self, obj, context, path):
        if isinstance(self.subcon, Struct):
            return Container({sc.name:getattr(obj,sc.name) for sc in self.subcon.subcons if sc.name})
        if isinstance(self.subcon, (Sequence,Array,GreedyRange)):
            return list(obj)
        raise NamedTupleError("subcon is neither Struct Sequence Array GreedyRange", path=path)


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


#===============================================================================
# conditional
#===============================================================================
class Union(Construct):
    r"""
    Treats the same data as multiple constructs (similar to C union) so you can look at the data in multiple views. Fields are usually named (so parsed values are inserted into dictionary under same name).

    Parses subcons in sequence, and reverts the stream back to original position after each subcon. Afterwards, advances the stream by selected subcon. Builds from first subcon that has a matching key in given dict. Size is undefined (because parsefrom is not used for building).

    This class does context nesting, meaning its members are given access to a new dictionary where the "_" entry points to the outer context. When parsing, each member gets parsed and subcon parse return value is inserted into context under matching key only if the member was named. When building, the matching entry gets inserted into context before subcon gets build, and if subcon build returns a new value (not None) that gets replaced in the context.

    This class exposes subcons as attributes. You can refer to subcons that were inlined (and therefore do not exist as variable in the namespace) by accessing the struct attributes, under same name. Also note that compiler does not support this feature. See examples.

    This class exposes subcons in the context. You can refer to subcons that were inlined (and therefore do not exist as variable in the namespace) within other inlined fields using the context. Note that you need to use a lambda (`this` expression is not supported). Also note that compiler does not support this feature. See examples.

    .. warning:: If you skip `parsefrom` parameter then stream will be left back at starting offset, not seeked to any common denominator.

    :param parsefrom: how to leave stream after parsing, can be integer index or string name selecting a subcon, or None (leaves stream at initial offset, the default), or context lambda
    :param \*subcons: Construct instances, list of members, some can be anonymous
    :param \*\*subconskw: Construct instances, list of members (requires Python 3.6)

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises StreamError: stream is not seekable and tellable
    :raises UnionError: selector does not match any subcon, or dict given to build does not contain any keys matching any subcon
    :raises IndexError: selector does not match any subcon
    :raises KeyError: selector does not match any subcon

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Union(0, 
        ...     "raw" / Bytes(8),
        ...     "ints" / Int32ub[2],
        ...     "shorts" / Int16ub[4],
        ...     "chars" / Byte[8],
        ... )
        >>> d.parse(b"12345678")
        Container(raw=b'12345678', ints=[825373492, 892745528], shorts=[12594, 13108, 13622, 14136], chars=[49, 50, 51, 52, 53, 54, 55, 56])
        >>> d.build(dict(chars=range(8)))
        b'\x00\x01\x02\x03\x04\x05\x06\x07'

        >>> d = Union(None,
        ...     "animal" / Enum(Byte, giraffe=1),
        ... )
        >>> d.animal.giraffe
        'giraffe'
        >>> d = Union(None,
        ...     "chars" / Byte[4],
        ...     "data" / Bytes(lambda this: this._subcons.chars.sizeof()),
        ... )
        >>> d.parse(b"\x01\x02\x03\x04")
        Container(chars=[1, 2, 3, 4], data=b'\x01\x02\x03\x04')

        Alternative syntax, but requires Python 3.6 or any PyPy:
        >>> Union(0, raw=Bytes(8), ints=Int32ub[2], shorts=Int16ub[4], chars=Byte[8])
    """

    def __init__(self, parsefrom, *subcons, **subconskw):
        if isinstance(parsefrom, Construct):
            raise UnionError("parsefrom should be either: None int str context-function")
        super().__init__()
        self.parsefrom = parsefrom
        self.subcons = list(subcons) + list(k/v for k,v in subconskw.items())
        self._subcons = Container((sc.name,sc) for sc in self.subcons if sc.name)

    def __getattr__(self, name):
        if name in self._subcons:
            return self._subcons[name]
        raise AttributeError

    def _parse(self, stream, context, path):
        obj = Container()
        context = Container(_ = context, _params = context._params, _root = None, _parsing = context._parsing, _building = context._building, _sizing = context._sizing, _subcons = self._subcons, _io = stream, _index = context.get("_index", None))
        context._root = context._.get("_root", context)
        fallback = stream_tell(stream, path)
        forwards = {}
        for i,sc in enumerate(self.subcons):
            subobj = sc._parsereport(stream, context, path)
            if sc.name:
                obj[sc.name] = subobj
                context[sc.name] = subobj
            forwards[i] = stream_tell(stream, path)
            if sc.name:
                forwards[sc.name] = stream_tell(stream, path)
            stream_seek(stream, fallback, 0, path)
        parsefrom = evaluate(self.parsefrom, context)
        if parsefrom is not None:
            stream_seek(stream, forwards[parsefrom], 0, path) # raises KeyError
        return obj

    def _build(self, obj, stream, context, path):
        context = Container(_ = context, _params = context._params, _root = None, _parsing = context._parsing, _building = context._building, _sizing = context._sizing, _subcons = self._subcons, _io = stream, _index = context.get("_index", None))
        context._root = context._.get("_root", context)
        context.update(obj)
        for sc in self.subcons:
            if sc.flagbuildnone:
                subobj = obj.get(sc.name, None)
            elif sc.name in obj:
                subobj = obj[sc.name]
            else:
                continue

            if sc.name:
                context[sc.name] = subobj

            buildret = sc._build(subobj, stream, context, path)
            if sc.name:
                context[sc.name] = buildret
            return Container({sc.name:buildret})
        else:
            raise UnionError("cannot build, none of subcons were found in the dictionary %r" % (obj,), path=path)

    def _static_sizeof(self, context, path):
        raise SizeofError("Union builds depending on actual object dict, size is unknown", path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        raise SizeofError(path=path)


class Select(Construct):
    r"""
    Selects the first matching subconstruct.

    Parses and builds by literally trying each subcon in sequence until one of them parses or builds without exception. Stream gets reverted back to original position after each failed attempt, but not if parsing succeeds. Size is not defined.

    :param \*subcons: Construct instances, list of members, some can be anonymous
    :param \*\*subconskw: Construct instances, list of members (requires Python 3.6)

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises StreamError: stream is not seekable and tellable
    :raises SelectError: neither subcon succeded when parsing or building

    Example::

        >>> d = Select(Int32ub, CString("utf8"))
        >>> d.build(1)
        b'\x00\x00\x00\x01'
        >>> d.build(u"Афон")
        b'\xd0\x90\xd1\x84\xd0\xbe\xd0\xbd\x00'

        Alternative syntax, but requires Python 3.6 or any PyPy:
        >>> Select(num=Int32ub, text=CString("utf8"))
    """

    def __init__(self, *subcons, **subconskw):
        super().__init__()
        self.subcons = list(subcons) + list(k/v for k,v in subconskw.items())
        self.flagbuildnone = any(sc.flagbuildnone for sc in self.subcons)

    def _parse(self, stream, context, path):
        for sc in self.subcons:
            fallback = stream_tell(stream, path)
            try:
                obj = sc._parsereport(stream, context, path)
            except ExplicitError:
                raise
            except Exception:
                stream_seek(stream, fallback, 0, path)
            else:
                return obj
        raise SelectError("no subconstruct matched", path=path)

    def _build(self, obj, stream, context, path):
        for sc in self.subcons:
            try:
                data = sc.build(obj, **context)
            except ExplicitError:
                raise
            except Exception:
                pass
            else:
                stream_write(stream, data, len(data), path)
                return obj
        raise SelectError("no subconstruct matched: %s" % (obj,), path=path)


def TryParse(subcon):
    r"""
    Makes an optional field.

    Parsing attempts to parse subcon. If sub-parsing fails, returns None and reports success. Building attempts to build subcon. If sub-building fails, writes nothing and reports success. Size is undefined, because whether bytes would be consumed or produced depends on actual data and actual context.

    :param subcon: Construct instance

    Example::

        TryParse  <-->  Select(subcon, Pass)

        >>> d = TryParse(Int64ul)
        >>> d.parse(b"12345678")
        4050765991979987505
        >>> d.parse(b"")
        None
        >>> d.build(1)
        b'\x01\x00\x00\x00\x00\x00\x00\x00'
        >>> d.build(None)
        b''
    """
    return Select(subcon, Pass)


def If(condfunc, subcon):
    r"""
    If-then conditional construct.

    Parsing evaluates condition, if True then subcon is parsed, otherwise just returns None. Building also evaluates condition, if True then subcon gets build from, otherwise does nothing. Size is either same as subcon or 0, depending how condfunc evaluates.

    :param condfunc: bool or context lambda (or a truthy value)
    :param subcon: Construct instance, used if condition indicates True

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        If <--> IfThenElse(condfunc, subcon, Pass)

        >>> d = If(this.x > 0, Byte)
        >>> d.build(255, x=1)
        b'\xff'
        >>> d.build(255, x=0)
        b''
    """
    macro = IfThenElse(condfunc, subcon, Pass)

    return macro


class IfThenElse(Construct):
    r"""
    If-then-else conditional construct, similar to ternary operator.

    Parsing and building evaluates condition, and defers to either subcon depending on the value. Size is computed the same way.

    The XML builder/parser uses the XML tag name for determining the branch. Both branches need to be different Renamed
    constructs to work properly. (Pass needs not to be named.)

    :param condfunc: bool or context lambda (or a truthy value)
    :param thensubcon: Construct instance, used if condition indicates True
    :param elsesubcon: Construct instance, used if condition indicates False
    :param rebuild_hack: if True, when using fromET the xml tag name is used to determine the subcon, instead
    of evaluating the condition. This is a hack to support cases, where the value is not know while parsing the xml.
    If using the hack, only Renamed subcons are allowed as thensubcon and elsesubcon. Exception: If either
    thensubcon or elsesubcon are Pass, any subcon is allowed - it assumes that it was Passed, when the value is not
    found in the XML.

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = IfThenElse(this.x > 0, VarInt, Byte)
        >>> d.build(255, dict(x=1))
        b'\xff\x01'
        >>> d.build(255, dict(x=0))
        b'\xff'
    """

    def __init__(self, condfunc, thensubcon, elsesubcon, rebuild_hack = False):
        super().__init__()
        self.condfunc = condfunc
        self.thensubcon = thensubcon
        self.elsesubcon = elsesubcon
        self.flagbuildnone = thensubcon.flagbuildnone and elsesubcon.flagbuildnone
        self.rebuild_hack = rebuild_hack

    def _parse(self, stream, context, path):
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon
        return sc._parsereport(stream, context, path)

    def _build(self, obj, stream, context, path):
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon
        return sc._build(obj, stream, context, path)

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon
        return sc._preprocess(obj, context, path)

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon
        return sc._preprocess_size(obj, context, path, offset)

    def _static_sizeof(self, context: Container, path: str) -> int:
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon
        return sc._static_sizeof(context, path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon
        return sc._sizeof(obj, context, path)

    def _toET(self, parent, name, context, path):
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon

        return sc._toET(parent, name, context, path)

    def _fromET(self, parent, name, context, path, is_root=False):
        elems = []

        if self.rebuild_hack:
            # this hack is necessary, because at this point in parsing we don't know which branch to take
            # and can't infer it using the condition, because it might be a context lambda from Rebuild using
            # information not parsed yet
            sc_list = []
            if isinstance(self.thensubcon, type(Pass)):
                sc_list = [self.elsesubcon]
            elif isinstance(self.elsesubcon, type(Pass)):
                sc_list = [self.thensubcon]
            else:
                assert(isinstance(self.elsesubcon, Renamed))
                assert(isinstance(self.thensubcon, Renamed))
                sc_list = [self.thensubcon, self.elsesubcon]
            assert(len(sc_list) in [1,2])
            for sc in sc_list:
                if not sc._is_simple_type():
                    n = sc.name if isinstance(sc, Renamed) else name
                    elems = parent.findall(n)
                else:
                    names = sc._names()
                    if len(names) == 0:
                        elems = [parent]
                    else:
                        for n in names:
                            if parent.attrib.get(n, None) is not None:
                                elems = [parent]
                                break

                # no elements found => Pass
                if len(elems) == 0:
                    continue

                assert(len(elems) == 1)
                elem = elems[0]
                return sc._fromET(elem, name, context, path, is_root=True)

            # means: one pass is in there, but no element was found
            # if len(sc_list == 2) -> no element was found, although at least one should have been
            # Pass does nothing -> return the context
            assert(len(sc_list) == 1)
            return context
        else:
            # without the hack, we can just evaluate the condfunc with the current context
            condfunc = evaluate(self.condfunc, context)
            sc = self.thensubcon if condfunc else self.elsesubcon
            return sc._fromET(parent, name, context, path)

    def _names(self):
        return self.thensubcon._names() + self.elsesubcon._names()


class Switch(Construct):
    r"""
    A conditional branch.

    Parsing and building evaluate keyfunc and select a subcon based on the value and dictionary entries. Dictionary (cases) maps values into subcons. If no case matches then `default` is used (that is Pass by default). Note that `default` is a Construct instance, not a dictionary key. Size is evaluated in same way as parsing and building, by evaluating keyfunc and selecting a field accordingly.

    The XML tag names are used for identifying the cases. It breaks, when these names are used on the same level in the XML tree, or when you try to create an array of switches.
    Do not nest switches, add Struct() layers in between, so the names can be resolved properly.

    :param keyfunc: context lambda or constant, that matches some key in cases
    :param cases: dict mapping keys to Construct instances
    :param default: optional, Construct instance, used when keyfunc is not found in cases, Pass is default value for this parameter, Error is a possible value for this parameter

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Switch(this.n, { 1:Int8ub, 2:Int16ub, 4:Int32ub })
        >>> d.build(5, n=1)
        b'\x05'
        >>> d.build(5, n=4)
        b'\x00\x00\x00\x05'

        >>> d = Switch(this.n, {}, default=Byte)
        >>> d.parse(b"\x01", n=255)
        1
        >>> d.build(1, n=255)
        b"\x01"
    """

    def __init__(self, keyfunc, cases, default=None):
        if default is None:
            default = Pass
        super().__init__()
        self.keyfunc = keyfunc
        self.cases = cases
        self.default = default
        allcases = list(cases.values()) + [default]
        self.flagbuildnone = all(sc.flagbuildnone for sc in allcases)

    def _parse(self, stream, context, path):
        keyfunc = evaluate(self.keyfunc, context)
        sc = self.cases.get(keyfunc, self.default)
        return sc._parsereport(stream, context, path)

    def _build(self, obj, stream, context, path):
        keyfunc = evaluate(self.keyfunc, context)
        sc = self.cases.get(keyfunc, self.default)
        return sc._build(obj, stream, context, path)

    def _preprocess(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        keyfunc = evaluate(self.keyfunc, context, recurse=True)
        sc = self.cases[keyfunc]

        extra_info = {}

        obj, child_extra_info = sc._preprocess(obj, context, path)

        extra = {f"_{sc.name}{k}": v for k, v in child_extra_info.items()}
        extra_info.update(extra)

        return obj, extra_info

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Dict[str, Any]]:
        keyfunc = evaluate(self.keyfunc, context, recurse=True)
        sc = self.cases[keyfunc]

        extra_info = {"_offset": offset}

        obj, child_extra_info = sc._preprocess_size(obj=obj, context=context, path=path, offset=offset)

        extra = {f"_{sc.name}{k}": v for k, v in child_extra_info.items()}
        extra_info.update(extra)

        extra_info["_size"] = child_extra_info["_size"]
        extra_info["_endoffset"] = offset + child_extra_info["_size"]

        return obj, extra_info

    def _static_sizeof(self, context: Container, path: str) -> int:
        raise SizeofError("Switches cannot calculate static size", path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        try:
            keyfunc = evaluate(self.keyfunc, context)
            sc = self.cases.get(keyfunc, self.default)
            return sc._sizeof(obj, context, path)

        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    def _toET(self, parent, name, context, path):
        ctx = context
        keyfunc = None
        idx = context.get("_index", None)
        if idx is not None:
            ctx = context[f"{name}_{idx}"]

        keyfunc = evaluate(self.keyfunc, ctx)
        sc = self.cases.get(keyfunc, self.default)

        assert(isinstance(sc, Renamed))

        return sc._toET(parent, name, ctx, path)

    def _fromET(self, parent, name, context, path, is_root=False):
        for i, case in self.cases.items():
            assert(isinstance(case, Renamed))
            if not is_root:
                elems = parent.findall(case.name)
            else:
                elems = [parent]

            if len(elems) == 0:
                continue

            if not case._is_array():
                assert(len(elems) == 1)
            else:
                elems = [parent]
            elem = elems[0]
            context[f"_switch_id_{name}"] = i
            context[f"_switch_name_{name}"] = case.name

            return case._fromET(elem, name, context, path, is_root=True)

    def _names(self):
        for case in self.cases.values():
            assert(isinstance(case, Renamed))
        names = [case.name for case in self.cases.values()]
        return names


class StopIf(Construct):
    r"""
    Checks for a condition, and stops certain classes (:class:`~dingsda.core.Struct` :class:`~dingsda.core.Sequence` :class:`~dingsda.core.GreedyRange`) from parsing or building further.

    Parsing and building check the condition, and raise StopFieldError if indicated. Size is undefined.

    :param condfunc: bool or context lambda (or truthy value)

    :raises StopFieldError: used internally

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> Struct('x'/Byte, StopIf(this.x == 0), 'y'/Byte)
        >>> Sequence('x'/Byte, StopIf(this.x == 0), 'y'/Byte)
        >>> GreedyRange(FocusedSeq(0, 'x'/Byte, StopIf(this.x == 0)))
    """

    def __init__(self, condfunc):
        super().__init__()
        self.condfunc = condfunc
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        condfunc = evaluate(self.condfunc, context)
        if condfunc:
            raise StopFieldError(path=path)

    def _build(self, obj, stream, context, path):
        condfunc = evaluate(self.condfunc, context)
        if condfunc:
            raise StopFieldError(path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        raise SizeofError("StopIf cannot determine size because it depends on actual context which then depends on actual data and outer constructs", path=path)


#===============================================================================
# alignment and padding
#===============================================================================
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


def AlignedStruct(modulus, *subcons, **subconskw):
    r"""
    Makes a structure where each field is aligned to the same modulus (it is a struct of aligned fields, NOT an aligned struct).

    See :class:`~dingsda.core.Aligned` and :class:`~dingsda.core.Struct` for semantics and raisable exceptions.

    :param modulus: integer or context lambda, passed to each member
    :param \*subcons: Construct instances, list of members, some can be anonymous
    :param \*\*subconskw: Construct instances, list of members (requires Python 3.6)

    Example::

        >>> d = AlignedStruct(4, "a"/Int8ub, "b"/Int16ub)
        >>> d.build(dict(a=0xFF,b=0xFFFF))
        b'\xff\x00\x00\x00\xff\xff\x00\x00'
    """
    subcons = list(subcons) + list(k/v for k,v in subconskw.items())
    return Struct(*[sc.name / Aligned(modulus, sc) for sc in subcons])


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


#===============================================================================
# stream manipulation
#===============================================================================
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

        extra_info = {f"_ptr{k}": v for k, v in child_extra_info.items()}
        extra_info["_offset"] = offset
        extra_info["_size"] = 0
        extra_info["_endoffset"] = offset

        return obj, extra_info

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


    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return 0


class Peek(Subconstruct):
    r"""
    Peeks at the stream.

    Parsing sub-parses (and returns None if failed), then reverts stream to original position. Building does nothing (its NOT deferred). Size is defined as 0 because there is no building.

    This class is used in :class:`~dingsda.core.Union` class to parse each member.

    :param subcon: Construct instance

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises StreamError: stream is not seekable and tellable

    Example::

        >>> d = Sequence(Peek(Int8ub), Peek(Int16ub))
        >>> d.parse(b"\x01\x02")
        [1, 258]
        >>> d.sizeof()
        0
    """

    def __init__(self, subcon):
        super().__init__(subcon)
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        fallback = stream_tell(stream, path)
        try:
            return self.subcon._parsereport(stream, context, path)
        except ExplicitError:
            raise
        except ConstructError:
            pass
        finally:
            stream_seek(stream, fallback, 0, path)

    def _build(self, obj, stream, context, path):
        return obj

    def _static_sizeof(self, context, path):
        return 0


class OffsettedEnd(Subconstruct):
    r"""
    Parses all bytes in the stream till `EOF plus a negative endoffset` is reached.

    This is useful when GreedyBytes (or any other greedy construct) is followed by a fixed-size footer.

    Parsing determines the length of the stream and reads all bytes till EOF plus `endoffset` is reached,
    then defers to subcon using new BytesIO with said bytes. Building defers to subcon as-is. Size is undefined.

    :param endoffset: integer or context lambda, only negative offsets or zero are allowed
    :param subcon: Construct instance

    :raises StreamError: could not read enough bytes
    :raises StreamError: reads behind the stream (if endoffset is positive)

    Example::

        >>> d = Struct(
        ...     "header" / Bytes(2),
        ...     "data" / OffsettedEnd(-2, GreedyBytes),
        ...     "footer" / Bytes(2),
        ... )
        >>> d.parse(b"\x01\x02\x03\x04\x05\x06\x07")
        Container(header=b'\x01\x02', data=b'\x03\x04\x05', footer=b'\x06\x07')
    """

    def __init__(self, endoffset, subcon):
        super().__init__(subcon)
        self.endoffset = endoffset

    def _parse(self, stream, context, path):
        endoffset = evaluate(self.endoffset, context)
        curpos = stream_tell(stream, path)
        stream_seek(stream, 0, 2, path)
        endpos = stream_tell(stream, path)
        stream_seek(stream, curpos, 0, path)
        length = endpos + endoffset - curpos
        data = stream_read(stream, length, path)
        return self.subcon._parsereport(io.BytesIO(data), context, path)

    def _build(self, obj, stream, context, path):
        return self.subcon._build(obj, stream, context, path)

    def _static_sizeof(self, context, path):
        raise SizeofError(path=path)


class Seek(Construct):
    r"""
    Seeks the stream.

    Parsing and building seek the stream to given location (and whence), and return stream.seek() return value. Size is not defined.

    .. seealso:: Analog :class:`~dingsda.core.Pointer` wrapper that has same side effect but also processes a subcon, and also seeks back.

    :param at: integer or context lambda, where to jump to
    :param whence: optional, integer or context lambda, is the offset from beginning (0) or from current position (1) or from EOF (2), default is 0

    :raises StreamError: stream is not seekable

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = (Seek(5) >> Byte)
        >>> d.parse(b"01234x")
        [5, 120]

        >>> d = (Bytes(10) >> Seek(5) >> Byte)
        >>> d.build([b"0123456789", None, 255])
        b'01234\xff6789'
    """

    def __init__(self, at, whence=0):
        super().__init__()
        self.at = at
        self.whence = whence
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        at = evaluate(self.at, context)
        whence = evaluate(self.whence, context)
        return stream_seek(stream, at, whence, path)

    def _build(self, obj, stream, context, path):
        at = evaluate(self.at, context)
        whence = evaluate(self.whence, context)
        return stream_seek(stream, at, whence, path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        raise SizeofError("Seek only moves the stream, size is not meaningful", path=path)

@singleton
class Tell(Construct):
    r"""
    Tells the stream.

    Parsing and building return current stream offset using using stream.tell(). Size is defined as 0 because parsing and building does not consume or add into the stream.

    Tell is useful for adjusting relative offsets to absolute positions, or to measure sizes of Constructs. To get an absolute pointer, use a Tell plus a relative offset. To get a size, place two Tells and measure their difference using a Compute field. However, its recommended to use :class:`~dingsda.core.RawCopy` instead of manually extracting two positions and computing difference.

    :raises StreamError: stream is not tellable

    Example::

        >>> d = Struct("num"/VarInt, "offset"/Tell)
        >>> d.parse(b"X")
        Container(num=88, offset=1)
        >>> d.build(dict(num=88))
        b'X'
    """

    def __init__(self):
        super().__init__()
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        return stream_tell(stream, path)

    def _build(self, obj, stream, context, path):
        return stream_tell(stream, path)

    def _static_sizeof(self, context, path):
        return 0

@singleton
class Pass(Construct):
    r"""
    No-op construct, useful as default cases for Switch and Enum.

    Parsing returns None. Building does nothing. Size is 0 by definition.

    Example::

        >>> Pass.parse(b"")
        None
        >>> Pass.build(None)
        b''
        >>> Pass.sizeof()
        0
    """

    def __init__(self):
        super().__init__()
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        return None

    def _build(self, obj, stream, context, path):
        return obj

    def _static_sizeof(self, context, path):
        return 0

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context

@singleton
class Terminated(Construct):
    r"""
    Asserts end of stream (EOF). You can use it to ensure no more unparsed data follows in the stream.

    Parsing checks if stream reached EOF, and raises TerminatedError if not. Building does nothing. Size is defined as 0 because parsing and building does not consume or add into the stream, as far as other constructs see it.

    :raises TerminatedError: stream not at EOF when parsing

    Example::

        >>> Terminated.parse(b"")
        None
        >>> Terminated.parse(b"remaining")
        dingsda.core.TerminatedError: expected end of stream
    """

    def __init__(self):
        super().__init__()
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        if stream.read(1):
            raise TerminatedError("expected end of stream", path=path)

    def _build(self, obj, stream, context, path):
        return obj

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context


#===============================================================================
# tunneling and byte/bit swapping
#===============================================================================
class RawCopy(Subconstruct):
    r"""
    Used to obtain byte representation of a field (aside of object value).

    Returns a dict containing both parsed subcon value, the raw bytes that were consumed by subcon, starting and ending offset in the stream, and amount in bytes. Builds either from raw bytes representation or a value used by subcon. Size is same as subcon.

    Object is a dictionary with either "data" or "value" keys, or both.

    When building, if both the "value" and "data" keys are present, then the "data" key is used and the "value" key is ignored. This is undesirable in the case that you parse some data for the purpose of modifying it and writing it back; in this case, delete the "data" key when modifying the "value" key to correctly rebuild the former.

    :param subcon: Construct instance

    :raises StreamError: stream is not seekable and tellable
    :raises RawCopyError: building and neither data or value was given
    :raises StringError: building from non-bytes value, perhaps unicode

    Example::

        >>> d = RawCopy(Byte)
        >>> d.parse(b"\xff")
        Container(data=b'\xff', value=255, offset1=0, offset2=1, length=1)
        >>> d.build(dict(data=b"\xff"))
        '\xff'
        >>> d.build(dict(value=255))
        '\xff'
    """

    def _parse(self, stream, context, path):
        offset1 = stream_tell(stream, path)
        obj = self.subcon._parsereport(stream, context, path)
        offset2 = stream_tell(stream, path)
        stream_seek(stream, offset1, 0, path)
        data = stream_read(stream, offset2 - offset1, path)
        return Container(data=data, value=obj, offset1=offset1, offset2=offset2, length=(offset2-offset1))

    def _build(self, obj, stream, context, path):
        if obj is None and self.subcon.flagbuildnone:
            obj = dict(value=None)
        if 'data' in obj:
            data = obj['data']
            offset1 = stream_tell(stream, path)
            stream_write(stream, data, len(data), path)
            offset2 = stream_tell(stream, path)
            return Container(obj, data=data, offset1=offset1, offset2=offset2, length=(offset2-offset1))
        if 'value' in obj:
            value = obj['value']
            offset1 = stream_tell(stream, path)
            buildret = self.subcon._build(value, stream, context, path)
            value = value if buildret is None else buildret
            offset2 = stream_tell(stream, path)
            stream_seek(stream, offset1, 0, path)
            data = stream_read(stream, offset2 - offset1, path)
            return Container(obj, data=data, value=value, offset1=offset1, offset2=offset2, length=(offset2-offset1))
        raise RawCopyError('RawCopy cannot build, both data and value keys are missing', path=path)


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
        return self.lengthfield._static_sizeof(context, path) + self.subcon._sizeof(obj, context, path)

    def _expected_size(self, stream, context, path):
        position1 = stream_tell(stream, path)
        length = self.lengthfield._parse(stream, context, path)
        if self.includelength:
            length -= self.lengthfield._static_sizeof(context, path)
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
        extra_info = {"_offset": offset}
        obj, child_extra_info = subcon._preprocess_size(obj=obj, context=context, path=path, offset=offset+count_size)
        extra = {f"_{subcon.name}{k}": v for k, v in child_extra_info.items()}
        extra_info.update(extra)
        extra_info["_size"] = count_size + child_extra_info["_size"]
        extra_info["_endoffset"] = extra_info["_offset"] + extra_info["_size"]
        return obj, extra_info
    macro._preprocess_size = _preprocess_size

    def _expected_size(self, stream, context, path):
        position1 = stream_tell(stream, path)
        count = countfield._parse(stream, context, path)
        position2 = stream_tell(stream, path)
        return (position2-position1) + count * subcon._sizeof(context, path)
    macro._expected_size = _expected_size

    return macro


class FixedSized(Subconstruct):
    r"""
    Restricts parsing to specified amount of bytes.

    Parsing reads `length` bytes, then defers to subcon using new BytesIO with said bytes. Building builds the subcon using new BytesIO, then writes said data and additional null bytes accordingly. Size is same as `length`, although negative amount raises an error.

    :param length: integer or context lambda, total amount of bytes (both data and padding)
    :param subcon: Construct instance

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises PaddingError: length is negative
    :raises PaddingError: subcon written more bytes than entire length (negative padding)

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = FixedSized(10, Byte)
        >>> d.parse(b'\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        255
        >>> d.build(255)
        b'\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        >>> d.sizeof()
        10
    """

    def __init__(self, length, subcon):
        super().__init__(subcon)
        self.length = length

    def _parse(self, stream, context, path):
        length = evaluate(self.length, context)
        if length < 0:
            raise PaddingError("length cannot be negative", path=path)
        data = stream_read(stream, length, path)
        return self.subcon._parsereport(io.BytesIO(data), context, path)

    def _build(self, obj, stream, context, path):
        length = evaluate(self.length, context)
        if length < 0:
            raise PaddingError("length cannot be negative", path=path)
        stream2 = io.BytesIO()
        buildret = self.subcon._build(obj, stream2, context, path)
        data = stream2.getvalue()
        pad = length - len(data)
        if pad < 0:
            raise PaddingError("subcon build %d bytes but was allowed only %d" % (len(data), length), path=path)
        stream_write(stream, data, len(data), path)
        stream_write(stream, bytes(pad), pad, path)
        return buildret

    def _static_sizeof(self, context: Container, path: str) -> int:
        length = evaluate(self.length, context)
        if length < 0:
            raise PaddingError("length cannot be negative", path=path)
        return length

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        length = evaluate(self.length, context)
        if length < 0:
            raise PaddingError("length cannot be negative", path=path)
        return length


class NullTerminated(Subconstruct):
    r"""
    Restricts parsing to bytes preceding a null byte.

    Parsing reads one byte at a time and accumulates it with previous bytes. When term was found, (by default) consumes but discards the term. When EOF was found, (by default) raises same StreamError exception. Then subcon is parsed using new BytesIO made with said data. Building builds the subcon and then writes the term. Size is undefined.

    The term can be multiple bytes, to support string classes with UTF16/32 encodings.

    :param subcon: Construct instance
    :param term: optional, bytes, terminator byte-string, default is \x00 single null byte
    :param include: optional, bool, if to include terminator in resulting data, default is False
    :param consume: optional, bool, if to consume terminator or leave it in the stream, default is True
    :param require: optional, bool, if EOF results in failure or not, default is True

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different amount than actual data, or could not write all bytes
    :raises StreamError: encountered EOF but require is not disabled
    :raises PaddingError: terminator is less than 1 bytes in length

    Example::

        >>> d = NullTerminated(Byte)
        >>> d.parse(b'\xff\x00')
        255
        >>> d.build(255)
        b'\xff\x00'
    """

    def __init__(self, subcon, term=b"\x00", include=False, consume=True, require=True):
        super().__init__(subcon)
        self.term = term
        self.include = include
        self.consume = consume
        self.require = require

    def _parse(self, stream, context, path):
        term = self.term
        unit = len(term)
        if unit < 1:
            raise PaddingError("NullTerminated term must be at least 1 byte", path=path)
        data = b''
        while True:
            try:
                b = stream_read(stream, unit, path)
            except StreamError:
                if self.require:
                    raise
                else:
                    break
            if b == term:
                if self.include:
                    data += b
                if not self.consume:
                    stream_seek(stream, -unit, 1, path)
                break
            data += b
        return self.subcon._parsereport(io.BytesIO(data), context, path)

    def _build(self, obj, stream, context, path):
        buildret = self.subcon._build(obj, stream, context, path)
        stream_write(stream, self.term, len(self.term), path)
        return buildret

    def _static_sizeof(self, context, path):
        raise SizeofError(path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        raise SizeofError(path=path)


class NullStripped(Subconstruct):
    r"""
    Restricts parsing to bytes except padding left of EOF.

    Parsing reads entire stream, then strips the data from right to left of null bytes, then parses subcon using new BytesIO made of said data. Building defers to subcon as-is. Size is undefined, because it reads till EOF.

    The pad can be multiple bytes, to support string classes with UTF16/32 encodings.

    :param subcon: Construct instance
    :param pad: optional, bytes, padding byte-string, default is \x00 single null byte

    :raises PaddingError: pad is less than 1 bytes in length

    Example::

        >>> d = NullStripped(Byte)
        >>> d.parse(b'\xff\x00\x00')
        255
        >>> d.build(255)
        b'\xff'
    """

    def __init__(self, subcon, pad=b"\x00"):
        super().__init__(subcon)
        self.pad = pad

    def _parse(self, stream, context, path):
        pad = self.pad
        unit = len(pad)
        if unit < 1:
            raise PaddingError("NullStripped pad must be at least 1 byte", path=path)
        data = stream_read_entire(stream, path)
        if unit == 1:
            data = data.rstrip(pad)
        else:
            tailunit = len(data) % unit
            end = len(data)
            if tailunit and data[-tailunit:] == pad[:tailunit]:
                end -= tailunit
            while end-unit >= 0 and data[end-unit:end] == pad:
                end -= unit
            data = data[:end]
        return self.subcon._parsereport(io.BytesIO(data), context, path)

    def _build(self, obj, stream, context, path):
        return self.subcon._build(obj, stream, context, path)

    def _static_sizeof(self, context, path):
        raise SizeofError(path=path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        raise SizeofError(path=path)


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


class ProcessXor(Subconstruct):
    r"""
    Transforms bytes between the underlying stream and the subcon.

    Used internally by KaitaiStruct compiler, when translating `process: xor` tags.

    Parsing reads till EOF, xors data with the pad, then feeds that data into subcon. Building first builds the subcon into separate BytesIO stream, xors data with the pad, then writes that data into the main stream. Size is the same as subcon, unless it raises SizeofError.

    :param padfunc: integer or bytes or context lambda, single or multiple bytes to xor data with
    :param subcon: Construct instance

    :raises StringError: pad is not integer or bytes

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = ProcessXor(0xf0 or b'\xf0', Int16ub)
        >>> d.parse(b"\x00\xff")
        0xf00f
        >>> d.sizeof()
        2
    """

    def __init__(self, padfunc, subcon):
        super().__init__(subcon)
        self.padfunc = padfunc

    def _parse(self, stream, context, path):
        pad = evaluate(self.padfunc, context)
        if not isinstance(pad, (integertypes, bytestringtype)):
            raise StringError("ProcessXor needs integer or bytes pad", path=path)
        if isinstance(pad, bytestringtype) and len(pad) == 1:
            pad = byte2int(pad)
        data = stream_read_entire(stream, path)
        if isinstance(pad, integertypes):
            if not (pad == 0):
                data = integers2bytes( (b ^ pad) for b in data )
        if isinstance(pad, bytestringtype):
            if not (len(pad) <= 64 and pad == bytes(len(pad))):
                data = integers2bytes( (b ^ p) for b,p in zip(data, itertools.cycle(pad)) )
        return self.subcon._parsereport(io.BytesIO(data), context, path)

    def _build(self, obj, stream, context, path):
        pad = evaluate(self.padfunc, context)
        if not isinstance(pad, (integertypes, bytestringtype)):
            raise StringError("ProcessXor needs integer or bytes pad", path=path)
        if isinstance(pad, bytestringtype) and len(pad) == 1:
            pad = byte2int(pad)
        stream2 = io.BytesIO()
        buildret = self.subcon._build(obj, stream2, context, path)
        data = stream2.getvalue()
        if isinstance(pad, integertypes):
            if not (pad == 0):
                data = integers2bytes( (b ^ pad) for b in data )
        if isinstance(pad, bytestringtype):
            if not (len(pad) <= 64 and pad == bytes(len(pad))):
                data = integers2bytes( (b ^ p) for b,p in zip(data, itertools.cycle(pad)) )
        stream_write(stream, data, len(data), path)
        return buildret

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return self.subcon._sizeof(obj, context, path)


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


class Compressed(Tunnel):
    r"""
    Compresses and decompresses underlying stream when processing subcon. When parsing, entire stream is consumed. When building, it puts compressed bytes without marking the end. This dingsda should be used with :class:`~dingsda.core.Prefixed` .

    Parsing and building transforms all bytes using a specified codec. Since data is processed until EOF, it behaves similar to `GreedyBytes`. Size is undefined.

    :param subcon: Construct instance, subcon used for storing the value
    :param encoding: string, any of module names like zlib/gzip/bzip2/lzma, otherwise any of codecs module bytes<->bytes encodings, each codec usually requires some Python version
    :param level: optional, integer between 0..9, although lzma discards it, some encoders allow different compression levels

    :raises ImportError: needed module could not be imported by ctor
    :raises StreamError: stream failed when reading until EOF

    Example::

        >>> d = Prefixed(VarInt, Compressed(GreedyBytes, "zlib"))
        >>> d.build(bytes(100))
        b'\x0cx\x9cc`\xa0=\x00\x00\x00d\x00\x01'
        >>> len(_)
        13
   """

    def __init__(self, subcon, encoding, level=None):
        super().__init__(subcon)
        self.encoding = encoding
        self.level = level
        if self.encoding == "zlib":
            import zlib
            self.lib = zlib
        elif self.encoding == "gzip":
            import gzip
            self.lib = gzip
        elif self.encoding == "bzip2":
            import bz2
            self.lib = bz2
        elif self.encoding == "lzma":
            import lzma
            self.lib = lzma
        else:
            import codecs
            self.lib = codecs

    def _decode(self, data, context, path):
        if self.encoding in ("zlib", "gzip", "bzip2", "lzma"):
            return self.lib.decompress(data)
        return self.lib.decode(data, self.encoding)

    def _encode(self, data, context, path):
        if self.encoding in ("zlib", "gzip", "bzip2", "lzma"):
            if self.level is None or self.encoding == "lzma":
                return self.lib.compress(data)
            else:
                return self.lib.compress(data, self.level)
        return self.lib.encode(data, self.encoding)


class CompressedLZ4(Tunnel):
    r"""
    Compresses and decompresses underlying stream before processing subcon. When parsing, entire stream is consumed. When building, it puts compressed bytes without marking the end. This dingsda should be used with :class:`~dingsda.core.Prefixed` .

    Parsing and building transforms all bytes using LZ4 library. Since data is processed until EOF, it behaves similar to `GreedyBytes`. Size is undefined.

    :param subcon: Construct instance, subcon used for storing the value

    :raises ImportError: needed module could not be imported by ctor
    :raises StreamError: stream failed when reading until EOF

    Can propagate lz4.frame exceptions.

    Example::

        >>> d = Prefixed(VarInt, CompressedLZ4(GreedyBytes))
        >>> d.build(bytes(100))
        b'"\x04"M\x18h@d\x00\x00\x00\x00\x00\x00\x00#\x0b\x00\x00\x00\x1f\x00\x01\x00KP\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        >>> len(_)
        35
   """

    def __init__(self, subcon):
        super().__init__(subcon)
        import lz4.frame
        self.lib = lz4.frame

    def _decode(self, data, context, path):
        return self.lib.decompress(data)

    def _encode(self, data, context, path):
        return self.lib.compress(data)


class EncryptedSym(Tunnel):
    r"""
    Perform symmetrical encryption and decryption of the underlying stream before processing subcon. When parsing, entire stream is consumed. When building, it puts encrypted bytes without marking the end.

    Parsing and building transforms all bytes using the selected cipher. Since data is processed until EOF, it behaves similar to `GreedyBytes`. Size is undefined.

    The key for encryption and decryption should be passed via `contextkw` to `build` and `parse` methods.

    This dingsda is heavily based on the `cryptography` library, which supports the following algorithms and modes. For more details please see the documentation of that library.
    
    Algorithms:
    - AES
    - Camellia
    - ChaCha20
    - TripleDES
    - CAST5
    - SEED
    - SM4
    - Blowfish (weak cipher)
    - ARC4 (weak cipher)
    - IDEA (weak cipher)

    Modes:
    - CBC
    - CTR
    - OFB
    - CFB
    - CFB8
    - XTS
    - ECB (insecure)

    .. note:: Keep in mind that some of the algorithms require padding of the data. This can be done e.g. with :class:`~dingsda.core.Aligned`.
    .. note:: For GCM mode use :class:`~dingsda.core.EncryptedSymAead`.

    :param subcon: Construct instance, subcon used for storing the value
    :param cipher: Cipher object or context lambda from cryptography.hazmat.primitives.ciphers

    :raises ImportError: needed module could not be imported
    :raises StreamError: stream failed when reading until EOF
    :raises CipherError: no cipher object is provided
    :raises CipherError: an AEAD cipher is used

    Can propagate cryptography.exceptions exceptions.

    Example::

        >>> from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        >>> d = Struct(
        ...     "iv" / Default(Bytes(16), os.urandom(16)),
        ...     "enc_data" / EncryptedSym(
        ...         Aligned(16,
        ...             Struct(
        ...                 "width" / Int16ul,
        ...                 "height" / Int16ul,
        ...             )
        ...         ),
        ...         lambda ctx: Cipher(algorithms.AES(ctx._.key), modes.CBC(ctx.iv))
        ...     )
        ... )
        >>> key128 = b"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
        >>> d.build({"enc_data": {"width": 5, "height": 4}}, key=key128)
        b"o\x11i\x98~H\xc9\x1c\x17\x83\xf6|U:\x1a\x86+\x00\x89\xf7\x8e\xc3L\x04\t\xca\x8a\xc8\xc2\xfb'\xc8"
        >>> d.parse(b"o\x11i\x98~H\xc9\x1c\x17\x83\xf6|U:\x1a\x86+\x00\x89\xf7\x8e\xc3L\x04\t\xca\x8a\xc8\xc2\xfb'\xc8", key=key128)
        Container: 
            iv = b'o\x11i\x98~H\xc9\x1c\x17\x83\xf6|U:\x1a\x86' (total 16)
            enc_data = Container: 
                width = 5
                height = 4
   """

    def __init__(self, subcon, cipher):
        super().__init__(subcon)
        self.cipher = cipher

    def _evaluate_cipher(self, context, path):
        from cryptography.hazmat.primitives.ciphers import Cipher, modes
        cipher = evaluate(self.cipher, context)
        if not isinstance(cipher, Cipher):
            raise CipherError(f"cipher {repr(cipher)} is not a cryptography.hazmat.primitives.ciphers.Cipher object", path=path)
        if isinstance(cipher.mode, modes.GCM):
            raise CipherError(f"AEAD cipher is not supported in this class, use EncryptedSymAead", path=path)
        return cipher

    def _decode(self, data, context, path):
        cipher = self._evaluate_cipher(context, path)
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    def _encode(self, data, context, path):
        cipher = self._evaluate_cipher(context, path)
        encryptor = cipher.encryptor()
        return encryptor.update(data) + encryptor.finalize()


class EncryptedSymAead(Tunnel):
    r"""
    Perform symmetrical AEAD encryption and decryption of the underlying stream before processing subcon. When parsing, entire stream is consumed. When building, it puts encrypted bytes and tag without marking the end.

    Parsing and building transforms all bytes using the selected cipher and also authenticates the `associated_data`. Since data is processed until EOF, it behaves similar to `GreedyBytes`. Size is undefined.

    The key for encryption and decryption should be passed via `contextkw` to `build` and `parse` methods.

    This dingsda is heavily based on the `cryptography` library, which supports the following AEAD ciphers. For more details please see the documentation of that library.
    
    AEAD ciphers:
    - AESGCM
    - AESCCM
    - ChaCha20Poly1305

    :param subcon: Construct instance, subcon used for storing the value
    :param cipher: Cipher object or context lambda from cryptography.hazmat.primitives.ciphers

    :raises ImportError: needed module could not be imported
    :raises StreamError: stream failed when reading until EOF
    :raises CipherError: unsupported cipher object is provided

    Can propagate cryptography.exceptions exceptions.

    Example::

        >>> from cryptography.hazmat.primitives.ciphers import aead
        >>> d = Struct(
        ...     "nonce" / Default(Bytes(16), os.urandom(16)),
        ...     "associated_data" / Bytes(21),
        ...     "enc_data" / EncryptedSymAead(
        ...         GreedyBytes,
        ...         lambda ctx: aead.AESGCM(ctx._.key),
        ...         this.nonce,
        ...         this.associated_data
        ...     )
        ... )
        >>> key128 = b"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
        >>> d.build({"associated_data": b"This is authenticated", "enc_data": b"The secret message"}, key=key128)
        b'\xe3\xb0"\xbaQ\x18\xd3|\x14\xb0q\x11\xb5XZ\xeeThis is authenticated\x88~\xe5Vh\x00\x01m\xacn\xad k\x02\x13\xf4\xb4[\xbe\x12$\xa0\x7f\xfb\xbf\x82Ar\xb0\x97C\x0b\xe3\x85'
        >>> d.parse(b'\xe3\xb0"\xbaQ\x18\xd3|\x14\xb0q\x11\xb5XZ\xeeThis is authenticated\x88~\xe5Vh\x00\x01m\xacn\xad k\x02\x13\xf4\xb4[\xbe\x12$\xa0\x7f\xfb\xbf\x82Ar\xb0\x97C\x0b\xe3\x85', key=key128)
        Container: 
            nonce = b'\xe3\xb0"\xbaQ\x18\xd3|\x14\xb0q\x11\xb5XZ\xee' (total 16)
            associated_data = b'This is authenti'... (truncated, total 21)
            enc_data = b'The secret messa'... (truncated, total 18)
   """

    def __init__(self, subcon, cipher, nonce, associated_data=b""):
        super().__init__(subcon)
        self.cipher = cipher
        self.nonce = nonce
        self.associated_data = associated_data

    def _evaluate_cipher(self, context, path):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESCCM, ChaCha20Poly1305
        cipher = evaluate(self.cipher, context)
        if not isinstance(cipher, (AESGCM, AESCCM, ChaCha20Poly1305)):
            raise CipherError(f"cipher object {repr(cipher)} is not supported", path=path)
        return cipher

    def _decode(self, data, context, path):
        cipher = self._evaluate_cipher(context, path)
        nonce = evaluate(self.nonce, context)
        associated_data = evaluate(self.associated_data, context)
        return cipher.decrypt(nonce, data, associated_data)

    def _encode(self, data, context, path):
        cipher = self._evaluate_cipher(context, path)
        nonce = evaluate(self.nonce, context)
        associated_data = evaluate(self.associated_data, context)
        return cipher.encrypt(nonce, data, associated_data)


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

#===============================================================================
# adapters and validators
#===============================================================================
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


class ExprValidator(Validator):
    r"""
    Generic adapter that takes `validator` lambda as parameter. You can use ExprValidator instead of writing a full-blown class deriving from Validator when only a simple lambda is needed.

    :param subcon: Construct instance, subcon to adapt
    :param validator: lambda that takes (obj, context) and returns a bool

    Example::

        >>> d = ExprValidator(Byte, obj_ & 0b11111110 == 0)
        >>> d.build(1)
        b'\x01'
        >>> d.build(88)
        ValidationError: object failed validation: 88

    """
    def __init__(self, subcon, validator):
        super().__init__(subcon)
        self._validate = lambda obj,ctx,path: validator(obj,ctx)


def OneOf(subcon, valids):
    r"""
    Validates that the object is one of the listed values, both during parsing and building.

    .. note:: For performance, `valids` should be a set or frozenset.

    :param subcon: Construct instance, subcon to validate
    :param valids: collection implementing __contains__, usually a list or set

    :raises ValidationError: parsed or build value is not among valids

    Example::

        >>> d = OneOf(Byte, [1,2,3])
        >>> d.parse(b"\x01")
        1
        >>> d.parse(b"\xff")
        dingsda.core.ValidationError: object failed validation: 255
    """
    return ExprValidator(subcon, lambda obj,ctx: obj in valids)


def NoneOf(subcon, invalids):
    r"""
    Validates that the object is none of the listed values, both during parsing and building.

    .. note:: For performance, `valids` should be a set or frozenset.

    :param subcon: Construct instance, subcon to validate
    :param invalids: collection implementing __contains__, usually a list or set

    :raises ValidationError: parsed or build value is among invalids

    """
    return ExprValidator(subcon, lambda obj,ctx: obj not in invalids)


def Filter(predicate, subcon):
    r"""
    Filters a list leaving only the elements that passed through the predicate.

    :param subcon: Construct instance, usually Array GreedyRange Sequence
    :param predicate: lambda that takes (obj, context) and returns a bool

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Filter(obj_ != 0, Byte[:])
        >>> d.parse(b"\x00\x02\x00")
        [2]
        >>> d.build([0,1,0,2,0])
        b'\x01\x02'
    """
    return ExprSymmetricAdapter(subcon, lambda obj,ctx: [x for x in obj if predicate(x,ctx)])


class Slicing(Adapter):
    r"""
    Adapter for slicing a list. Works with GreedyRange and Sequence.

    :param subcon: Construct instance, subcon to slice
    :param count: integer, expected number of elements, needed during building
    :param start: integer for start index (or None for entire list)
    :param stop: integer for stop index (or None for up-to-end)
    :param step: integer, step (or 1 for every element)
    :param empty: object, value to fill the list with, during building

    Example::

        d = Slicing(Array(4,Byte), 4, 1, 3, empty=0)
        assert d.parse(b"\x01\x02\x03\x04") == [2,3]
        assert d.build([2,3]) == b"\x00\x02\x03\x00"
        assert d.sizeof() == 4
    """
    def __init__(self, subcon, count, start, stop, step=1, empty=None):
        super().__init__(subcon)
        self.count = count
        self.start = start
        self.stop = stop
        self.step = step
        self.empty = empty

    def _decode(self, obj, context, path):
        return obj[self.start:self.stop:self.step]

    def _encode(self, obj, context, path):
        if self.start is None:
            return obj
        elif self.stop is None:
            output = [self.empty] * self.count
            output[self.start::self.step] = obj
        else:
            output = [self.empty] * self.count
            output[self.start:self.stop:self.step] = obj
        return output


class Indexing(Adapter):
    r"""
    Adapter for indexing a list (getting a single item from that list). Works with Range and Sequence and their lazy equivalents.

    :param subcon: Construct instance, subcon to index
    :param count: integer, expected number of elements, needed during building
    :param index: integer, index of the list to get
    :param empty: object, value to fill the list with, during building

    Example::

        d = Indexing(Array(4,Byte), 4, 2, empty=0)
        assert d.parse(b"\x01\x02\x03\x04") == 3
        assert d.build(3) == b"\x00\x00\x03\x00"
        assert d.sizeof() == 4
    """
    def __init__(self, subcon, count, index, empty=None):
        super().__init__(subcon)
        self.count = count
        self.index = index
        self.empty = empty

    def _decode(self, obj, context, path):
        return obj[self.index]

    def _encode(self, obj, context, path):
        output = [self.empty] * self.count
        output[self.index] = obj
        return output

