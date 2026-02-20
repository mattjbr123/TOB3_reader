def ftc(filepath: str) -> str:
    """Checks the file type is TOB1 or TOB3

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
        tobtype = topline.split(",")[3:-1]
    if not tobtype in ("TOB1", "TOB3"):
        raise TypeError(filepath + " should be TOB1 or TOB3 format, not " + tobtype)

    return tobtype


def read_tob1(filepath: str):
    """Reads in TOB1 file and outputs as TOA5 ASCII

    :param filepath: path to the input TOB1 datafile
    :type filepath: str

    :return: DESCRIPTION
    :rtype: TYPE

    """


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
