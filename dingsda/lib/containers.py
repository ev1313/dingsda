from itertools import chain
from typing import Any, Optional

from dingsda.lib.py3compat import *
import io
import re
import collections

from dataclasses import dataclass, field

@dataclass
class ConstructMetaInformation:
    """
    Used in Containers to save the meta information on the current action of the construct.

    Only created in the root context and given through the tree via indirection / references.
    """
    preprocessing: bool = False
    preprocessing_sizing: bool = False
    parsing: bool = False
    building: bool = False
    sizing: bool = False
    xml_building: bool = False
    xml_parsing: bool = False
    params: dict = field(default_factory=lambda: {})
    io: Optional[Any] = field(default=None)


@dataclass
class MetaInformation:
    """
    Used in Containers and ListContainers for storing the meta information of single elements
    """
    offset: int
    size: int
    end_offset: int
    ptr_size: int = 0


globalPrintFullStrings = False
globalPrintFalseFlags = False
globalPrintPrivateEntries = False


def setGlobalPrintFullStrings(enabled=False):
    r"""
    When enabled, Container __str__ produces full content of bytes and unicode strings, otherwise and by default, it produces truncated output (16 bytes and 32 characters).

    :param enabled: bool
    """
    global globalPrintFullStrings
    globalPrintFullStrings = enabled


def setGlobalPrintFalseFlags(enabled=False):
    r"""
    When enabled, Container __str__ that was produced by FlagsEnum parsing prints all values, otherwise and by default, it prints only the values that are True.

    :param enabled: bool
    """
    global globalPrintFalseFlags
    globalPrintFalseFlags = enabled


def setGlobalPrintPrivateEntries(enabled=False):
    r"""
    When enabled, Container __str__ shows keys like _ _index _etc, otherwise and by default, it hides those keys. __repr__ never shows private entries.

    :param enabled: bool
    """
    global globalPrintPrivateEntries
    globalPrintPrivateEntries = enabled


def recursion_lock(retval="<recursion detected>", lock_name="__recursion_lock__"):
    """Used internally."""
    def decorator(func):
        def wrapper(self, *args, **kw):
            if getattr(self, lock_name, False):
                return retval
            setattr(self, lock_name, True)
            try:
                return func(self, *args, **kw)
            finally:
                delattr(self, lock_name)

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


class Container(collections.OrderedDict):
    r"""
    The container used for results in all constructs.

    Under the hood it is a generic ordered dictionary that allows both key and attribute access, and preserves key order by insertion.
    Adding keys is preferred using \*\*entrieskw. Equality does NOT check item order. Also provides regex searching.

    Furthermore every item inside the dictionary gets a MetaInformation attribute. This can be accessed via get_meta and
    set_meta.

    For space efficiency dingsda tries to not create copies of Containers. For this every container stores his
    parent and root node reference. These can be accessed using the "_" and "_root" node respectively.

    Note that not all parameters can be accessed via attribute access (dot operator). If the name of an item matches
    a method name of the Container, it can only be accessed via key acces (square brackets). This includes the following
    names: clear, copy, fromkeys, get, items, keys, move_to_end, pop, popitem, search, search_all, setdefault, update, values.

    Example::

        # empty dict
        >>> Container()
        # list of pairs, not recommended
        >>> Container([ ("name","anonymous"), ("age",21) ])
        # This syntax requires Python 3.6
        >>> Container(name="anonymous", age=21)
        # copies another dict
        >>> Container(dict2)
        >>> Container(container2)

    ::

        >>> print(repr(obj))
        Container(text='utf8 decoded string...', value=123)
        >>> print(obj)
        Container
            text = u'utf8 decoded string...' (total 22)
            value = 123
    """
    __slots__ = ["__recursion_lock__", "_root_node", "_parent_node", "_parent_meta_info"]

    def __init__(self, other=(), /, **kwds):
        self._root_node = None
        self._parent_node = None
        self._parent_meta_info = None
        parent = kwds.pop("parent", None)
        if parent is not None:
            self._parent_node = parent
            self._root_node = parent if parent._root_node is None else parent._root_node
        parent_meta = kwds.pop("metadata", None)
        if parent_meta is not None:
            assert(self._parent_node is None)
            self._parent_meta_info = parent_meta

        self.update(other, **kwds)

    def __getattr__(self, name):
        try:
            if name in self.__slots__:
                return object.__getattribute__(self, name)
            else:
                return self.__getitem__(name)
        except KeyError:
            raise AttributeError(name)

    def __get_handle_special(self, name):
        if name == "_":
            if self._parent_node is None:
                raise KeyError(name)
            return self._parent_node
        elif name == "_root":
            if self._root_node is None:
                return self
            else:
                return self._root_node
        elif name == "_parsing":
            return self._root._parent_meta_info.parsing
        elif name == "_building":
            return self._root._parent_meta_info.building
        elif name == "_sizing":
            return self._root._parent_meta_info.sizing
        elif name == "_preprocessing":
            return self._root._parent_meta_info.preprocessing
        elif name == "_preprocessing_sizing":
            return self._root._parent_meta_info.preprocessing_sizing
        elif name == "_xml_building":
            return self._root._parent_meta_info.xml_building
        elif name == "_xml_parsing":
            return self._root._parent_meta_info.xml_parsing
        elif name == "_params":
            return self._root._parent_meta_info.params
        elif name == "_io":
            return self._root._parent_meta_info.io
        ret = super().__getitem__(name)[0]
        if isinstance(ret, Container):
            ret._parent_node = self
            ret._root_node = None
        return ret

    def __getitem__(self, name):
        ret = self.__get_handle_special(name)
        if callable(ret):
            return ret(self)
        return ret

    def __setattr__(self, name, value):
        try:
            if name in self.__slots__:
                return object.__setattr__(self, name, value)
            else:
                # calls __setitem__ + their checks
                self[name] = value
        except KeyError:
            raise AttributeError(name)

    def __setitem__(self, key, value):
        if key in ["_", "_root", "_parsing", "_building", "_sizing", "_preprocessing",
                   "_preprocessing_sizing", "_xml_building", "_xml_parsing", "_params", "_io"]:
            raise AttributeError(f"{key} not allowed to be set")
        super().__setitem__(key, (value, self.get_meta(key)))

    def __delattr__(self, name):
        try:
            if name in self.__slots__:
                return object.__delattr__(self, name)
            elif name in ["_", "_root"]:
                raise AttributeError(f"{name} not allowed to be deleted")
            else:
                del self[name]
        except KeyError:
            raise AttributeError(name)

    def get_meta(self, name):
        if name in ["_", "_root", "_parsing", "_building", "_sizing", "_preprocessing",
                   "_xml_building", "_xml_parsing", "_params", "_io"]:
            raise AttributeError(f"{name} not allowed to have meta information")
        try:
            return super().__getitem__(name)[1]
        except KeyError:
            return None

    def meta(self, name):
        return self.get_meta(name)

    def set_meta(self, name, value):
        if name in ["_", "_root"]:
            raise AttributeError(f"{name} not allowed to be set")
        try:
            super().__setitem__(name, (self.get(name, None), value))
        except KeyError:
            raise AttributeError(name)

    def meta_items(self):
        """ helper returning key/value tuple for meta information """
        for k,v in super().items():
            yield k, v[1]

    def meta_values(self):
        """ helper returning values for meta information """
        for k,v in super().items():
            yield v[1]

    def update(self, seqordict, **kwds):
        """
            Appends items from another dict/Container or list-of-tuples.
        """
        items = seqordict
        if isinstance(seqordict, dict):
            items = seqordict.items()
        chained = list(chain(items, kwds.items()))
        if len(chained) > 0:
            for k, v in chained:
                self[k] = v
                if isinstance(seqordict, Container):
                    self.set_meta(k, seqordict.get_meta(k))

    def get(self, key, default=None):
        try:
            return self.__get_handle_special(key)
        except KeyError:
            return default

    def setdefault(self, key):
        if key not in self:
            self[key] = None
        return self[key]

    def items(self):
        for k,v in super().items():
            yield k, v[0]

    def values(self):
        for v in super().values():
            yield v[0]

    def pop(self, key, default={}):
        if key in ["_", "_root"]:
            raise AttributeError(f"{key} not allowed to be popped")
        try:
            return super().pop(key)[0]
        except KeyError as k:
            if default is not self.pop.__defaults__[0]:
                return default
            else:
                raise k

    def popitem(self):
        ret = super().popitem()
        return (ret[0], ret[1][0])

    def copy(self):
        return Container(self)

    __update__ = update

    __copy__ = copy

    def __dir__(self):
        """For auto completion of attributes based on container values."""
        return list(self.keys()) + list(self.__class__.__dict__) + dir(super(Container, self)) + ["_", "_root"]

    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, dict):
            return False
        def isequal(v1, v2):
            if v1.__class__.__name__ == "ndarray" or v2.__class__.__name__ == "ndarray":
                import numpy
                return numpy.array_equal(v1, v2)
            return v1 == v2
        for k,v in self.items():
            if isinstance(k, unicodestringtype) and k.startswith(u"_"):
                continue
            if isinstance(k, bytestringtype) and k.startswith(b"_"):
                continue
            if k not in other or not isequal(v, other[k]):
                return False
        for k,v in other.items():
            if isinstance(k, unicodestringtype) and k.startswith(u"_"):
                continue
            if isinstance(k, bytestringtype) and k.startswith(b"_"):
                continue
            if k not in self or not isequal(v, self[k]):
                return False
        return True

    def __ne__(self, other):
       return not self == other

    @recursion_lock()
    def __repr__(self):
        parts = []
        for k,v in self.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            if isinstance(v, stringtypes):
                parts.append(str(k) + "=" + reprstring(v))
            else:
                parts.append(str(k) + "=" + repr(v))
        return "Container(%s)" % ", ".join(parts)

    @recursion_lock()
    def __str__(self):
        indentation = "\n    "
        text = ["Container: "]
        isflags = getattr(self, "_flagsenum", False)
        for k,v in self.items():
            if isinstance(k, str) and k.startswith("_") and not globalPrintPrivateEntries:
                continue
            if isflags and not v and not globalPrintFalseFlags:
                continue
            text.extend([indentation, str(k), " = "])
            if v.__class__.__name__ == "EnumInteger":
                text.append("(enum) (unknown) %s" % (v, ))
            elif v.__class__.__name__ == "EnumIntegerString":
                text.append("(enum) %s %s" % (v, v.intvalue, ))
            elif v.__class__.__name__ in ["HexDisplayedBytes", "HexDumpDisplayedBytes"]:
                text.append(indentation.join(str(v).split("\n")))
            elif isinstance(v, bytestringtype):
                printingcap = 16
                if len(v) <= printingcap or globalPrintFullStrings:
                    text.append("%s (total %d)" % (reprstring(v), len(v)))
                else:
                    text.append("%s... (truncated, total %d)" % (reprstring(v[:printingcap]), len(v)))
            elif isinstance(v, unicodestringtype):
                printingcap = 32
                if len(v) <= printingcap or globalPrintFullStrings:
                    text.append("%s (total %d)" % (reprstring(v), len(v)))
                else:
                    text.append("%s... (truncated, total %d)" % (reprstring(v[:printingcap]), len(v)))
            else:
                text.append(indentation.join(str(v).split("\n")))
        return "".join(text)

    def _search(self, compiled_pattern, search_all):
        items = []
        for key in self.keys():
            try:
                if isinstance(self[key], (Container,ListContainer)):
                    ret = self[key]._search(compiled_pattern, search_all)
                    if ret is not None:
                        if search_all:
                            items.extend(ret)
                        else:
                            return ret
                elif compiled_pattern.match(key):
                    if search_all:
                        items.append(self[key])
                    else:
                        return self[key]
            except:
                pass
        if search_all:
            return items
        else:
            return None

    def search(self, pattern):
        """
        Searches a container (non-recursively) using regex.
        """
        compiled_pattern = re.compile(pattern)
        return self._search(compiled_pattern, False)

    def search_all(self, pattern):
        """
        Searches a container (recursively) using regex.
        """
        compiled_pattern = re.compile(pattern)
        return self._search(compiled_pattern, True)


class ListContainer(list):
    r"""
    Generic container like list. Provides pretty-printing. Also provides regex searching.

    Further stores meta information for every item in the list.

    Example::

        >>> ListContainer()
        >>> ListContainer([1, 2, 3])

    ::

        >>> print(repr(obj))
        [1, 2, 3]
        >>> print(obj)
        ListContainer
            1
            2
            3
    """
    meta_infos = []

    @recursion_lock()
    def __repr__(self):
        return "ListContainer(%s)" % (list.__repr__(self), )

    @recursion_lock()
    def __str__(self):
        indentation = "\n    "
        text = ["ListContainer: "]
        for k in self:
            text.append(indentation)
            lines = str(k).split("\n")
            text.append(indentation.join(lines))
        return "".join(text)

    def get_meta(self, idx: int) -> Optional[MetaInformation]:
        """ returns the meta information of the item, if it exists, else None. """
        if idx < len(self.meta_infos):
            return self.meta_infos[idx]
        else:
            return None

    def meta(self, name):
        """ just a shorter name for get_meta """
        return self.get_meta(name)

    def set_meta(self, idx: int, value: MetaInformation):
        """ sets the meta information for the item, extends meta_info list if necessary.  """
        if len(self.meta_infos) <= idx:
            assert(idx < len(self))
            self.meta_infos.extend([None] * (1 + (idx - len(self.meta_infos))))
        self.meta_infos[idx] = value

    def _search(self, compiled_pattern, search_all):
        items = []
        for item in self:
            try:
                ret = item._search(compiled_pattern, search_all)
            except:
                continue
            if ret is not None:
                if search_all:
                    items.extend(ret)
                else:
                    return ret
        if search_all:
            return items
        else:
            return None

    def search(self, pattern):
        """
        Searches a container (non-recursively) using regex.
        """
        compiled_pattern = re.compile(pattern)
        return self._search(compiled_pattern, False)

    def search_all(self, pattern):
        """
        Searches a container (recursively) using regex.
        """
        compiled_pattern = re.compile(pattern)
        return self._search(compiled_pattern, True)
