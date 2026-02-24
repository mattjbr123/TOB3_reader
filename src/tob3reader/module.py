import os


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
        if datatype == "ULONG":
            bytelen = 8
            linelength += bytelen
            bytelens.append(bytelen)
        elif datatype == "FP2":
            bytelen = 2
            linelength += bytelen
            bytelens.append(bytelen)
    nlines = (filesize - datapos) / linelength

    return bytelens, linelength, nlines


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
