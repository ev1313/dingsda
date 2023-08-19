from dingsda import Adapter, Construct, TimestampError, BitStruct, Container
from dingsda.numbers import BitsInteger
from dingsda.lib import integertypes, stringtypes


class TimestampAdapter(Adapter):
    """Used internally."""


def Timestamp(subcon, unit, epoch):
    r"""
    Datetime, represented as `Arrow <https://pypi.org/project/arrow/>`_ object.

    Note that accuracy is not guaranteed, because building rounds the value to integer (even when Float subcon is used), due to floating-point errors in general, and because MSDOS scheme has only 5-bit (32 values) seconds field (seconds are rounded to multiple of 2).

    Unit is a fraction of a second. 1 is second resolution, 10**-3 is milliseconds resolution, 10**-6 is microseconds resolution, etc. Usually its 1 on Unix and MacOSX, 10**-7 on Windows. Epoch is a year (if integer) or a specific day (if Arrow object). Usually its 1970 on Unix, 1904 on MacOSX, 1600 on Windows. MSDOS format doesnt support custom unit or epoch, it uses 2-seconds resolution and 1980 epoch.

    :param subcon: Construct instance like Int* Float*, or Int32ub with msdos format
    :param unit: integer or float, or msdos string
    :param epoch: integer, or Arrow instance, or msdos string

    :raises ImportError: arrow could not be imported during ctor
    :raises TimestampError: subcon is not a Construct instance
    :raises TimestampError: unit or epoch is a wrong type

    Example::

        >>> d = Timestamp(Int64ub, 1., 1970)
        >>> d.parse(b'\x00\x00\x00\x00ZIz\x00')
        <Arrow [2018-01-01T00:00:00+00:00]>
        >>> d = Timestamp(Int32ub, "msdos", "msdos")
        >>> d.parse(b'H9\x8c"')
        <Arrow [2016-01-25T17:33:04+00:00]>
    """
    import arrow

    if not isinstance(subcon, Construct):
        raise TimestampError("subcon should be Int*, experimentally Float*, or Int32ub when using msdos format")
    if not isinstance(unit, (integertypes, float, stringtypes)):
        raise TimestampError("unit must be one of: int float string")
    if not isinstance(epoch, (integertypes, arrow.Arrow, stringtypes)):
        raise TimestampError("epoch must be one of: int Arrow string")

    if unit == "msdos" or epoch == "msdos":
        st = BitStruct(
            "year" / BitsInteger(7),
            "month" / BitsInteger(4),
            "day" / BitsInteger(5),
            "hour" / BitsInteger(5),
            "minute" / BitsInteger(6),
            "second" / BitsInteger(5),
        )
        class MsdosTimestampAdapter(TimestampAdapter):
            def _decode(self, obj, context, path):
                return arrow.Arrow(1980,1,1).shift(years=obj.year, months=obj.month-1, days=obj.day-1, hours=obj.hour, minutes=obj.minute, seconds=obj.second*2)
            def _encode(self, obj, context, path):
                t = obj.timetuple()
                return Container(year=t.tm_year-1980, month=t.tm_mon, day=t.tm_mday, hour=t.tm_hour, minute=t.tm_min, second=t.tm_sec//2)
        macro = MsdosTimestampAdapter(st)

    else:
        if isinstance(epoch, integertypes):
            epoch = arrow.Arrow(epoch, 1, 1)
        class EpochTimestampAdapter(TimestampAdapter):
            def _decode(self, obj, context, path):
                return epoch.shift(seconds=obj*unit)
            def _encode(self, obj, context, path):
                return int((obj-epoch).total_seconds()/unit)
        macro = EpochTimestampAdapter(subcon)

    return macro
