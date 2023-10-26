import xml.etree.ElementTree as ET

import io
from typing import Optional, Any, Tuple

from dingsda.core import Construct, Container, sizeof_decorator
from dingsda.errors import SizeofError, StopFieldError
from dingsda.helpers import evaluate
from dingsda.lib.containers import MetaInformation, ListContainer
from dingsda.alignment import Aligned


class Structconstruct(Construct):
    def _is_simple_type(self, context: Optional[Container] = None) -> bool:
        return False

    def _is_struct(self, context: Optional[Container] = None) -> bool:
        return True

    def _static_sizeof(self, context: Container, path: str) -> int:
        try:
            return sum(sc._static_sizeof(context, path) for sc in self.subcons)
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)

    @sizeof_decorator
    def _sizeof(self, obj: Any, context: Container, path: str) -> int:
        try:
            size_sum = 0
            for sc in self.subcons:
                try:
                    size_sum += sc._static_sizeof(context, path)
                except SizeofError:
                    if sc._is_array(context):
                        ctx = Container(parent=context)
                    else:
                        ctx = context

                    for name in sc._names():
                        child_obj = context.get(name, None)
                        if child_obj is not None:
                            break

                    size_sum += sc._sizeof(child_obj, ctx, path)

            return size_sum
        except (KeyError, AttributeError):
            raise SizeofError("cannot calculate size, key not found in context", path=path)
        assert(0)


class Struct(Structconstruct):
    r"""
    Sequence of usually named constructs, similar to structs in C. The members are parsed and build in the order they are defined. If a member is anonymous (its name is None) then it gets parsed and the value discarded, or it gets build from nothing (from None).

    Some fields do not need to be named, since they are built without value anyway. See: Const Padding Check Error Pass Terminated Tell for examples of such fields.

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
        # FIXME: for what is this?
        self._subcons = Container((sc.name,sc) for sc in self.subcons if sc.name)
        self.flagbuildnone = all(sc.flagbuildnone for sc in self.subcons)

    def __getattr__(self, name):
        if name in self._subcons:
            return self._subcons[name]
        raise AttributeError

    def _parse(self, stream, context, path):
        """
        When parsing a Struct we need to create a new subcontext, where the subcons of the structure store
        their values. For this we create a new Container and set the parent to the current context.

        Furthermore we return the reference to this context after all subcons got parsed.
        If this is a nested Struct for example, this reference gets set as a value in the parent context afterwards.

        """
        context["_subcons"] = self._subcons
        for sc in self.subcons:
            try:
                # we need to determine at this point, whether we need to create a new context or not
                # (only Arrays / Structs need a new context, everything else is just added with their name to the current context)
                if sc._is_struct(context=context):
                    ctx = Container(parent=context)
                else:
                    ctx = context
                subobj = sc._parsereport(stream, ctx, path)
                if sc.name:
                    context[sc.name] = subobj

            except StopFieldError:
                break
        context.pop("_subcons")
        return context

    def _preprocess(self, obj: Container, context: Container, path: str) -> Tuple[Any, Optional[MetaInformation]]:
        if obj is None:
            obj = Container(parent=context)
        else:
            assert(isinstance(obj, Container))
            if obj is not context:
                assert(obj._ is context)

        for sc in self.subcons:
            subobj = obj.get(sc.name, None)

            preprocessret, _ = sc._preprocess(subobj, obj, path)
            assert(_ is None)

            if sc.name:
                obj[sc.name] = preprocessret

        return obj, None

    def _preprocess_size(self, obj: Container, context: Container, path: str, offset: int = 0) -> Tuple[Any, Optional[MetaInformation]]:
        if obj is None:
            obj = Container(parent=context)
        else:
            assert(isinstance(obj, Container))
            if obj is not context:
                assert(obj._ is context)

        size = 0
        meta_info = MetaInformation(offset=offset, size=0, end_offset=0)
        for sc in self.subcons:
            try:
                subobj = obj.get(sc.name, None)

                preprocessret, child_meta_info = sc._preprocess_size(subobj, obj, path, offset=offset)

                # update offset & size
                retsize = child_meta_info.size
                offset += retsize
                size += retsize
                if sc.name:
                    obj[sc.name] = preprocessret

                # add current meta_info to context, so e.g. lambdas can use them already
                obj.set_meta(sc.name, child_meta_info)
            except StopFieldError:
                break

        meta_info.size = size
        meta_info.end_offset = offset

        return obj, meta_info

    def _build(self, obj: Any, stream: io.IOBase, context: Container, path: str):
        """
        When building we get a context containing all the values of the subcons.

        Furthermore when parsing a structure, obj contains a reference to the current part of the context.

        Python doesn't allow something like const, however the context should not be changed usually.

        This layout is for legacy reasons and with the new Containers storing their parents and the root, the context
        can also be gotten using the "_" of the obj.
        """
        # the _subcons get updated here, because fromET wouldn't add them
        context["_subcons"] = self._subcons
        idx = context.get("_index", None)
        if idx is not None:
            context["_index"] = idx

        for sc in self.subcons:
            try:
                if not sc.flagbuildnone and not obj.__contains__(sc.name):
                    raise KeyError(sc.name)
                subobj = obj.get(sc.name, None)

                sc._build(subobj, stream, obj, path)

            except StopFieldError:
                break

    def _toET(self, parent: ET.Element, obj: Container, path: str) -> ET.Element:
        assert(parent is not None)

        ctx = Container(parent=context)

        elem = ET.Element(name)
        for sc in self.subcons:
            if sc.name is None or sc.name.startswith("_"):
                continue

            child = sc._toET(parent=elem, name=sc.name, context=ctx, path=f"{path} -> {name}")
            if child is not None:
                elem.append(child)

        return elem

    def _fromET(self, parent: ET.Element, obj: Container, path: str) -> Container:
        # we go down one layer
        ctx = Container(parent=context)

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

        context[name] = ctx

        return context


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


class FocusedStruct(Construct):
    r"""
    Allows constructing more elaborate "adapters" than Adapter class.

    Parse does parse all subcons in Struct, but returns only the element that was selected (discards other values).
    Build does build all subcons in sequence, where each gets build from nothing
    (except the selected subcon which is given the object). Size is the sum of all subcon sizes,
    unless any subcon raises SizeofError.

    This class does context nesting, meaning its members are given access to a new dictionary where the "_" entry points
    to the outer context. When parsing, each member gets parsed and subcon parse return value is inserted into context
    under matching key only if the member was named. When building, the matching entry gets inserted into context before
    subcon gets build, and if subcon build returns a new value (not None) that gets replaced in the context.

    This class exposes subcons as attributes. You can refer to subcons that were inlined (and therefore do not exist as
    variable in the namespace) by accessing the struct attributes, under same name. Also note that compiler does not
    support this feature. See examples.

    This class exposes subcons in the context. You can refer to subcons that were inlined (and therefore do not exist as
    variable in the namespace) within other inlined fields using the context. Note that you need to use a lambda (`this`
    expression is not supported). Also note that compiler does not support this feature. See examples.

    This class is used internally to implement :class:`~dingsda.core.PrefixedArray`.

    :param parsebuildfrom: string name or context lambda, selects a subcon
    :param \*subcons: Construct instances, list of members, some can be named
    :param \*\*subconskw: Construct instances, list of members (requires Python 3.6)

    :raises StreamError: requested reading negative amount, could not read enough bytes, requested writing different
    amount than actual data, or could not write all bytes
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

    def _build(self, obj: Any, stream, context: Container, path: str):
        ctx = Container(parent=context)
        parsebuildfrom = evaluate(self.parsebuildfrom, ctx)
        ctx[parsebuildfrom] = obj
        for i,sc in enumerate(self.subcons):
            sc._build(obj if sc.name == parsebuildfrom else None, stream, ctx, path)

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

    def _fromET(self, parent: ET.Element, name: str, context: Container, path: str, is_root=False) -> Container:
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

    def _names(self) -> list[str]:
        return self._get_main_sc()._names()

    def _is_simple_type(self, context: Optional[Container] = None) -> bool:
        return self._get_main_sc()._is_simple_type(context=context)

    def _is_array(self, context: Optional[Container] = None) -> bool:
        return self._get_main_sc()._is_array(context=context)


FocusedSeq = FocusedStruct
