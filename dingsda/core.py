# -*- coding: utf-8 -*-
import io

from typing import Tuple, Dict, Any, Optional

from dingsda.errors import *
from dingsda.lib.containers import Container, MetaInformation, ConstructMetaInformation
from dingsda.lib import stringtypes
from dingsda.helpers import singleton, evaluate, stream_tell, stream_write, stream_read, stream_seek
from dingsda.version import version_string

import xml.etree.ElementTree as ET


def sizeof_decorator(func):
    """ this decorator is for _sizeof functions only. It first tries to find the size using _static_sizeof and only
    calls sizeof when that throws a SizeofError. """
    def inner(*args, **kwargs):
        try:
            return args[0]._static_sizeof(args[2], args[3])
        except SizeofError:
            return func(*args, **kwargs)
    return inner


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
        metadata = ConstructMetaInformation(parsing=True, params=contextkw, io=stream)
        context = Container(metadata=metadata, **contextkw)
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

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Optional[MetaInformation]]:
        r"""
           Preprocess an object before building or sizing, called by the preprocess function.

            The basic preprocess function just returns the object and an empty dictionary.

            :param obj: the object to preprocess
            :param context: the context dictionary
            :param path: the path to the construct

            :return obj: the preprocessed object
            :return meta_info: a MetaInformation object containing extra information regarding offset, size, etc.
        """
        return obj, None

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Optional[MetaInformation]]:
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
            :return meta_info: a MetaInformation object containing extra information regarding offset, size, etc.
        """
        size = self._sizeof(obj, context, path)
        meta = MetaInformation(size=size, offset=offset, end_offset=offset + size)
        return obj, meta

    def build(self, obj: Any, preprocess_before: bool = True, **contextkw) -> bytes:
        r"""
        Build an object in memory (a bytes object).

        Whenever data cannot be written, ConstructError or its derivative is raised. This method is NOT ALLOWED to raise any other exceptions although (1) user-defined lambdas can raise arbitrary exceptions which are propagated (2) external libraries like numpy can raise arbitrary exceptions which are propagated (3) some list and dict lookups can raise IndexError and KeyError which are propagated.

        Context entries are passed only as keyword parameters \*\*contextkw.

        :param \*\*contextkw: context entries, usually empty

        :returns: bytes

        :raises ConstructError: raised for any reason
        """
        stream = io.BytesIO()
        self.build_stream(obj, stream, preprocess_before, **contextkw)
        return stream.getvalue()

    def build_stream(self, obj: Any, stream, preprocess_before: bool = True, **contextkw):
        r"""
        Build an object directly into a stream. See build().

        Does not return anything.
        """
        if preprocess_before:
            obj, _ = self.preprocess(obj, **contextkw)

        metadata = ConstructMetaInformation(building=True, params=contextkw)
        if isinstance(obj, dict):
            context = Container(obj, metadata=metadata, **contextkw)
            self._build(context, stream, context, "(building)")
        else:
            context = Container(metadata=metadata, **contextkw)
            self._build(obj, stream, context, "(building)")

    def build_file(self, obj: Any, filename: str, preprocess_before: bool = True, **contextkw):
        r"""
        Build an object into a closed binary file. See build().

        Does not return anything.
        """
        # Open the file for reading as well as writing. This allows builders to
        # read back the stream just written. For example. RawCopy does this.
        # See issue #888.
        with open(filename, 'w+b') as f:
            self.build_stream(obj, f, preprocess_before, **contextkw)

    def _build(self, obj: Any, stream: io.IOBase, context: Container, path: str):
        """Override in your subclass. Shall not return anything."""
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
        metadata = ConstructMetaInformation(xml_building=True, params=contextkw)
        context = Container(metadata=metadata, **contextkw)
        context[name] = obj
        # create root node
        xml = ET.Element(name)
        xml.attrib["_dingsda_version"] = version_string
        return self._toET(parent=xml, context=context, name=name, path="(toET)")

    def fromET(self, xml, **contextkw):
        r"""
            Convert an XML ElementTree to a construct.

        :param xml: The ElementTree
        :param contextkw: further arguments, passed directly into the context
        :returns: a Container
        """
        metadata = ConstructMetaInformation(xml_parsing=True, params=contextkw)
        context = Container(metadata=metadata, **contextkw)

        # create root node
        parent = ET.Element("Root")
        parent.append(xml)
        result = self._fromET(parent=parent, name=xml.tag, context=context, path="(fromET)")

        return result.get(xml.tag)

    def preprocess(self, obj: Any, sizing: bool = True, **contextkw) -> Tuple[Any, Optional[MetaInformation]]:
        r"""
            Preprocess an object before building.

            The basic preprocessing step adds for some special Constructs like Rebuilds lambdas or other
            values to the construct, so especially Rebuilds can use them in the build step afterwards.

            After the basic preprocessing, if the sizing parameter is set, the size of the construct and
            all subconstructs is added to the context. This adds attributes like _size and _ptr_size.

            :param obj: the object to preprocess
            :param sizing: whether to size the object after the first preprocessing step.
            :return obj: the preprocessed object
            :return extra_info: the dictionary containing extra information for the *current* object, like offset, size, etc.
        """
        metadata = ConstructMetaInformation(preprocessing=True, params=contextkw)

        if isinstance(obj, dict):
            context = Container(obj, metadata=metadata, **contextkw)
            obj, meta_info = self._preprocess(obj=context, context=context, path="(preprocess)")
        else:
            context = Container(metadata=metadata, **contextkw)
            obj, meta_info = self._preprocess(obj=obj, context=context, path="(preprocess)")

        if sizing:
            metadata = ConstructMetaInformation(preprocessing_sizing=True, params=contextkw)
            # FIXME: maybe function for force changing metadata?
            context._parent_meta_info = metadata
            return self._preprocess_size(obj=obj, context=context, path="(preprocess_size)", offset=0)

        return obj, meta_info

    def static_sizeof(self, **contextkw):
        r"""
        Calculate the size of this object without the use of an already parsed object.

        This always works for Constructs with static sizes like FormatFields, but doesn't for Constructs
        with dynamic length like Strings or RepeatUntil.

        Whenever size cannot be determined, a SizeofError is raised.

        :returns: integer if computable, raises SizeofError otherwise

        :raises SizeofError: size could not be determined in current context, or is impossible to be determined
        """
        metadata = ConstructMetaInformation(sizing=True, params=contextkw)
        context = Container(metadata=metadata, **contextkw)
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
        metadata = ConstructMetaInformation(sizing=True, params=contextkw)
        context = Container(metadata=metadata, **contextkw)
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
        Pointertypes, so you don't have to search for the _ptr_size attribute.

        This function is experimental!

        If _full_sizeof is not implemented, _sizeof is returned instead by default.

        Whenever size cannot be determined, a SizeofError is raised.

        :param: obj the parsed object for that the sizes of the fields shall be determined
        :returns: integer if computable, raises SizeofError otherwise

        :raises SizeofError: size could not be determined in current context, or is impossible to be determined
        """
        metadata = ConstructMetaInformation(sizing=True, params=contextkw)
        context = Container(metadata=metadata, **contextkw)
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

    def _is_simple_type(self, context: Optional[Container] = None) -> bool:
        """ is used by Array to determine, whether the type can be stored in a string array as XML attribute """
        return False

    def _is_struct(self, context: Optional[Container] = None) -> bool:
        """ is used by Struct to determine, whether a new context while parsing is needed """
        return False

    def _is_array(self, context: Optional[Container] = None) -> bool:
        """ is used by Array to detect nested arrays (is a problem with Array of Array of simple type) """
        return False

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
        from dingsda.struct import Struct
        lhs = self.subcons  if isinstance(self,  Struct) else [self]
        rhs = other.subcons if isinstance(other, Struct) else [other]
        return Struct(*(lhs + rhs))

    def __getitem__(self, count):
        """
        Used for making Arrays like Byte[5] and Byte[this.count].
        """
        if isinstance(count, slice):
            raise ConstructError("subcon[N] syntax can only be used for Arrays, use GreedyRange(subcon) instead?")
        if isinstance(count, int) or callable(count):
            from dingsda.arrays import Array
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

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Optional[MetaInformation]]:
        return self.subcon._preprocess(obj, context, path)

    def _build(self, obj, stream, context, path):
        self.subcon._build(obj, stream, context, path)

    def _static_sizeof(self, context: Container, path: str) -> int:
        return self.subcon._static_sizeof(context, path)

    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        return self.subcon._sizeof(obj, context, path)

    def _full_sizeof(self, obj: Any, context: Container, path: str) -> int:
        return self.subcon._full_sizeof(obj, context, path)

    def _is_array(self, context: Optional[Container] = None) -> bool:
        return self.subcon._is_array(context=context)

    def _is_simple_type(self, context: Optional[Container] = None) -> bool:
        return self.subcon._is_simple_type(context=context)

    def _is_struct(self, context: Optional[Container] = None) -> bool:
        return self.subcon._is_struct(context=context)


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
        self.subcon._build(obj, stream, context, path)

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

    def _is_simple_type(self, context: Optional[Container] = None):
        return self.subcon._is_simple_type(context=context)

    def _is_struct(self, context: Optional[Container] = None):
        return self.subcon._is_struct(context=context)

    def _is_array(self, context: Optional[Container] = None):
        return self.subcon._is_array(context=context)

    def _names(self):
        sc_names = [self.name]
        sc_names += self.subcon._names()
        return sc_names


#===============================================================================
# miscellaneous
#===============================================================================
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

    def _build(self, obj: Any, stream, context: Container, path: str):
        context.get("_index", None)

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

    def _build(self, obj: Any, stream, context: Container, path: str):
        obj = evaluate(self.func, context)
        self.subcon._build(obj, stream, context, path)

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Optional[MetaInformation]]:
        return self.func, None

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Optional[MetaInformation]]:
        try:
            size = self.subcon._static_sizeof(context, path)
            meta_info = MetaInformation(offset=offset, size=size, end_offset=offset + size)
            return self.func, meta_info
        except SizeofError:
            pass
        ev_obj = evaluate(self.func, context)
        size = self.subcon.sizeof(ev_obj, context, path)
        meta_info = MetaInformation(offset=offset, size=size, end_offset=offset + size)
        return self.func, meta_info

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


class StopIf(Construct):
    r"""
    Checks for a condition, and stops certain classes (:class:`~dingsda.core.Struct` :class:`~dingsda.core.GreedyRange`) from parsing or building further.

    Parsing and building check the condition, and raise StopFieldError if indicated. Size is undefined.

    :param condfunc: bool or context lambda (or truthy value)

    :raises StopFieldError: used internally

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> Struct('x'/Byte, StopIf(this.x == 0), 'y'/Byte)
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
        condfunc = evaluate(self.condfunc, context)
        if condfunc:
            raise StopFieldError(path=path)
        else:
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
