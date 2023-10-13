from dingsda.adapters import Adapter
from dingsda.errors import MappingError
from dingsda.lib import stringtypes, integertypes
from dingsda.lib.containers import Container


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


