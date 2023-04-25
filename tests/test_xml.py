# -*- coding: utf-8 -*-

from tests.declarativeunittest import *
from construct import *
from construct.lib import *

from xml.etree import ElementTree as ET

def test_basic_xml():
    s = Struct(
        "a" / Int32ul,
        "b" / Int32ul,
    )

    data = {"a": 1, "b": 2}
    xml = s.toET(context=data, name="test", parent=None, is_root=True)

    assert(ET.tostring(xml) == b'<test a="1" b="2" />')
