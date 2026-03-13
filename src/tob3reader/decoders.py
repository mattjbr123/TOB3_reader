import struct
import pandas as pd
import datetime as dt


def decode(data: bytes, datatype: str) -> int | float:
    if datatype == "ULONG":
        value = decode_ulong(data)
    elif datatype == "LONG":
        value = decode_long(data)
    elif datatype == "FP4":
        value = decode_fp4(data)
    elif datatype == "FP2":
        value = decode_fp2(data)
    elif datatype in ["IEEE4", "IEEE4B"]:
        value = decode_IEEE4(data)
    elif datatype in ["IEEE8", "IEEE8B"]:
        value = decode_IEEE8(data)
    elif datatype == "INT4":
        value = decode_int4(data)
    else:
        raise TypeError("Unsupported datatype: " + datatype)
    return value


def decode_fp2(data: bytes) -> float:
    """Decode a Campbell Scientific FP2 two-byte float."""

    raw = int.from_bytes(data, byteorder="big")

    sign = (raw >> 15) & 0x01  # bit 15
    exponent = (raw >> 13) & 0x03  # bits 14-13
    mantissa = (raw >> 0) & 0x1FFF  # bits 12-0

    value = mantissa * (10**-exponent)
    if sign:
        value = -value
    return value


def decode_fp4(data: bytes) -> float:
    """Decode a Campbell Scientific FP4 four-byte float."""

    raw = int.from_bytes(data, byteorder="big")

    sign = (raw >> 31) & 0x01  # bit 31
    exponent = (raw >> 24) & 0x7F  # bits 30-24
    mantissa = (raw >> 0) & 0xFFFFFF  # bits 23-0

    value = mantissa * (2**exponent)
    if sign:
        value = -value
    return value


def decode_IEEE4(data: bytes) -> float:
    """Decode a standard IEEE4 four-byte float."""

    value = struct.unpack_from(">f", data)[0]
    return value


def decode_IEEE8(data: bytes) -> float:
    """Decode a standard IEEE8 eight-byte float."""

    value = struct.unpack_from(">d", data)[0]
    return value


def decode_ulong(data: bytes) -> int:
    """Decode a ULONG (unsigned, 4-byte) little-endian integer"""
    return int.from_bytes(data, byteorder="little")


def decode_long(data: bytes) -> int:
    """Decode a LONG (signed, 4-byte) little-endian integer"""
    return int.from_bytes(data, byteorder="little", signed=True)


def decode_int4(data: bytes) -> int:
    """Decode Campbell Scientific INT4 packed byte."""
    return int.from_bytes(data, signed=True)


def decode_time(data: pd.DataFrame, origin: dt.datetime = dt.datetime(1990, 1, 1)) -> pd.DataFrame:
    """Translate the time information from the TOB1 or TOB3 files into
    something human readable"""
    if "SECONDS" and "NANOSECONDS" in list(data.columns):
        data.index = pd.to_datetime(
            data.loc[:, "SECONDS"] + data.loc[:, "NANOSECONDS"] / 1e9,
            unit="s",
            origin=origin,
        )
    elif "SECONDS" in list(data.columns):
        data.index = pd.to_datetime(
            data.loc[:, "SECONDS"],
            unit="s",
            origin=origin,
        )
    else:
        raise IndexError(
            "At least one of SECONDS and NANOSECONDS not "
            + "present in data. Cannot establish unique time coords."
            + "Data headers are: "
            + str(list(data.columns))
        )
    return data
