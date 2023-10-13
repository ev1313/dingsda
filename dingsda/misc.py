from typing import Any, Tuple, Dict

from dingsda.core import Construct, Subconstruct
from dingsda.errors import CheckError, ConstError, StringError, ExplicitError, SizeofError, TerminatedError
from dingsda.helpers import bytestringtype, evaluate, singleton
from dingsda.lib.containers import Container
from dingsda.bytes import Bytes


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

    def _build(self, obj: Any, stream, context: Container, path):
        if obj not in (None, self.value):
            raise ConstError(f"building expected None or {repr(self.value)} but got {repr(obj)}", path=path)
        self.subcon._build(self.value, stream, context, path)

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

    def _build(self, obj: Any, stream, context: Container, path: str):
        return evaluate(self.func, context)

    def _preprocess(self, obj: Any, context: Container, path: str) -> Tuple[Any, Dict[str, Any]]:
        return self.func, None

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 0

    def _toET(self, parent, name, context, path):
        return None

    def _fromET(self, parent, name, context, path, is_root=False):
        return context


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
        self.subcon._build(obj, stream, context, path)

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

    def _static_sizeof(self, context: Container, path: str) -> int:
        return 0


