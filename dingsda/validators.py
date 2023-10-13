from dingsda.errors import ValidationError
from dingsda.adapters import Adapter, SymmetricAdapter, ExprSymmetricAdapter

class Validator(SymmetricAdapter):
    r"""
    Abstract class that validates a condition on the encoded/decoded object.

    Needs to implement `_validate()` that returns a bool (or a truthy value)

    :param subcon: Construct instance
    """
    def _decode(self, obj, context, path):
        if not self._validate(obj, context, path):
            raise ValidationError("object failed validation: %s" % (obj,), path=path)
        return obj

    def _validate(self, obj, context, path):
        raise NotImplementedError


class ExprValidator(Validator):
    r"""
    Generic adapter that takes `validator` lambda as parameter. You can use ExprValidator instead of writing a full-blown class deriving from Validator when only a simple lambda is needed.

    :param subcon: Construct instance, subcon to adapt
    :param validator: lambda that takes (obj, context) and returns a bool

    Example::

        >>> d = ExprValidator(Byte, obj_ & 0b11111110 == 0)
        >>> d.build(1)
        b'\x01'
        >>> d.build(88)
        ValidationError: object failed validation: 88

    """
    def __init__(self, subcon, validator):
        super().__init__(subcon)
        self._validate = lambda obj,ctx,path: validator(obj,ctx)


def OneOf(subcon, valids):
    r"""
    Validates that the object is one of the listed values, both during parsing and building.

    .. note:: For performance, `valids` should be a set or frozenset.

    :param subcon: Construct instance, subcon to validate
    :param valids: collection implementing __contains__, usually a list or set

    :raises ValidationError: parsed or build value is not among valids

    Example::

        >>> d = OneOf(Byte, [1,2,3])
        >>> d.parse(b"\x01")
        1
        >>> d.parse(b"\xff")
        dingsda.core.ValidationError: object failed validation: 255
    """
    return ExprValidator(subcon, lambda obj,ctx: obj in valids)


def NoneOf(subcon, invalids):
    r"""
    Validates that the object is none of the listed values, both during parsing and building.

    .. note:: For performance, `valids` should be a set or frozenset.

    :param subcon: Construct instance, subcon to validate
    :param invalids: collection implementing __contains__, usually a list or set

    :raises ValidationError: parsed or build value is among invalids

    """
    return ExprValidator(subcon, lambda obj,ctx: obj not in invalids)


def Filter(predicate, subcon):
    r"""
    Filters a list leaving only the elements that passed through the predicate.

    :param subcon: Construct instance, usually Array GreedyRange
    :param predicate: lambda that takes (obj, context) and returns a bool

    Can propagate any exception from the lambda, possibly non-ConstructError.

    Example::

        >>> d = Filter(obj_ != 0, Byte[:])
        >>> d.parse(b"\x00\x02\x00")
        [2]
        >>> d.build([0,1,0,2,0])
        b'\x01\x02'
    """
    return ExprSymmetricAdapter(subcon, lambda obj,ctx: [x for x in obj if predicate(x,ctx)])


class Slicing(Adapter):
    r"""
    Adapter for slicing a list. Works with GreedyRange.

    :param subcon: Construct instance, subcon to slice
    :param count: integer, expected number of elements, needed during building
    :param start: integer for start index (or None for entire list)
    :param stop: integer for stop index (or None for up-to-end)
    :param step: integer, step (or 1 for every element)
    :param empty: object, value to fill the list with, during building

    Example::

        d = Slicing(Array(4,Byte), 4, 1, 3, empty=0)
        assert d.parse(b"\x01\x02\x03\x04") == [2,3]
        assert d.build([2,3]) == b"\x00\x02\x03\x00"
        assert d.sizeof() == 4
    """
    def __init__(self, subcon, count, start, stop, step=1, empty=None):
        super().__init__(subcon)
        self.count = count
        self.start = start
        self.stop = stop
        self.step = step
        self.empty = empty

    def _decode(self, obj, context, path):
        return obj[self.start:self.stop:self.step]

    def _encode(self, obj, context, path):
        if self.start is None:
            return obj
        elif self.stop is None:
            output = [self.empty] * self.count
            output[self.start::self.step] = obj
        else:
            output = [self.empty] * self.count
            output[self.start:self.stop:self.step] = obj
        return output


class Indexing(Adapter):
    r"""
    Adapter for indexing a list (getting a single item from that list). Works with Range and their lazy equivalents.

    :param subcon: Construct instance, subcon to index
    :param count: integer, expected number of elements, needed during building
    :param index: integer, index of the list to get
    :param empty: object, value to fill the list with, during building

    Example::

        d = Indexing(Array(4,Byte), 4, 2, empty=0)
        assert d.parse(b"\x01\x02\x03\x04") == 3
        assert d.build(3) == b"\x00\x00\x03\x00"
        assert d.sizeof() == 4
    """
    def __init__(self, subcon, count, index, empty=None):
        super().__init__(subcon)
        self.count = count
        self.index = index
        self.empty = empty

    def _decode(self, obj, context, path):
        return obj[self.index]

    def _encode(self, obj, context, path):
        output = [self.empty] * self.count
        output[self.index] = obj
        return output

