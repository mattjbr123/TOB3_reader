import os
import csv
import numpy as np
import pandas as pd
import datetime as dt
from .decoders import *
from .constants import bytelengths


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


def read_header(filepath: str) -> (list[str], int, int, str):

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

    return headerlines, datapos, filesize, tobtype


def read_tob1(filepath: str, outpath: str = ".") -> None:
    """Reads in TOB1 file and outputs as pd.DataFrame

    :param filepath: path to the input TOB1 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """

    headerlines, datapos, filesize, tobtype = read_header(filepath)
    datatypes = headerlines[-1].split(",")
    datatypes = [datatype.strip('"') for datatype in datatypes]
    names = headerlines[1].split(",")
    names = [name.strip('"') for name in names]
    ncols = len(datatypes)
    bytelens = [bytelengths[datatype] for datatype in datatypes]
    linelength = np.asarray(bytelens).sum()
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
            value = decode(element, datatype)
            datastore[line, b] = value
    datastore = pd.DataFrame(datastore)
    datastore.columns = names
    datastore = decode_time(datastore)
    datastore = process_nans(datastore)

    splits = split30(datastore, tobtype)
    to_files(splits, headerlines[:-1], tobtype, outpath)

    return


def read_tob3(filepath: str, outpath: str = ".") -> None:
    """Reads in TOB3 file and outputs as pd.DataFrame

    :param filepath: path to the input TOB1 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """

    headerlines, datapos, filesize, tobtype = read_header(filepath)
    datatypes = headerlines[-1].split(",")
    datatypes = [datatype.strip(" ").strip('"') for datatype in datatypes]
    filedata = headerlines[1].split(",")
    filedata = [filedatum.strip(" ").strip('"') for filedatum in filedata]
    framesize = int(filedata[2])  # size of each "frame" in the file
    datasize = framesize - 16  # size of the actual data in each "frame"
    recordinterval = filedata[1].split(" ")
    if "NSEC" in recordinterval:
        nsecjump = 1 * int(recordinterval[0])
    elif "USEC" in recordinterval:
        nsecjump = 1e3 * int(recordinterval[0])
    elif "MSEC" in recordinterval:
        nsecjump = 1e6 * int(recordinterval[0])
    elif "SEC" in recordinterval:
        nsecjump = 1e9 * int(recordinterval[0])

    nanosunit = filedata[5]  # unit that the nanoseconds info is encoded as
    if nanosunit == "SecMsec":
        nanosmultiplier = 1e6
    elif nanosunit == "Sec100Usec":
        nanosmultiplier = 1e5
    elif nanosunit == "Sec10Usec":
        nanosmultiplier = 1e4
    elif nanosunit == "SecUsec":
        nanosmultiplier = 1e3
    names = headerlines[2].split(",")
    names = [name.strip(" ").strip('"') for name in names]
    names.reverse()
    names.append("NANOSECONDS")
    names.append("SECONDS")
    names.reverse()
    ncols = len(datatypes)
    bytelens = [bytelengths[datatype] for datatype in datatypes]
    linelength = np.asarray(bytelens).sum()
    nlines_per_frame = datasize / linelength  # usually 1 line per "frame"
    nframes = (filesize - datapos) / (framesize)
    nlines = nframes * nlines_per_frame
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
    data = allfile[datapos:]
    frame1secs = decode(data[:4], "ULONG")
    frame1nanos = decode(data[4:8], "ULONG") * nanosmultiplier
    startbyte = 12
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
            value = decode(element, datatype)
            datastore[line, b + 2] = value
        datastore[line, 0] = recordsecs
        datastore[line, 1] = recordnanos
        # when we reach the end of a frame, update the timestamp of the first
        # line of the frame
        if line % nlines_per_frame == 0:
            startbyte += 4  # skip the frame footer
            # obtain new timestamp info from next frame header
            recordsecs = decode(data[startbyte : startbyte + 4], "ULONG")
            recordnanos = decode(data[startbyte + 4 : startbyte + 8], "ULONG") * nanosmultiplier
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
        else:
            # increment the timestamp
            if recordnanos == 950000000:
                recordnanos = 0
                recordsecs += 1
            else:
                recordnanos += nsecjump

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

    return


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
            linecount = 1
            for line in headers:
                linecopy = line
                if tobtype == "TOB1":
                    linecopy = linecopy.replace("TOB1", "TOA5")
                    linecopy = linecopy.replace('"SECONDS","NANOSECONDS","RECORD",', "")
                    linecopy = linecopy.replace('"SECONDS","NANOSECONDS","RN",', "")
                    linecopy = linecopy.replace('"","","",', "")
                elif tobtype == "TOB3":
                    linecopy = linecopy.replace("TOB3", "TOA5")
                if tobtype == "TOB3" and linecount == 2:
                    pass
                else:
                    outfile.write(linecopy + "\r\n")
                linecount += 1
        print("Outputting to file: " + outpath)
        if tobtype == "TOB1":
            fmt = "%.2f"
        elif tobtype == "TOB3":
            fmt = "%.8f"
        ds.to_csv(
            outpath,
            index=None,
            header=None,
            float_format=fmt,
            na_rep='"NAN"',
            quoting=csv.QUOTE_NONE,
            mode="a",
        )

    return


def process_nans(data: pd.DataFrame) -> pd.DataFrame:
    """
    Replace invalid values with NaNs

    :param data: DESCRIPTION
    :type data: pd.DataFrame
    :return: DESCRIPTION
    :rtype: TYPE

    """
    data = data.where(data != -8190)
    return data


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
