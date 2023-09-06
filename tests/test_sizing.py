# -*- coding: utf-8 -*-
import hashlib
from tests.declarativeunittest import *
from dingsda import *
from dingsda.numbers import *
from dingsda.string import *
from dingsda.lazy import *
from dingsda.lib import *
from dingsda.date import Timestamp

def test_size_array_different():
    # test elements with differing sizes like Switch
    d = Array(3, Struct("test" / Byte, "x" / Switch(this.test, {1: "a" / Byte, 2: "b" / Int16ub, 3: "c" / Int32ub})))
    size_test(d, [{"test": 1, "x": 1},{"test": 1, "x": 2},{"test": 1, "x": 3}], size=6)
    size_test(d, [{"test": 1, "x": 1},{"test": 2, "x": 2},{"test": 1, "x": 3}], size=7)
    size_test(d, [{"test": 1, "x": 1},{"test": 2, "x": 2},{"test": 3, "x": 3}], size=10)

def test_size_pascalstring():
    # PascalString is a macro using GreedyBytes
    d = PascalString(Byte, "utf8")
    size_test(d, "test", size=5)