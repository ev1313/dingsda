DingsDa 0.2.1
===================

DingsDa is a powerful **declarative** and **symmetrical** parser and builder for binary data.
It is a fork of Construct 2.1, which removes the parser generator features, but adds preprocessing and XML de- and
encoding. It is build mainly with reverse engineering data formats in mind.

Instead of writing *imperative code* to parse a piece of data, you declaratively define a *data structure* that describes your data. As this data structure is not code, you can use it in one direction to *parse* data into Pythonic objects, and in the other direction, to *build* objects into binary data.

The library provides both simple, atomic constructs (such as integers of various sizes), as well as composite ones which allow you form hierarchical and sequential structures of increasing complexity. Construct features **bit and byte granularity**, easy debugging and testing, an **easy-to-extend subclass system**, and lots of primitive constructs to make your work easier:

* Fields: raw bytes or numerical types
* Structs and Sequences: combine simpler constructs into more complex ones
* Bitwise: splitting bytes into bit-grained fields
* Adapters: change how data is represented
* Arrays/Ranges: duplicate constructs
* Meta-constructs: use the context (history) to compute the size of data
* If/Switch: branch the computational path based on the context
* On-demand (lazy) parsing: read and parse only what you require
* Pointers: jump from here to there in the data stream
* Tunneling: prefix data with a byte count or compress it


Example
---------

A ``Struct`` is a collection of ordered, named fields::

    >>> format = Struct(
    ...     "signature" / Const(b"BMP"),
    ...     "width" / Int8ub,
    ...     "height" / Int8ub,
    ...     "pixels" / Array(this.width * this.height, Byte),
    ... )
    >>> format.build(dict(width=3,height=2,pixels=[7,8,9,11,12,13]))
    b'BMP\x03\x02\x07\x08\t\x0b\x0c\r'
    >>> format.parse(b'BMP\x03\x02\x07\x08\t\x0b\x0c\r')
    Container(signature=b'BMP')(width=3)(height=2)(pixels=[7, 8, 9, 11, 12, 13])

A ``Sequence`` is a collection of ordered fields, and differs from ``Array`` and ``GreedyRange`` in that those two are homogenous::

    >>> format = Sequence(PascalString(Byte, "utf8"), GreedyRange(Byte))
    >>> format.build([u"lalaland", [255,1,2]])
    b'\nlalaland\xff\x01\x02'
    >>> format.parse(b"\x004361789432197")
    ['', [52, 51, 54, 49, 55, 56, 57, 52, 51, 50, 49, 57, 55]]

Most constructs can be build into XML and parsed back from XML:

    >>> s = Struct(
    ...    "a" / Int32ul,
    ...    "b" / Int32ul,
    ...    "s" / Struct(
    ...        "c" / Int32ul,
    ...        "d" / Int32ul,
    ...    ),
    ...    )
    >>> data = {"a": 1, "b": 2, "s": {"c": 3, "d": 4}}
    >>> xml = s.toET(obj=data, name="test")
    >>> assert(ET.tostring(xml) == b'<test a="1" b="2"><s c="3" d="4" /></test>')

    >>> s = "test" / Struct(
    ...     "a" / Int32ul,
    ...     "b" / Int32ul,
    ... )
    >>> xml = ET.fromstring(b'<test a="1" b="2" />')
    >>> obj = s.fromET(xml=xml)
    >>> assert(obj == {"a": 1, "b": 2})

However some constructs, like Switch or FocusedSeq have some caveats,
because they use the XML tag name for identifying the corresponding construct.

This is mainly build for easy and quick describing of datastructures with an
easy, human readable and changeable XML representation, rather than completeness of
all possible constructs.
