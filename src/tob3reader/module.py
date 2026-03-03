import os
import sys
import numpy as np
import pandas as pd


def ftc(filepath: str) -> str:
    """Checks and returns file type if TOB1 or TOB3, errors otherwise

    Parameters
    ----------
    filepath : str
        path to the input data file.

    Returns
    -------
    tobtype : str
        File type. TOB1 or TOB3

    """

    with open(filepath, "rb") as testfile:
        topline = str(testfile.readline())
        tobtype = topline[3:7]
    if not tobtype in ("TOB1", "TOB3"):
        raise TypeError(filepath + " should be TOB1 or TOB3 format, not " + tobtype)

    return tobtype


def read_header(filepath: str) -> (list[str], int, int):

    tobtype = ftc(filepath)
    if tobtype == "TOB1":
        nhlines = 5
    elif tobtype == "TOB3":
        nhlines = 6

    with open(filepath, "rb") as infile:
        headerlines = []
        for nline in range(nhlines):
            line = str(infile.readline()).strip("b").strip("'")
            headerlines.append(line)
        datapos = infile.tell()
        filesize = infile.seek(0, os.SEEK_END)
    print(headerlines)

    return headerlines, datapos, filesize


def read_body(filepath: str) -> list:

    tobtype = ftc(filepath)
    if tobtype == "TOB1":
        nhlines = 5
    elif tobtype == "TOB3":
        nhlines = 6

    with open(filepath, "rb") as infile:
        alllines = infile.readlines()
        body = alllines[nhlines:]

    return body


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

    print("Decoding FP4")
    raw = int.from_bytes(data, byteorder="big")

    sign = (raw >> 31) & 0x01  # bit 31
    exponent = (raw >> 24) & 0x7F  # bits 30-24
    mantissa = (raw >> 0) & 0xFFFFFF  # bits 23-0

    value = mantissa * (2**exponent)  ## EXPONENT MAY BE NEGATIVE. DOCS UNCLEAR
    if sign:
        value = -value
    return value


def decode_ulong(data: bytes) -> int:
    """Decode a ULONG (unsigned, 4-byte) little-endian integer"""
    return int.from_bytes(data, byteorder="little")


def decode_long(data: bytes) -> int:
    """Decode a LONG (signed, 4-byte) little-endian integer"""
    return int.from_bytes(data, byteorder="little", signed=True)


def decode_time(data: int):
    """Translate the time information from the TOB1 or TOB3 files into
    something human readable"""
    pass
    return


def read_tob1(filepath: str):
    """Reads in TOB1 file and outputs as TOA5 ASCII

    :param filepath: path to the input TOB1 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """

    headerlines, datapos, filesize = read_header(filepath)
    datatypes = headerlines[-1][:-4].split(",")
    datatypes = [datatype.strip('"') for datatype in datatypes]
    ncols = len(datatypes)
    linelength = 0
    bytelens = []
    for datatype in datatypes:
        print(datatype)
        if datatype == "ULONG" or datatype == "LONG" or datatype == "FP4":
            bytelen = 4
            linelength += bytelen
            bytelens.append(bytelen)
        elif datatype == "FP2":
            bytelen = 2
            linelength += bytelen
            bytelens.append(bytelen)
        else:
            raise TypeError("Unsupported datatype: " + datatype)
    nlines = (filesize - datapos) / linelength
    assert nlines % 1 == 0  # check it's a whole number
    nlines = int(nlines)
    datastore = np.zeros((nlines, ncols))

    # read in the data element by element
    # first put all the binary date into memory
    with open(filepath, "rb") as infile:
        allfile = infile.read()
    # remove the header
    data = allfile[datapos:]
    startbyte = 0
    totaldatapoints = datastore.size
    for line in range(nlines):
        progresspc = float(line) * len(bytelens) / totaldatapoints * 100
        print("Progress: " + str(progresspc) + "%")
        for b in range(len(bytelens)):
            bytelen = bytelens[b]
            datatype = datatypes[b]
            # read the next x bytes and put it in the empty data array
            element = data[startbyte : startbyte + bytelen]
            startbyte += bytelen
            if datatype == "ULONG":
                value = decode_ulong(element)
            elif datatype == "LONG":
                value = decode_long(element)
            elif datatype == "FP4":
                value = decode_fp4(element)
            elif datatype == "FP2":
                value = decode_fp2(element)
            else:
                raise TypeError("Unsupported datatype: " + datatype)
            datastore[line, b] = value
    datastore = pd.DataFrame(datastore)

    return datastore


def read_tob3(filepath: str):
    """Reads in TOB3 file and outputs as TOA5 ASCII

    :param filepath: path to the input TOB3 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """


def split30(filepath_toa5: str):
    """Splits a TOA5 file output by read_tob1 or read_tob3 into 30min chunks

    :param filepath_toa5: path to input TOA5 file
    :type filepath_toa5: str
    :return: DESCRIPTION
    :rtype: TYPE

    """


# def add_int(x: int, y: int) -> int:
#   """Adds two integers together
#
#    Args:
#        x: The first number
#        y: The second number
#
#    Returns:
#        int: The result
#    """
#
#    return x + y
