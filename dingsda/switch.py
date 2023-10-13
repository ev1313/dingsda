from typing import Any, Tuple, Optional

from dingsda import Construct, Pass, Container, evaluate, MetaInformation, SizeofError, Renamed


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

    def _parse(self, stream, context: Container, path: str) -> Any:
        keyfunc = evaluate(self.keyfunc, context)
        sc = self.cases.get(keyfunc, self.default)

        if sc._is_struct(context):
            ctx = Container(parent=context)
        else:
            ctx = context
        return sc._parsereport(stream, ctx, path)

    def _build(self, obj: Any, stream, context: Container, path: str):
        keyfunc = evaluate(self.keyfunc, context)
        sc = self.cases.get(keyfunc, self.default)
        sc._build(obj, stream, context, path)

    def _preprocess(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Optional[MetaInformation]]:
        keyfunc = evaluate(self.keyfunc, context, recurse=True)
        sc = self.cases.get(keyfunc, self.default)

        obj, _ = sc._preprocess(obj, context, path)
        assert(_ is None)

        return obj, None

    def _preprocess_size(self, obj: Any, context: Container, path: str, offset: int = 0) -> Tuple[Any, Optional[MetaInformation]]:
        keyfunc = evaluate(self.keyfunc, context, recurse=True)
        sc = self.cases.get(keyfunc, self.default)

        meta_info = MetaInformation(offset=offset, size=0, end_offset=0)

        obj, child_meta_info = sc._preprocess_size(obj=obj, context=context, path=path, offset=offset)

        meta_info.size = child_meta_info.size
        meta_info.end_offset = offset + child_meta_info.size

        return obj, meta_info

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

    def _is_simple_type(self, context: Optional[Container] = None) -> bool:
        assert(context is not None)
        keyfunc = evaluate(self.keyfunc, context, recurse=True)
        sc = self.cases.get(keyfunc, self.default)
        return sc._is_array(context)

    def _is_array(self, context: Optional[Container] = None) -> bool:
        assert(context is not None)
        keyfunc = evaluate(self.keyfunc, context, recurse=True)
        sc = self.cases.get(keyfunc, self.default)
        return sc._is_array(context)

    def _is_struct(self, context: Optional[Container] = None) -> bool:
        return False
        assert(context is not None)
        keyfunc = evaluate(self.keyfunc, context, recurse=True)
        sc = self.cases.get(keyfunc, self.default)
        return sc._is_struct(context)


