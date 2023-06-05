from construct.lib.containers import Container, ListContainer
def get_current_field(context, name):
    idx = context.get("_index", None)
    if idx is not None:
        return context[f"{name}_{idx}"]
    else:
        return context[name]

def create_child_context(context, name, list_index=None):
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


def get_current_field(context, name):
    idx = context.get("_index", None)
    if idx is not None:
        return context[f"{name}_{idx}"]
    else:
        return context[name]

def create_parent_context(context):
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

def insert_or_append_field(context, name, value):
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


def rename_in_context(context, name, new_name):
    ctx = context
    idx = context.get("_index", None)
    if idx is not None:
        ctx[f"{new_name}_{idx}"] = context[f"{name}_{idx}"]
        ctx[f"{name}_{idx}"] = None
    else:
        ctx[new_name] = context[name]
        ctx[name] = None

    return ctx

import csv
from io import StringIO
def list_to_string(string_list):
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(string_list)
    return output.getvalue().removesuffix("\r\n")

def string_to_list(string):
    reader = csv.reader([string])
    return next(reader)
