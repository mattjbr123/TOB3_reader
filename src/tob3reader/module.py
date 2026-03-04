import os
import sys
import numpy as np
import pandas as pd
import datetime as dt


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
            line = str(infile.readline()).strip("b").strip("'").strip("\\r\\n")
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

    value = mantissa * (2**exponent)
    if sign:
        value = -value
    return value


def decode_ulong(data: bytes) -> int:
    """Decode a ULONG (unsigned, 4-byte) little-endian integer"""
    return int.from_bytes(data, byteorder="little")


def decode_long(data: bytes) -> int:
    """Decode a LONG (signed, 4-byte) little-endian integer"""
    return int.from_bytes(data, byteorder="little", signed=True)


def decode_time(data: pd.DataFrame, origin: dt.datetime = dt.datetime(1990, 1, 1)) -> pd.DataFrame:
    """Translate the time information from the TOB1 or TOB3 files into
    something human readable"""
    if "SECONDS" and "NANOSECONDS" in list(data.columns):
        data.index = pd.to_datetime(
            data.loc[:, "SECONDS"] + data.loc[:, "NANOSECONDS"] / 1e9,
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


def read_tob1(filepath: str) -> pd.DataFrame:
    """Reads in TOB1 file and outputs as TOA5 ASCII

    :param filepath: path to the input TOB1 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """

    headerlines, datapos, filesize = read_header(filepath)
    datatypes = headerlines[-1].split(",")
    datatypes = [datatype.strip('"') for datatype in datatypes]
    names = headerlines[1].split(",")
    names = [name.strip('"') for name in names]
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
    datastore.columns = names
    datastore = decode_time(datastore)
    # datastore = process_nans(datastore)

    splits = split30(datastore)
    to_files(splits, headers=headerlines[:-1])

    return datastore


def read_tob3(filepath: str):
    """Reads in TOB3 file and outputs as TOA5 ASCII

    :param filepath: path to the input TOB3 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """


def split30(data: pd.DataFrame) -> list[pd.DataFrame]:
    """Splits a pd dataframe output by read_tob1 or read_tob3 into 30min chunks

    :param data: pd.DataFrame containing time-indexed data
    :type filepath_toa5: str
    :return: DESCRIPTION
    :rtype: TYPE

    """
    data = data.drop(columns=["SECONDS", "NANOSECONDS", "RECORD"], errors="ignore")
    firstfirst = data.index[0].to_pydatetime()
    last = data.index[-1].to_pydatetime()
    if 29 >= firstfirst.minute >= 0:
        nextminute = 30
    elif 59 >= firstfirst.minute >= 30:
        nextminute = 60
    minstonext30 = dt.timedelta(minutes=nextminute - firstfirst.minute)
    next30 = firstfirst + minstonext30
    next30 = dt.datetime(next30.year, next30.month, next30.day, next30.hour, next30.minute, 0, 0) - dt.timedelta(
        microseconds=1
    )

    split_datasets = []
    first = firstfirst
    while first < last:
        split_data = data.loc[first:next30, :]
        if not split_data.empty:
            split_datasets.append(split_data)
        first = next30
        next30 += dt.timedelta(minutes=30)

    return split_datasets


def to_files(splits: list[pd.DataFrame], headers: list[str], outdir: str = ".") -> None:
    """
    Outputs each dataset in splits to separate, time-stamped files in TOA5
    ASCII format
    """
    sitename = headers[0].split(",")[1].strip('"')
    for ds in splits:
        timestamp = ds.index[0].to_pydatetime().strftime("%Y_%m_%d_%H%M")
        outpath = os.path.join(outdir, "TOA5_" + sitename + "_FluxRaw_" + timestamp + ".dat")
        with open(outpath, mode="w") as outfile:
            for line in headers:
                outfile.write(line + "\r\n")
        ds.to_csv(outpath, index=None, header=None, float_format="%.2f", mode="a")  # change nan format to "NAN"

    return


def process_nans(data: pd.DataFrame) -> pd.DataFrame:
    """
    Replace invalid values with NaNs

    :param data: DESCRIPTION
    :type data: pd.DataFrame
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
