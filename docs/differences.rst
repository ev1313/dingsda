===================
Differences to Construct
===================

DingsDa is a fork of Construct 2.10, which includes some major changes.

The focus is not on speed of parsing or building, but rather for use
in reverse engineering of file formats. Many features aim directly
for simple describing of whole file formats written in and for
other languages, especially in terms of offset/size handling (see Area).

New Features
==========

Preprocessing
---------

Previously when using Rebuilds it was not possible to nest them like this:

```
    f = "F" / Struct(
            "a" / Rebuild(Int32ul, this.b),
            "b" / Rebuild(Int32ul, this.c),
            "c" / Int32ul,
        )

    obj = f.parse(data)
    data = f.build(preprocessed_obj)
```

This works, because preprocess adds for a and b lambdas, which get
resolved after the preprocessing, which adds all of them.

Now before building DingsDa internally calls the preprocess and preprocess_size functions.

The new preprocessing step calls _preprocess and _preprocess_size functions by
default when building. Every construct is now able to determine its size and
this size gets appended in the meta information:

```
    assert(obj.meta("a")._offset == 0)
    assert(obj.meta("a")._size == 12)
    assert(obj.meta("a")._endoffset == 12)
```

Furthermore even pointers get their size determined and appended:

```
    f = "F" / Struct(
            "a" / Pointer(4, Int32ul),
            "b" / Int32ul,
            "c" / Int32ul,
        )

    obj = f.parse(data)
    data = f.build(preprocessed_obj)
    assert(obj.meta("a")._size == 4)
    assert(obj.meta("a")._ptrsize == 4)
```

This information is added in the Containers for every element in dataclasses
(so it is not that RAM intensive like in dictionaries).

After preprocessing Rebuilds also can access these meta attributes.

Area
====

Area is a mix of a Pointer and an Array.

Many file formats use offsets and sizes like this:

```
    fmt = Struct(
        "header1" / Struct(
            "offset" / Rebuild(Int8ul, lambda ctx: ctx._._header2_endoffset), # 0x04
            "size" / Rebuild(Int8ul, lambda ctx: ctx._data1_ptrsize), # 0x04
            "data1" / Area(Int8ul, this.offset, this.size), # 0x01,0x02,0x03,0x04
            ),
        "header2" / Struct(
            "offset" / Rebuild(Int8ul, lambda ctx: ctx._.header1.offset + ctx._.header1.size), # 0x04 + 0x04 = 0x08
            "size" / Rebuild(Int8ul, lambda ctx: ctx._data2_ptrsize), # 0x05
            "data2" / Area(Int8ul, this.offset, this.size), # 0x05,0x06,0x07,0x08,0x09
            )
    )
```

The offsets and sizes of data1 and 2 is only known when building and are dependent of each other.

However the definition for this above is quite straight forward. When parsing, the offsets and sizes get parsed
and Area even checks for their correctness (if a Int32ul gets parsed, although the size is only 2, this throws an error).

When building the Struct the preprocess step of Area adds the ptrsize of the object, which allows the Rebuilds to
calculate the respective positions of data1 and data2 (as they are in this fileformat directly behind each other.

Of course this also works for more complex data formats with Alignment, etc.

XML
===

Many Constructs get a experimental toET and fromET functionality.

This creates from a parsed object Container a XML ElementTree and
can convert the XML ElementTree back to an object Container, which
can in turn be converted back into a bytes stream / file.

This functionality has some hacks built into it, which need
some special "treatment" and care in building the constructs.
It will fail in many special cases, however should work in
all "simple" or "normal" cases.

Special handling includes:

 - Arrays of simple types like FormatFields will be XML Attributes like this:
(the csv module is used for this)

```
 <foo a="2" b="[1,2,3,4]" c="foobar" />
```
 - Switch will add on fromET to the context the parse case.name as _switchid_{name}.
This can be used when Rebuilding the object for determining a type id.
 - IfThenElse as an option called "rebuild_hack" which falls back on fromET to determining the
case not by evaluating, but by the name of the XML Tag. This is necessary in some cases, because the
data determining the branch will be rebuild later from the data itself.

Changed Features
===============

SizeOf
------

Construct provided two different sizeof methods, _sizeof and _actualsize.

_sizeof was essentially just a static size implementation - it did return SizeOf errors
for all the types with unknown lengths.

_actualsize was a helper function used only by LazyArray and LazyStruct for
determining whether the struct can be omitted parsing or not.

In DingsDa there are multiple different types of sizeof:

 - static_sizeof
 - sizeof
 - full_sizeof
 - _expected_sizeof

Static sizeof resembles the classic sizeof of Construct the most. It
returns only for types like FormatField, where the size of the construct
is known before parsing.

Sizeof takes now an extra argument, obj, which is the previously
parsed construct. With the information from the parser object it
can determine for any Construct the actual size. It will fallback to static sizeof,
if not implemented in a Construct.

Full sizeof determines the full size of the Struct, also measuring the sizes of
the Pointers as well by adding _ptrsize up. This is not intended or working as
a "how large will the file be?", but rather as a public method for Pointer types
to get the size of the pointer contents. It will fallback to normal sizeof.

_expected_size is a internal used sizeof replacing _actualsize. It determines
for some special types with prefixed lengths by using the current parsing stream
the expected size of the Construct and moves the stream along by this size.
The fallback of this function is static_sizeof.

Furthermore all Constructs in DingsDa support sizing, if the parsed Container
is provided.

Containers
---------

Construct used a wild mix of dictionaries and Containers for storing the parsed
information. Major speedbumps were the copying of the dictionaries and the nested
copies of the dictionaries (which led to a quite big RAM usage for big, nested datastructures).

DingsDa uses a custom Container and ListContainer datatype, which supports
parenting and stores meta information in dedicated dataclasses. This leads to
a much smaller RAM usage.

Furthermore all the _parse functions will create now a new Container and append this to
the parent Container. Everywhere are only used references instead of deep copying.
The _ and _root attributes are now references, that are handled by the Container/ListContainer:

```
    p = ListContainer([1,2,3])
    c = ListContainer([4,5,6], parent=p)
    p.append(c)
    c2 = ListContainer([7,8,9], parent=c)
    c.append(c2)

    assert(p._ == None)
    assert(p._root is p)
    assert(c._ is p)
    assert(c._root is p)
    assert(c2._ is c)
    assert(c2._root is p)
```

The building step now doesn't modify the Containers / ListContainers at all.

Only the preprocessing step will still modify the Containers / ListContainers for
obvious reasons, however it does also not copy any Containers / ListContainers.

FIXME: add documentation about static / non-static metainformation

FlagsEnum
--------

Previously the following was possible:

```
    d = FlagsEnum(Byte, one=1, two=2, four=4, eight=8)
    assert d.build(255) == b"\xff"
```

However this breaks in dingsda, because of the preprocessing step.
Now it returns:

```
    assert d.build(255) == b"\x0f"
```

As I do not know a clean way to fix this yet, it is documented here.

Removed features
================

All parser and kaitai generators were removed. DingsDa is not interesting in
speed, but rather ease of describing the formats.

Rather than generating parsers in Python or kaitai structs, a
C++ implementation or parser generator of this would be preferred.
But this is not planned currently.

Furthermore the following features were removed:

 - Sequence:
    - These were just Structs but with unnamed fields.
    - This creates problems with the new Container / ListContainer design and is technically not needed.
    - also deletes the legacy >> operator API for creating sequences
    - just create / use Structs now, and name elements you need
 - Select, TryParse: I regard these as bad design and they can't determine their size
 - NamedTuple: I don't see the use of this, and the API seemed bad
