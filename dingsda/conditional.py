import xml.etree.ElementTree as ET

from typing import Any, Dict, Tuple

from dingsda.core import Construct, Pass
from dingsda.helpers import evaluate
from dingsda.lib.containers import Container


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

    def _parse(self, stream, context: Container, path: str) -> Any:
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon
        return sc._parsereport(stream, context, path)

    def _build(self, obj: Any, stream, context: Container, path: str):
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon
        sc._build(obj, stream, context, path)

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

    def _toET(self, parent: ET.Element, name: str, context: Container, path: str) -> ET.Element:
        condfunc = evaluate(self.condfunc, context)
        sc = self.thensubcon if condfunc else self.elsesubcon

        return sc._toET(parent, name, context, path)

    def _fromET(self, parent: ET.Element, name: str, context: Container, path: str, is_root=False) -> Container:
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


