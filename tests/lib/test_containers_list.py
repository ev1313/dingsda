from tests.declarativeunittest import *
from dingsda import *
from dingsda.lib import *

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
