from io import BytesIO

from dingsda.lib import MetaInformation, ConstructMetaInformation
from dingsda.numbers import Int8ul
from tests.declarativeunittest import *
from dingsda import *
from dingsda.lib import *


def test_getitem():
    c = Container(a=1)
    assert c["a"] == 1
    assert c.a == 1
    assert raises(lambda: c.unknownkey) == AttributeError
    assert raises(lambda: c["unknownkey"]) == KeyError

def test_setitem():
    c = Container()
    c.a = 1
    assert c["a"] == 1
    assert c.a == 1
    c["a"] = 2
    assert c["a"] == 2
    assert c.a == 2

def test_delitem():
    c = Container(a=1, b=2)
    del c.a
    assert "a" not in c
    assert raises(lambda: c.a) == AttributeError
    assert raises(lambda: c["a"]) == KeyError
    del c["b"]
    assert "b" not in c
    assert raises(lambda: c.b) == AttributeError
    assert raises(lambda: c["b"]) == KeyError
    assert c == Container()
    assert list(c) == []

def test_ctor_empty():
    c = Container()
    assert len(c) == 0
    assert list(c.items()) == []
    assert c == Container()
    assert c == Container(c)
    assert c == Container({})
    assert c == Container([])

def test_ctor_chained():
    c = Container(a=1, b=2, c=3, d=4)
    assert c == Container(c)

def test_ctor_dict():
    c = Container(a=1, b=2, c=3, d=4)
    c = Container(c)
    assert len(c) == 4
    assert list(c.items()) == [('a',1),('b',2),('c',3),('d',4)]

def test_ctor_seqoftuples():
    c = Container([('a',1),('b',2),('c',3),('d',4)])
    assert len(c) == 4
    assert list(c.items()) == [('a',1),('b',2),('c',3),('d',4)]

def test_ctor_orderedkw():
    c = Container(a=1, b=2, c=3, d=4)
    d = Container(a=1, b=2, c=3, d=4)
    assert c == d
    assert len(c) == len(d)
    assert list(c.items()) == list(d.items())

def test_keys():
    c = Container(a=1, b=2, c=3, d=4)
    assert list(c.keys()) == ["a","b","c","d"]

def test_values():
    c = Container(a=1, b=2, c=3, d=4)
    assert list(c.values()) == [1,2,3,4]

def test_items():
    c = Container(a=1, b=2, c=3, d=4)
    assert list(c.items()) == [("a",1),("b",2),("c",3),("d",4)]

def test_iter():
    c = Container(a=1, b=2, c=3, d=4)
    assert list(c) == list(c.keys())

def test_clear():
    c = Container(a=1, b=2, c=3, d=4)
    c.clear()
    assert c == Container()
    assert list(c.items()) == []

def test_pop():
    c = Container(a=1, b=2, c=3, d=4)
    assert c.pop("b") == 2
    assert c.pop("d") == 4
    assert c.pop("a") == 1
    assert c.pop("c") == 3
    assert raises(c.pop, "missing") == KeyError
    assert c == Container()

def test_popitem():
    c = Container(a=1, b=2, c=3, d=4)
    assert c.popitem() == ("d",4)
    assert c.popitem() == ("c",3)
    assert c.popitem() == ("b",2)
    assert c.popitem() == ("a",1)
    assert raises(c.popitem) == KeyError

def test_update_dict():
    c = Container(a=1, b=2, c=3, d=4)
    d = Container()
    d.update(c)
    assert d.a == 1
    assert d.b == 2
    assert d.c == 3
    assert d.d == 4
    assert c == d
    assert list(c.items()) == list(d.items())

def test_update_seqoftuples():
    c = Container(a=1, b=2, c=3, d=4)
    d = Container()
    d.update([("a",1),("b",2),("c",3),("d",4)])
    assert d.a == 1
    assert d.b == 2
    assert d.c == 3
    assert d.d == 4
    assert c == d
    assert list(c.items()) == list(d.items())

def test_copy_method():
    c = Container(a=1)
    d = c.copy()
    assert c == d
    assert c is not d

def test_copy():
    from copy import copy

    c = Container(a=1)
    d = copy(c)
    assert c == d
    assert c is not d

def test_deepcopy():
    from copy import deepcopy

    c = Container(a=1)
    d = deepcopy(c)
    d.a = 2
    assert c != d
    assert c is not d

def test_pickling():
    import pickle

    empty = Container()
    empty_unpickled = pickle.loads(pickle.dumps(empty))
    assert empty_unpickled == empty

    nested = Container(a=1,b=Container(),c=3,d=Container(e=4))
    nested_unpickled = pickle.loads(pickle.dumps(nested))
    assert nested_unpickled == nested

def test_eq_issue_818():
    c = Container(a=1, b=2, c=3, d=4, e=5)
    d = Container(a=1, b=2, c=3, d=4, e=5)
    assert c == c
    assert d == d
    assert c == d
    assert d == c

    a = Container(a=1,b=2)
    b = Container(a=1,b=2,c=3)
    assert not a == b
    assert not b == a

    # c contains internal '_io' field, which shouldn't be considered in the comparison
    c = Struct('a' / Int8ul).parse(b'\x01')
    d = {'a': 1}
    assert c == d
    assert d == c

def test_eq_numpy():
    import numpy
    c = Container(arr=numpy.zeros(10, dtype=numpy.uint8))
    d = Container(arr=numpy.zeros(10, dtype=numpy.uint8))
    assert c == d

def test_ne_issue_818():
    c = Container(a=1, b=2, c=3)
    d = Container(a=1, b=2, c=3, d=4, e=5)
    assert c != d
    assert d != c

def test_str_repr_empty():
    c = Container()
    assert str(c) == "Container: "
    assert repr(c) == "Container()"
    assert eval(repr(c)) == c

def test_str_repr():
    c = Container(a=1, b=2, c=3)
    assert str(c) == "Container: \n    a = 1\n    b = 2\n    c = 3"
    assert repr(c) == "Container(a=1, b=2, c=3)"
    assert eval(repr(c)) == c

def test_str_repr_nested():
    c = Container(a=1,b=2,c=Container())
    assert str(c) == "Container: \n    a = 1\n    b = 2\n    c = Container: "
    assert repr(c) == "Container(a=1, b=2, c=Container())"
    assert eval(repr(c)) == c

def test_str_repr_recursive():
    c = Container(a=1,b=2)
    c.c = c
    assert str(c) == "Container: \n    a = 1\n    b = 2\n    c = <recursion detected>"
    assert repr(c) == "Container(a=1, b=2, c=<recursion detected>)"

def test_fullstrings():
    setGlobalPrintFullStrings(True)
    c = Container(data=b"1234567890")
    assert str(c) == "Container: \n    data = b'1234567890' (total 10)"
    assert repr(c) == "Container(data=b'1234567890')"
    c = Container(data=u"1234567890")
    assert str(c) == "Container: \n    data = u'1234567890' (total 10)"
    assert repr(c) == "Container(data=u'1234567890')"
    c = Container(data=b"1234567890123456789012345678901234567890")
    assert str(c) == "Container: \n    data = b'1234567890123456789012345678901234567890' (total 40)"
    assert repr(c) == "Container(data=b'1234567890123456789012345678901234567890')"
    c = Container(data=u"1234567890123456789012345678901234567890")
    assert str(c) == "Container: \n    data = u'1234567890123456789012345678901234567890' (total 40)"
    assert repr(c) == "Container(data=u'1234567890123456789012345678901234567890')"

    setGlobalPrintFullStrings(False)
    c = Container(data=b"1234567890")
    assert str(c) == "Container: \n    data = b'1234567890' (total 10)"
    assert repr(c) == "Container(data=b'1234567890')"
    c = Container(data=u"1234567890")
    assert str(c) == "Container: \n    data = u'1234567890' (total 10)"
    assert repr(c) == "Container(data=u'1234567890')"
    c = Container(data=b"1234567890123456789012345678901234567890")
    assert str(c) == "Container: \n    data = b'1234567890123456'... (truncated, total 40)"
    assert repr(c) == "Container(data=b'1234567890123456789012345678901234567890')"
    c = Container(data=u"1234567890123456789012345678901234567890")
    assert str(c) == "Container: \n    data = u'12345678901234567890123456789012'... (truncated, total 40)"
    assert repr(c) == "Container(data=u'1234567890123456789012345678901234567890')"

    setGlobalPrintFullStrings()

def test_falseflags():
    d = FlagsEnum(Byte, set=1, unset=2)
    c = d.parse(b"\x01")

    setGlobalPrintFalseFlags(True)
    assert str(c) == "Container: \n    set = True\n    unset = False"
    assert repr(c) == "Container(set=True, unset=False)"

    setGlobalPrintFalseFlags(False)
    assert str(c) == "Container: \n    set = True"
    assert repr(c) == "Container(set=True, unset=False)"

    setGlobalPrintFalseFlags()

def test_privateentries():
    c = Container(_private = 1)

    setGlobalPrintPrivateEntries(True)
    assert str(c) == "Container: \n    _private = 1"
    assert repr(c) == "Container()"

    setGlobalPrintPrivateEntries(False)
    assert str(c) == "Container: "
    assert repr(c) == "Container()"

    setGlobalPrintPrivateEntries()

def test_len_bool():
    c = Container(a=1, b=2, c=3, d=4)
    assert len(c) == 4
    assert c
    c = Container()
    assert len(c) == 0
    assert not c

def test_in():
    c = Container(a=1)
    assert "a" in c
    assert "b" not in c

def test_regression_recursionlock():
    print("REGRESSION: recursion_lock() used to leave private keys.")
    c = Container()
    str(c); repr(c)
    assert not c

def test_meta_info_add():
    c = Container({"a": 1, "b": 2})
    c.set_meta("a", MetaInformation(offset=0, size=1, end_offset=1))

    assert(c.get_meta("a").offset == 0)
    assert(c.get_meta("a").size == 1)
    assert(c.get_meta("a").end_offset == 1)
    assert(c.get_meta("a").ptr_size == 0)
    assert(c.get_meta("b") is None)

def test_meta_info_merge():
    x = Container({"a": 1, "b": 2})
    x.set_meta("a", MetaInformation(offset=0, size=1, end_offset=1))

    c = Container(x)

    assert(c.get_meta("a").offset == 0)
    assert(c.get_meta("a").size == 1)
    assert(c.get_meta("a").end_offset == 1)
    assert(c.get_meta("a").ptr_size == 0)
    assert(c.get_meta("b") is None)


def test_meta_info_merge():
    x = Container({"a": 1, "b": 2})
    x.set_meta("a", MetaInformation(offset=0, size=1, end_offset=1))

    c = Container(x)

    assert(c.get_meta("a") == c.meta("a"))
    assert(c.get_meta("b") == c.meta("b"))


def test_container_root():
    p = Container({"a": 1, "b": 2})
    c = Container({"c": 3, "d": 4}, parent=p)
    c2 = Container({"x": 3, "y": 42}, parent=c)

    assert(p._parent_node is None)
    assert(p._root_node is None)
    assert(c._parent_node is p)
    assert(c._root_node is p)
    assert(c2._parent_node is c)
    assert(c2._root_node is p)

    assert(p._ is None)
    assert(p._root is p)
    assert(c._ is p)
    assert(c._root is p)
    assert(c2._ is c)
    assert(c2._root is p)


def test_container_setting():
    p = Container({"a": 1, "b": 2})
    c = Container({"c": 3, "d": 4}, parent=p)
    c2 = Container({"x": 3, "y": 42}, parent=c)

    p.a = 3
    assert(p.a == 3)
    p.b = 4
    assert(p.b == 4)
    c.c = 12
    assert(c.c == 12)
    c.d = 24
    assert(c.d == 24)
    c2.x = 123
    assert(c2.x == 123)
    c2.y = 435
    assert(c2.y == 435)


def test_container_attr_item_equality():
    p = Container({"a": 1, "b": 2})
    c = Container({"c": 3, "d": 4}, parent=p)
    c2 = Container({"x": 3, "y": 42}, parent=c)

    assert(p._parent_node is p["_parent_node"])
    assert(p._root_node is p["_root_node"])
    assert(c._parent_node is c["_parent_node"])
    assert(c._root_node is c["_root_node"])
    assert(c2._parent_node is c2["_parent_node"])
    assert(c2._root_node is c2["_root_node"])


def test_container_construct_metadata():
    metadata = ConstructMetaInformation(
        preprocessing = True,
        preprocessing_sizing = True,
        parsing = True,
        building = True,
        sizing = True,
        xml_building = True,
        xml_parsing = True,
        params = {"param1": 1, "param2": 2},
        io=BytesIO(),
    )
    p = Container({"a": 1, "b": 2}, metadata=metadata)
    c = Container({"c": 3, "d": 4}, parent=p)
    c2 = Container({"x": 3, "y": 42}, parent=c)

    assert(True == p._preprocessing == c._preprocessing == c2._preprocessing)
    assert(True == p._preprocessing_sizing == c._preprocessing_sizing == c2._preprocessing_sizing)
    assert(True == p._parsing == c._parsing == c2._parsing)
    assert(True == p._building == c._building == c2._building)
    assert(True == p._sizing == c._sizing == c2._sizing)
    assert(True == p._xml_building == c._xml_building == c2._xml_building)
    assert(True == p._xml_parsing == c._xml_parsing == c2._xml_parsing)
    assert({"param1": 1, "param2": 2} == p._params == c._params == c2._params)
    assert(p._io == c._io == c2._io)

    assert(raises(lambda: p.__setattr__("_preprocessing", False)) == AttributeError)
    assert(raises(lambda: p.__setattr__("_preprocessing_sizing", False)) == AttributeError)
    assert(raises(lambda: p.__setattr__("_parsing", False)) == AttributeError)
    assert(raises(lambda: p.__setattr__("_building", False)) == AttributeError)
    assert(raises(lambda: p.__setattr__("_sizing", False)) == AttributeError)
    assert(raises(lambda: p.__setattr__("_xml_building", False)) == AttributeError)
    assert(raises(lambda: p.__setattr__("_xml_parsing", False)) == AttributeError)
    assert(raises(lambda: p.__setattr__("_params", False)) == AttributeError)
    assert(raises(lambda: p.__setattr__("_io", False)) == AttributeError)


def test_container_construct_empty_metadata():
    p = Container({"a": 1, "b": 2})
    c = Container({"c": 3, "d": 4}, parent=p)
    c2 = Container({"x": 3, "y": 42}, parent=c)

    assert(False == p._preprocessing == c._preprocessing == c2._preprocessing)
    assert(False == p._preprocessing_sizing == c._preprocessing_sizing == c2._preprocessing_sizing)
    assert(False == p._parsing == c._parsing == c2._parsing)
    assert(False == p._building == c._building == c2._building)
    assert(False == p._sizing == c._sizing == c2._sizing)
    assert(False == p._xml_building == c._xml_building == c2._xml_building)
    assert(False == p._xml_parsing == c._xml_parsing == c2._xml_parsing)
    assert(p._io == c._io == c2._io)
