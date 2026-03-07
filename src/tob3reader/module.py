import os
import sys
import numpy as np
import pandas as pd
import datetime as dt
import struct
from bitstring import ConstBitStream


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


def read_header(filepath: str) -> (list[str], int, int, int, str):

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
        if tobtype == "TOB3":
            binheader = infile.read(12)
        else:
            binheader = None
        datapos = infile.tell()
        filesize = infile.seek(0, os.SEEK_END)
    print(headerlines)

    return headerlines, binheader, datapos, filesize, tobtype


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
    """Decode Campbell Scientific INT4 packed byte.
    Bits 0-3: site number (0-15)
    Bit 4: omit flag (measurements being omitted from calculations)
    """
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


def read_tob1(filepath: str, outpath: str = ".") -> pd.DataFrame:
    """Reads in TOB1 file and outputs as pd.DataFrame

    :param filepath: path to the input TOB1 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """

    headerlines, binheader, datapos, filesize, tobtype = read_header(filepath)
    datatypes = headerlines[-1].split(",")
    datatypes = [datatype.strip('"') for datatype in datatypes]
    names = headerlines[1].split(",")
    names = [name.strip('"') for name in names]
    ncols = len(datatypes)
    linelength = 0
    bytelens = []
    for datatype in datatypes:
        print(datatype)
        if datatype in ["ULONG", "LONG", "FP4", "IEEE4", "IEEE4B", "INT4"]:
            bytelen = 4
        elif datatype == "FP2":
            bytelen = 2
        elif datatype in ["IEEE8", "IEEE8B"]:
            bytelen = 8
        else:
            raise TypeError("Unsupported datatype: " + datatype)
        linelength += bytelen
        bytelens.append(bytelen)
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
        if line % 10000 == 0:
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
            elif datatype in ["IEEE4", "IEEE4B"]:
                value = decode_IEEE4(element)
            elif datatype in ["IEEE8", "IEEE8B"]:
                value = decode_IEEE8(element)
            elif datatype == "INT4":
                value = decode_int4(element)
            else:
                raise TypeError("Unsupported datatype: " + datatype)
            datastore[line, b] = value
    datastore = pd.DataFrame(datastore)
    datastore.columns = names
    datastore = decode_time(datastore)
    # datastore = process_nans(datastore)

    splits = split30(datastore)
    to_files(splits, headerlines[:-1], tobtype, outpath)

    return splits


def read_tob3(filepath: str, outpath: str = ".") -> pd.DataFrame:
    """Reads in TOB3 file and outputs as pd.DataFrame

    :param filepath: path to the input TOB1 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """

    headerlines, binheader, datapos, filesize, tobtype = read_header(filepath)
    datatypes = headerlines[-1].split(",")
    datatypes = [datatype.strip(" ").strip('"') for datatype in datatypes]
    filedata = headerlines[1].split(",")
    filedata = [filedatum.strip(" ").strip('"') for filedatum in filedata]
    framesize = int(filedata[2])  # size of each "frame" in the file
    datasize = framesize - 16  # size of the actual data in each "frame"
    names = headerlines[2].split(",")
    names = [name.strip(" ").strip('"') for name in names]
    names.reverse()
    names.append("NANOSECONDS")
    names.append("SECONDS")
    names.reverse()
    ncols = len(datatypes)
    linelength = 0
    bytelens = []
    for datatype in datatypes:
        print(datatype)
        if datatype in ["ULONG", "LONG", "FP4", "IEEE4", "IEEE4B", "INT4"]:
            bytelen = 4
        elif datatype == "FP2":
            bytelen = 2
        elif datatype in ["IEEE8", "IEEE8B"]:
            bytelen = 8
        else:
            raise TypeError("Unsupported datatype: " + datatype)
        linelength += bytelen
        bytelens.append(bytelen)
    nlines_per_frame = datasize / linelength  # usually 1 line per "frame"
    nframes = (filesize - datapos + 12) / (framesize)
    nlines = nframes * nlines_per_frame
    print(nlines_per_frame)
    print(nframes)
    print(nlines)
    assert nlines % 1 == 0  # check it's a whole number
    nlines = int(nlines)
    datastore = np.zeros((nlines, ncols + 2))

    # read in the data element by element
    # first put all the binary date into memory
    with open(filepath, "rb") as infile:
        allfile = infile.read()
    # TOB3 files don't have timestamps for the individual records, instead
    # the timestamp of the first record and the interval OF EACH FRAME is
    # stored in the FRAME headers. So that pandas can easily decode the time of
    # each record, we'll add a timestamp to each record
    frame1secs = decode_ulong(binheader[:4])
    frame1nanos = decode_ulong(binheader[4:8]) * 1e5
    # remove the header
    data = allfile[datapos:]
    startbyte = 0
    recordsecs = frame1secs
    recordnanos = frame1nanos
    for line in range(nlines):
        if line % 10000 == 0:
            progresspc = float(line) / nlines * 100
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
            elif datatype in ["IEEE4", "IEEE4B"]:
                value = decode_IEEE4(element)
            elif datatype in ["IEEE8", "IEEE8B"]:
                value = decode_IEEE8(element)
            elif datatype == "INT4":
                value = decode_int4(element)
            else:
                raise TypeError("Unsupported datatype: " + datatype)
            datastore[line, b + 2] = value
        datastore[line, 0] = recordsecs
        datastore[line, 1] = recordnanos
        # when we reach the end of a frame, update the timestamp of the first
        # line of the frame
        if line % nlines_per_frame == 0:
            startbyte += 4  # skip the frame footer
            # obtain new timestamp info from next frame header
            recordsecs = decode_ulong(data[startbyte : startbyte + 4])
            recordnanos = decode_ulong(data[startbyte + 4 : startbyte + 8]) * 1e5
            if recordsecs + recordnanos / 1e9 < datastore[line, 0] + datastore[line, 1] / 1e9:
                print("Invalid timestamp encountered, probably end of data")
                print("Last valid line: " + str(line))
                break
            elif recordsecs > datastore[line, 0] + 365 * 24 * 60 * 60 * 2:
                print("Timestamp jumped more than 2 years, likely end of data")
                print("Last valid line: " + str(line))
                break
            startbyte += 12  # move to the next frame's data
        # otherwise increment the timestamp by the frequency in the frame head
        # assuming 20Hz for now...
        else:
            # increment the timestamp
            if recordnanos == 950000000:
                recordnanos = 0
                recordsecs += 1
            else:
                recordnanos += 50000000

    # trim trailing zeroes if data ended before file
    datastore = datastore[: line + 1, :]
    # convert to pd.DataFrame
    datastore = pd.DataFrame(datastore)
    datastore.columns = names
    # add timestamp
    datastore = decode_time(datastore)
    # datastore = process_nans(datastore)

    splits = split30(datastore, tobtype)
    to_files(splits, headerlines[:-1], tobtype, outpath)

    return datastore


def split30(data: pd.DataFrame, tobtype: str) -> list[pd.DataFrame]:
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
    if tobtype == "TOB1":
        next30 = dt.datetime(
            next30.year,
            next30.month,
            next30.day,
            next30.hour,
            next30.minute,
            0,
            0,
        ) - dt.timedelta(microseconds=1)
    # TOB3 outputs from CardConvert seem to start from the first record AFTER
    # the halfhour (e.g. 06:00:00.05), and end ON the halfhour, so include the
    # halfour at the end of the file, rather than omitting it for TOB1
    elif tobtype == "TOB3":
        next30 = dt.datetime(
            next30.year,
            next30.month,
            next30.day,
            next30.hour,
            next30.minute,
            0,
            0,
        ) + dt.timedelta(microseconds=49)

    split_datasets = []
    first = firstfirst
    while first < last:
        split_data = data.loc[first:next30, :]
        if not split_data.empty:
            split_datasets.append(split_data)
        first = next30
        next30 += dt.timedelta(minutes=30)

    return split_datasets


def to_files(
    splits: list[pd.DataFrame],
    headers: list[str],
    tobtype: str,
    outdir: str = ".",
) -> None:
    """
    Outputs each dataset in splits to separate, time-stamped files in TOA5
    ASCII format
    """
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    if tobtype == "TOB1":
        sitename = headers[0].split(",")[1].strip('"')
    elif tobtype == "TOB3":
        sitename = headers[0].split(",")[1].strip('"')
        siteno = headers[0].split(",")[3].strip('"')
        auxname = headers[1].split(",")[0].strip('"')
    for ds in splits:
        timestamp = ds.index[0].to_pydatetime().strftime("%Y_%m_%d_%H%M")
        if tobtype == "TOB1":
            outpath = os.path.join(outdir, "TOA5_" + sitename + "_FluxRaw_" + timestamp + ".dat")
        elif tobtype == "TOB3":
            outpath = os.path.join(
                outdir,
                "TOA5_" + siteno + "." + sitename + "_" + auxname + "_" + timestamp + ".dat",
            )
        with open(outpath, mode="w") as outfile:
            for line in headers:
                outfile.write(line + "\r\n")
        print("Outputting to file: " + outpath)
        if tobtype == "TOB1":
            fmt = "%.2f"
        elif tobtype == "TOB3":
            fmt = "%.8f"
        ds.to_csv(outpath, index=None, header=None, float_format=fmt, mode="a")  # change nan format to "NAN"

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
