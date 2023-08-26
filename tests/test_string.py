from dingsda import PaddedString, PaddingError, this, Byte, Int16ub, Int16ul, VarInt, PascalString, SizeofError, Select, \
    SelectError, CString, GreedyString
from tests.declarativeunittest import common, raises


def test_paddedstring():
    common(PaddedString(10, "utf8"), b"hello\x00\x00\x00\x00\x00", u"hello")

    d = PaddedString(100, "ascii")
    assert d.parse(b"X"*100) == u"X"*100
    assert d.build(u"X"*100) == b"X"*100
    assert raises(d.build, u"X"*200) == PaddingError

    for e, us in [("utf8",1),("utf16",2),("utf_16_le",2),("utf32",4),("utf_32_le",4)]:
        s = u"Афон"
        data = (s.encode(e)+bytes(100))[:100]
        common(PaddedString(100, e), data, s)
        s = u""
        data = bytes(100)
        common(PaddedString(100, e), data, s)

    for e in ["ascii","utf8","utf16","utf-16-le","utf32","utf-32-le"]:
        PaddedString(10, e).static_sizeof() == 10
        PaddedString(this.n, e).static_sizeof(n=10) == 10


def test_pascalstring():
    for e,us in [("utf8",1),("utf16",2),("utf_16_le",2),("utf32",4),("utf_32_le",4)]:
        for sc in [Byte, Int16ub, Int16ul, VarInt]:
            s = u"Афон"
            data = sc.build(len(s.encode(e))) + s.encode(e)
            common(PascalString(sc, e), data, s)
            common(PascalString(sc, e), sc.build(0), u"")

    for e in ["utf8","utf16","utf-16-le","utf32","utf-32-le","ascii"]:
        raises(PascalString(Byte, e).sizeof) == SizeofError
        raises(PascalString(VarInt, e).sizeof) == SizeofError


def test_pascalstring_issue_960():
    d = Select(PascalString(Byte, "ascii"))
    assert raises(d.parse, b"\x01\xff") == SelectError
    assert raises(d.build, u"Афон") == SelectError


def test_cstring():
    for e,us in [("utf8",1),("utf16",2),("utf_16_le",2),("utf32",4),("utf_32_le",4)]:
        s = u"Афон"
        common(CString(e), s.encode(e)+bytes(us), s)
        common(CString(e), bytes(us), u"")

    CString("utf8").build(s) == b'\xd0\x90\xd1\x84\xd0\xbe\xd0\xbd'+b"\x00"
    CString("utf16").build(s) == b'\xff\xfe\x10\x04D\x04>\x04=\x04'+b"\x00\x00"
    CString("utf32").build(s) == b'\xff\xfe\x00\x00\x10\x04\x00\x00D\x04\x00\x00>\x04\x00\x00=\x04\x00\x00'+b"\x00\x00\x00\x00"

    for e in ["utf8","utf16","utf-16-le","utf32","utf-32-le","ascii"]:
        raises(CString(e).sizeof) == SizeofError


def test_greedystring():
    for e,us in [("utf8",1),("utf16",2),("utf_16_le",2),("utf32",4),("utf_32_le",4)]:
        s = u"Афон"
        common(GreedyString(e), s.encode(e), s)
        common(GreedyString(e), b"", u"")

    for e in ["utf8","utf16","utf-16-le","utf32","utf-32-le","ascii"]:
        raises(GreedyString(e).sizeof) == SizeofError


def test_string_encodings():
    # checks that "-" is replaced with "_"
    common(GreedyString("utf-8"), b"", u"")
    common(GreedyString("utf-8"), b'\xd0\x90\xd1\x84\xd0\xbe\xd0\xbd', u"Афон")
