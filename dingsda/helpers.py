import pdb
from typing import Any, Optional
from dingsda.errors import StreamError, StringError
from dingsda.lib import bytestringtype
from dingsda.lib.containers import Container, ListContainer
from copy import deepcopy

def get_current_field(context: Container, name: str) -> Any:
    idx = context.get("_index", None)
    if idx is not None:
        return context[f"{name}_{idx}"]
    else:
        return context[name]


def create_child_context_2(context: Container, name: str, list_index: Optional[int]=None) -> Container:
    assert (context is not None)
    assert (name is not None)

    data = get_current_field(context, name)

    if isinstance(data, Container) or isinstance(data, dict):
        ctx = Container(_=context, **data)
    elif isinstance(data, ListContainer) or isinstance(data, list):
        assert (list_index is not None)
        # does not add an additional _ layer for arrays
        ctx = Container(**context)
        ctx._index = list_index
        ctx[f"{name}_{list_index}"] = data[list_index]
    else:
        # this is needed when the item is part of a list
        # then the name is e.g. "bar_1"
        ctx = Container(_=context)
        ctx[name] = data
    _root = ctx.get("_root", None)
    if _root is None:
        ctx["_root"] = context
    else:
        ctx["_root"] = _root
    return ctx


def create_parent_context(context):
    """ Creates a new context for the parent node. Used e.g. in Struct when parsing. """
    # we go down one layer
    ctx = Container()
    ctx["_"] = context
    # add root node
    _root = context.get("_root", None)
    if _root is None:
        ctx["_root"] = context
    else:
        ctx["_root"] = _root
    return ctx


def create_child_context(context: Container, obj: Optional[Container]) -> Container:
    """ Creates a new context for the child node. Used e.g. in Struct when building,
    will fail, if child is not a Container. """
    if obj is None:
        obj = {}

    ret = Container(obj)
    ctx = Container(_params = context.get("_params", None),
                    _root = context.get("_root", context),
                    _ = context,
                    _parsing = context.get("_parsing", False),
                    _building = context.get("_building", False),
                    _sizing = context.get("_sizing", False),
                    _subcons = context.get("_subcons", None),
                    _preprocessing = context.get('_preprocessing', False),
                    _index = context.get("_index", None))
    ret.update(ctx)
    return ret


def insert_or_append_field(context: Container, name: str, value: Any) -> Container:
    current = context.get(name, None)
    if current is None:
        context[name] = value
    elif isinstance(current, ListContainer) or isinstance(current, list):
        context[name].append(value)
    else:
        print("insert_or_append_field failed")
        print(context)
        print(name)
        print(current)
        assert (0)
    return context


def rename_in_context(context: Container, name: str, new_name: str) -> Container:
    ctx = context
    idx = context.get("_index", None)
    if idx is not None:
        ctx[f"{new_name}_{idx}"] = context[f"{name}_{idx}"]
        ctx.pop(f"{name}_{idx}", None)
    else:
        ctx[new_name] = context[name]
        ctx.pop(name, None)

    return ctx


import csv
from io import StringIO


def list_to_string(string_list: list) -> str:
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(string_list)
    return output.getvalue().removesuffix("\r\n")


def string_to_list(string: str) -> list:
    reader = csv.reader([string])
    return next(reader)


def singleton(arg):
    x = arg()
    return x


def hyphenatedict(d):
    return {k.replace("_","-").rstrip("-"):v for k,v in d.items()}


def hyphenatelist(l) -> list:
    return [hyphenatedict(d) for d in l]


def evaluate(param: Any, context: Container, recurse: bool = False):
    ctx = context
    ret = param(ctx) if callable(param) else param

    if recurse:
        while callable(ret):
            ret = ret(ctx)

    return ret


def stream_read(stream, length, path):
    if length < 0:
        raise StreamError("length must be non-negative, found %s" % length, path=path)
    try:
        data = stream.read(length)
    except Exception:
        raise StreamError("stream.read() failed, requested %s bytes" % (length,), path=path)
    if len(data) != length:
        raise StreamError("stream read less than specified amount, expected %d, found %d" % (length, len(data)), path=path)
    return data


def stream_read_entire(stream, path):
    try:
        return stream.read()
    except Exception:
        raise StreamError("stream.read() failed when reading until EOF", path=path)


def stream_write(stream, data, length, path):
    if not isinstance(data, bytestringtype):
        raise StringError("given non-bytes value, perhaps unicode? %r" % (data,), path=path)
    if length < 0:
        raise StreamError("length must be non-negative, found %s" % length, path=path)
    if len(data) != length:
        raise StreamError("bytes object of wrong length, expected %d, found %d" % (length, len(data)), path=path)
    try:
        written = stream.write(data)
    except Exception:
        raise StreamError("stream.write() failed, given %r" % (data,), path=path)
    if written != length:
        raise StreamError("stream written less than specified, expected %d, written %d" % (length, written), path=path)


def stream_seek(stream, offset, whence, path):
    try:
        return stream.seek(offset, whence)
    except Exception:
        raise StreamError("stream.seek() failed, offset %s, whence %s" % (offset, whence), path=path)


def stream_tell(stream, path):
    try:
        return stream.tell()
    except Exception:
        raise StreamError("stream.tell() failed", path=path)


def stream_size(stream):
    try:
        fallback = stream.tell()
        end = stream.seek(0, 2)
        stream.seek(fallback)
        return end
    except Exception:
        raise StreamError("stream. seek() tell() failed", path="???")


def stream_iseof(stream):
    try:
        fallback = stream.tell()
        data = stream.read(1)
        stream.seek(fallback)
        return not data
    except Exception:
        raise StreamError("stream. read() seek() tell() failed", path="???")
