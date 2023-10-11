from tests.declarativeunittest import *
from dingsda import *
from dingsda.lib import *

from dingsda.lib.containers import ConstructMetaInformation

from io import BytesIO


def test_str():
    l = ListContainer(range(5))
    assert str(l) == "ListContainer: \n    0\n    1\n    2\n    3\n    4"
    assert repr(l) == "ListContainer([0, 1, 2, 3, 4])"

    l = ListContainer(range(5))
    print(repr(str(l)))
    print(repr((l)))
    l.append(l)
    assert str(l) == "ListContainer: \n    0\n    1\n    2\n    3\n    4\n    <recursion detected>"
    assert repr(l) == "ListContainer([0, 1, 2, 3, 4, <recursion detected>])"


def test_listcontainer_root():
    p = ListContainer([1,2,3])
    c = ListContainer([4,5,6], parent=p)
    p.append(c)
    c2 = ListContainer([7,8,9], parent=c)
    c.append(c2)

    assert(p._parent_node is None)
    assert(p._root_node is None)
    assert(c._parent_node is p)
    assert(c._root_node is p)
    assert(c2._parent_node is c)
    assert(c2._root_node is p)

    assert(p._ == None)
    assert(p._root is p)
    assert(c._ is p)
    assert(c._root is p)
    assert(c2._ is c)
    assert(c2._root is p)


def test_listcontainer_attr_item_equality():
    p = ListContainer([1, 2, 3])
    c = ListContainer([4, 5, 6], parent=p)
    p.append(c)
    c2 = ListContainer([7, 8, 9], parent=c)
    c.append(c2)

    assert(p._parent_node is p["_parent_node"])
    assert(p._root_node is p["_root_node"])
    assert(c._parent_node is c["_parent_node"])
    assert(c._root_node is c["_root_node"])
    assert(c2._parent_node is c2["_parent_node"])
    assert(c2._root_node is c2["_root_node"])


def test_listcontainer_construct_metadata():
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
    c = ListContainer([1,2,3], parent=p)
    p["c"] = c
    c2 = Container({"x": 3, "y": 42}, parent=c)
    c.append(c2)

    assert(True == p._preprocessing == c._preprocessing == c2._preprocessing)
    assert(True == p._preprocessing_sizing == c._preprocessing_sizing == c2._preprocessing_sizing)
    assert(True == p._parsing == c._parsing == c2._parsing)
    assert(True == p._building == c._building == c2._building)
    assert(True == p._sizing == c._sizing == c2._sizing)
    assert(True == p._xml_building == c._xml_building == c2._xml_building)
    assert(True == p._xml_parsing == c._xml_parsing == c2._xml_parsing)
    assert({"param1": 1, "param2": 2} == p._params == c._params == c2._params)
    assert(p._io == c._io == c2._io)


def test_listcontainer_access_items():
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
    c = ListContainer([1, 2, 3], parent=p)
    p["c"] = c
    c2 = Container({"x": 3, "y": 42}, parent=c)
    c.append(c2)

    assert(c[0] == 1)
    assert(c[1] == 2)
    assert(c[2] == 3)
    assert(c[3].x == 3)
    assert(c[3].y == 42)
    assert(c["_"].a == 1)
    assert(c["_"].b == 2)
    assert(c.a == 1)
    assert(c.b == 2)

