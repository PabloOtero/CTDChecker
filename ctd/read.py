import bz2
import gzip
import linecache
import re
import warnings
import zipfile
from datetime import datetime
from io import StringIO
from pathlib import Path
from flask import flash
import lxml.etree as ET
import numpy as np
import pandas as pd
#flash_messages = False


import config
if config.RUN_LOCALLY:
    flash_messages = False
else:
    flash_messages = True


def _basename(fname):
    """Return file name without path."""
    if not isinstance(fname, Path):
        fname = Path(fname)
    path, name, ext = fname.parent, fname.stem, fname.suffix
    return path, name, ext


def _normalize_names(name):
    name = name.strip()
    name = name.strip("*")
    return name


def _open_compressed(fname):
    extension = fname.suffix.lower()
    if extension in [".gzip", ".gz"]:
        cfile = gzip.open(str(fname))
    elif extension == ".bz2":
        cfile = bz2.BZ2File(str(fname))
    elif extension == ".zip":
        # NOTE: Zip format may contain more than one file in the archive
        # (similar to tar), here we assume that there is just one file per
        # zipfile!  Also, we ask for the name because it can be different from
        # the zipfile file!!
        zfile = zipfile.ZipFile(str(fname))
        name = zfile.namelist()[0]
        cfile = zfile.open(name)
    else:
        raise ValueError(
            "Unrecognized file extension. Expected .gzip, .bz2, or .zip, got {}".format(
                extension
            )
        )
    contents = cfile.read()
    cfile.close()
    return contents


def _read_file(fname):
    if not isinstance(fname, Path):
        fname = Path(fname).resolve()

    extension = fname.suffix.lower()
    if extension in [".gzip", ".gz", ".bz2", ".zip"]:
        contents = _open_compressed(fname)
    elif extension in [".cnv", ".edf", ".txt", ".ros", ".btl"]:
        contents = fname.read_bytes()
    else:
        if flash_messages:
            flash('Unrecognized file extension. Expected .cnv, .edf, .txt, .ros, or .btl got' + extension, "danger")        
        raise ValueError(
            f"Unrecognized file extension. Expected .cnv, .edf, .txt, .ros, or .btl got {extension}"
        )
    # Read as bytes but we need to return strings for the parsers.
    text = contents.decode(encoding="utf8", errors="replace")
    return StringIO(text)


def _parse_seabird(lines, ftype="cnv", fname=None):

    # Initialize variables.
    # lon = lat = time = depth = cruise = station = None, None, None, None, None, None
    lon = lat = time = depth = cruise = station = instrument = message_lat = message_lon = message_depth = None
    nmea_lat = False
    nmea_lon = False
    skiprows = 0

    metadata = {}
    header, config, names = [], [], []
     
    for k, line in enumerate(lines):
        line = line.strip()

        # Only cnv has columns names, for bottle files we will use the variable row.
        if ftype == "cnv":
            if "# name" in line:
                name, unit = line.split("=")[1].split(":")
                name, unit = list(map(_normalize_names, (name, unit)))
                names.append(name)

        # Seabird headers starts with *.
        if line.startswith("*"):
            header.append(line)

        # Seabird configuration starts with #.
        if line.startswith("#"):
            config.append(line)

        # NMEA position and time.
        if "NMEA Lat".casefold() in line.casefold():
            hemisphere = line[-1]
            lat = line.strip(hemisphere).split("=")[1].strip()
            # delimiter = re.findall("[=:]", line)
            # lat = line.strip(hemisphere).split(delimiter[0])[1].strip()
            lat = np.float_(lat.split())
            nmea_lat = True
            if hemisphere == "S":
                lat = -(lat[0] + lat[1] / 60.0)
            elif hemisphere == "N":
                lat = lat[0] + lat[1] / 60.0
            else:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + ' Latitude not recognized in header file', "danger")
                raise ValueError("Latitude not recognized in header file.")

        if "NMEA Lon".casefold() in line.casefold():
            hemisphere = line[-1]
            lon = line.strip(hemisphere).split("=")[1].strip()
            lon = np.float_(lon.split())
            nmea_lon = True
            if hemisphere == "W":
                lon = -(lon[0] + lon[1] / 60.0)
            elif hemisphere == "E":
                lon = lon[0] + lon[1] / 60.0
            else:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + ' Longitude not recognized in header file', "danger")
                raise ValueError("Longitude not recognized in header file.")

        # If NMEA position does not exit, take that indicated by the techcnician
        #
        # This info is usually hand-copied and not always follows the same
        # structure, for example:
        # St3     43 24820
        # St4     43.24971
        # St6     43 23.18N   --> Only this should be valid
        # St8     43.606
        #
        # Option A)  if degrees and minutes are space-separated, we assume minutes
        # are sexagesimal 43 23.18N (valid) 43 78.18N (invalid)
        #   Option A1) Minutes contain decimal point
        #   Option A2) Decimal point is not present.
        #
        # Option B) if only one number we assume that info was copied from the
        # the vessel screen and precision is usually 5 digits. In this case, the number
        # is a float:
        #   Option B.1) The decimal (point) is present.
        #   Option B.2) The decimal is NOT present. Then, first two digits are
        #   the int part and the rest are the decimal part.

        if ("Latitude:".casefold() in line.casefold() or "Latitud:".casefold() in line.casefold()) and nmea_lat is False:

            if len(line.split(":")) != 2:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + ' Latitude not recognized. Check unneccesary existence of symbol '':'' in header file', "danger")
                raise ValueError(
                    "Latitude not recognized. Check unneccesary existence of symbol ':' in header file"
                )                

            
            #Strip and replace many spaces by one
            old_value = (
                line.split(":")[1]
                .strip()
                .lstrip("0")
            )
            old_value = ' '.join(old_value.split())
            
            
            # Replace commas by dots as decimal separator
            # Remove space before hemisphere symbol
            lat = old_value
            lat = lat.replace(",", ".").replace("n", "N").replace("s", "S")
            lat = lat.replace(" N","N").replace(" S", "S")

            # Check hemisphere
            try:
                hemisphere = lat[-1]
                signus = lat[0]
            except:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + ' Latitude not recognized', "danger")
                raise ValueError("Latitude not recognized.")
                
                           
            if not hemisphere.isalpha():
                if signus == "-":
                    lat = lat[1:]
                    hemisphere = "S"
                else:
                    hemisphere = "N"
            else:
                if signus == "-":
                    if flash_messages:
                        flash('<code>File ' + fname + '</code>'
                              + ' Latitude not recognized. Minus signus and hemisphere letter coexist', "danger")
                    raise ValueError(
                        "Latitude not recognized. Minus signus and hemisphere letter coexist."
                    )
            lat = lat.strip(hemisphere)

            if len(lat.split()) == 2:
                # Option A2: 43 23 means 43 23N
                #            43 234 means 43.234 and therefore 43 14.04N
                lat = lat.split()
                if "." not in lat[1]:
                    if len(lat[1]) > 2:
                        lat[1] = float(lat[1]) / float("1".ljust(len(lat[1]) + 1, "0"))
                    else:
                        if float(lat[1]) >= 60:
                            if flash_messages:
                                flash('<code>File ' + fname + '</code>' + ' Latitude not recognized. Minutes exceed 60', "danger")
                            raise ValueError(
                                "Latitude not recognized. Minutes exceed 60."
                            )
                        lat[1] = float(lat[1]) / 60.0
                else:
                    if float(lat[1]) < 100:
                        lat[1] = float(lat[1]) / 60.0
                    else:
                        if flash_messages:
                            flash('<code>File ' + fname + '</code>' + ' Latitude not recognized. Revise minutes', "danger")
                        raise ValueError(
                            "Latitude not recognized. Revise minutes."
                        )                        
                lat = np.float_(lat)
            elif len(lat.split()) == 1:
                # Option B1) A number in the style 42.5364
                if "." in lat:
                    lat = divmod(float(lat), 1)
                # Option B2) A number in the style 425364 means 42.5364
                else:
                    if len(lat) < 7:
                        print(
                            "WARNING! Check latitude degrees are really ",
                            lat[0:2],
                            "and not ",
                            lat[0],
                        )
                        if flash_messages:
                            flash('<code>File ' + fname + '</code>' 
                                  + ' Check latitude degrees are really '
                                  + lat[0:2]
                                  + ' and not '
                                  + lat[0], "warning")
                    degrees = lat[0:2]
                    minutes = lat[2:]
                    minutes = float(minutes) / float("1".ljust(len(minutes) + 1, "0"))
                    lat = np.float_([degrees, minutes])
            else:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>' 
                          + ' Latitude not recognized', "danger")
                raise ValueError("Latitude not recognized")

            # Compare old and new values. Assume '43 35.95 N' and '43 35.95N' are identical
            new_value = (
                str(int(lat[0]))
                + " "
                + str("{:>05.2f}".format(lat[1] * 60))
                + hemisphere
            )

            # Show message if old and new value differ in degrees or the first
            # two decimals of minutes
            idx_twodec = new_value.index('.') + 2            
            if old_value[:idx_twodec] != new_value[:idx_twodec]:
                print("   Modifying LAT from " + old_value + " to " + new_value)
                message_lat = 'Modifying LAT from ' + old_value + ' to ' + new_value
            # if old_value != new_value and old_value[:-2] + old_value[-1] != new_value:
            #     print("   LAT from: " + old_value + " to: " + new_value)
            #     message_lat = 'LAT from ' + old_value + ' to ' + new_value

            if hemisphere == "S":
                lat = -(lat[0] + lat[1])
            elif hemisphere == "N":
                lat = lat[0] + lat[1]
            else:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>' 
                          + ' Latitude not recognized', "danger")
                raise ValueError("Latitude not recognized.")

            if lat < -90 or lat > 90:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>' 
                          + ' Latitude impossible, must be in the range -90 to 90', "danger")
                raise ValueError("Latitude impossible.")

        if ("Longitude:".casefold() in line.casefold() or "Longitud:".casefold() in line.casefold()) and nmea_lon is False:

            if len(line.split(":")) != 2:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + ' Longitude not recognized. Check unneccesary existence of symbol '':'' in header file', "danger")
                raise ValueError(
                    "Longitude not recognized. Check unneccesary existence of symbol ':' in header file"
                ) 
            
            old_value = (
                line.split(":")[1]
                .strip()
                .lstrip("0")
            )
            old_value = ' '.join(old_value.split())
            
            # Replace commas by dots as decimal separator
            lon = old_value
            lon = lon.replace(",", ".").replace("e", "E").replace("w", "W")
            lon = lon.replace(" E","E").replace(" W", "W")
 
            try:
                hemisphere = lon[-1]
                signus = lon[0]
            except:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + ' Longitude not recognized', "danger")
                raise ValueError("Longitude not recognized.")            

            if not hemisphere.isalpha():
                if signus == "-":
                    lon = lon[1:]
                    hemisphere = "W"
                else:
                    hemisphere = "E"
            else:
                if signus == "-":
                    if flash_messages:
                        flash('<code>File ' + fname + '</code>'
                              + ' Longitude not recognized. Minus signus and hemisphere letter coexist', "danger")
                    raise ValueError(
                        "Longitude not recognized. Minus signus and hemisphere letter coexist."
                    )
            lon = lon.strip(hemisphere)

            if len(lon.split()) == 2:
                # Option A2: 43 23 means 43 23N
                #            43 234 means 43.234 and therefore 43 14.04N
                lon = lon.split()
                if "." not in lon[1]:
                    if len(lon[1]) > 2:
                        lon[1] = float(lon[1]) / float("1".ljust(len(lon[1]) + 1, "0"))
                    else:
                        if float(lon[1]) >= 60:
                            if flash_messages:
                                flash('<code>File ' + fname + '</code>'
                                      + ' Longitude not recognized. Minutes exceed 60', "danger")
                            raise ValueError(
                                "Longitude not recognized. Minutes exceed 60."
                            )
                        lon[1] = float(lon[1]) / 60.0
                else:
                    lon[1] = float(lon[1]) / 60.0
                lon = np.float_(lon)
            elif len(lon.split()) == 1:
                # Option B1) A number in the style 42.5364
                if "." in lon:
                    lon = divmod(float(lon), 1)
                # Option B2) A number in the style 425364 means 42.5364
                else:
                    if len(lon) < 7:
                        print(
                            "WARNING! Check longitude degrees are really ",
                            lon[0:2],
                            " and not ",
                            lon[0],
                            " or ",
                            lon[0:3],
                        )
                        if flash_messages:
                            flash('<code>File ' + fname + '</code>' 
                                  + ' Check longitude degrees are really '
                                  + lon[0:2]
                                  + ' and not '
                                  + lon[0], "warning")
                    degrees = lon[0:2]
                    minutes = lon[2:]
                    minutes = float(minutes) / float("1".ljust(len(minutes) + 1, "0"))
                    lon = np.float_([degrees, minutes])
            else:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + ' Longitude not recognized', "danger")
                raise ValueError("Longitude not recognized")

            # Compare old and new values. Assume '43 35.95 N' and '43 35.95N' are identical
            new_value = (
                str(int(lon[0]))
                + " "
                + str("{:>05.2f}".format(lon[1] * 60))
                + hemisphere
            )
            
            idx_twodec = new_value.index('.') + 2            
            if old_value[:idx_twodec] != new_value[:idx_twodec]:
                print("   Modifying LON from " + old_value + " to " + new_value)
                message_lat = 'Modifying LON from ' + old_value + ' to ' + new_value
            
            # if old_value != new_value and old_value[:-2] + old_value[-1] != new_value:
            #     print("   LON from: " + old_value + " to: " + new_value)
            #     message_lon = 'LON from ' + old_value + ' to ' + new_value

            if hemisphere == "W":
                lon = -(lon[0] + lon[1])
            elif hemisphere == "E":
                lon = lon[0] + lon[1]
            else:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>' +
                          ' Longitude not recognized', "danger")
                raise ValueError("Longitude not recognized.")

            if lon < -180 or lon > 180:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + 'Longitude impossible. Must be in the range -180 to 180', "danger")
                raise ValueError("Longitude impossible.")

        if (
            "Depth:".casefold() in line.casefold()
            or "Depth (m):".casefold() in line.casefold()
            or "Profundidad:".casefold() in line.casefold()
        ):
            try:
                depth = line.split(":")[-1].replace('m','').strip().replace('.',' ').split()[0]
            except:
                depth = ''
                print('INFO: Depth not found in cruise header')
                message_depth = ' Depth not found in cruise header'

        if (
            "Cruise:".casefold() in line.casefold()
            or "** Campa".casefold() in line.casefold()
            or "** Survey".casefold() in line.casefold()
        ):
            cruise = line.split(":")[-1].strip()

        if (
            "Station:".casefold() in line.casefold()
            or "** Estaci".casefold() in line.casefold()
        ):
            station = line.split(":")[-1].strip()

        if (
            "* SBE".casefold() in line.casefold()
        ):
            try:
                instrument = line.split("*")[-1].strip()
            except:
                instrument = ''
                print('WARNING: Type of instrument could not be retrieved from file')
                if flash_messages:
                    flash('<code>File ' + fname + '</code>'
                          + ' Type of instrument could not be retrieved from file', "warning")
                pass
                    

        # cnv file header ends with *END* while
        if ftype == "cnv":
            if line == "*END*":
                skiprows = k + 1
                break
        else:  # btl.
            # There is no *END* like in a .cnv file, skip two after header info.
            if not (line.startswith("*") | line.startswith("#")):
                # Fix commonly occurring problem when Sbeox.* exists in the file
                # the name is concatenated to previous parameter
                # example:
                #   CStarAt0Sbeox0Mm/Kg to CStarAt0 Sbeox0Mm/Kg (really two different params)
                line = re.sub(r"(\S)Sbeox", "\\1 Sbeox", line)

                names = line.split()
                skiprows = k + 2
                break

    if not header:
        print("Header not in file")
        if flash_messages:
            flash('<code>File ' + fname + '</code>' + ' ' + 'Header not in file. Header in SBE files starts with *', "danger")   
    if not config:
        print("Configuration section not in file")
        if flash_messages:
            flash('<code>File ' + fname + '</code>' + ' ' + 'Configuration not in file. Configuration section in SBE files starts with #', "danger")          
    if not names:
        print("Variable names not in file")
        if flash_messages:
            flash('<code>File ' + fname + '</code>' + ' ' + 'Could not read variable names', "danger")          
        
    # Check time. Time is preferrable obtained from:
    #       1) NMEA Time
    #       2) System Upload Time
    #       3) <startTime> tag when CTD is in XML format
    #       4) Date and time present in header and typed by technician
    timestring = ["NMEA UTC", "System UpLoad Time"]
    for target in timestring:
        line = [line for line in header if target in line]
        if line:
            time = line[0].split("=")[-1].strip().replace('dic','dec')
            try:
                time = datetime.strptime(time, "%b %d %Y %H:%M:%S")
            except ValueError:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>' + ' Invalid date or time', "danger")
                raise ValueError("Invalid date or time")

    if time is None:
        line = [line for line in header if "<startTime>" in line]
        if line:
            time = line[0].split("<startTime>")[-1].split("</startTime>")[0].strip()
            try:
                time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                if flash_messages:
                    flash('<code>File ' + fname + '</code>' + ' Invalid date or time', "danger")
                raise ValueError("Invalid date or time")

    if time is None:
        day, hour = None, None
        line = [line for line in header if " Date".casefold() in line.casefold()]
        if line:
            day = line[0].split(":")[-1].replace("-", "/").strip()
        line = [line for line in header if " Time UTC".casefold() in line.casefold()]
        if line:
            hour = line[0].split(":", 1)[-1].strip()
        try:
            if day is not None and hour is not None:
                time = day + " " + hour
                time = datetime.strptime(time, "%d/%m/%Y %H:%M")
                print(
                        "Warning! Time deducted. Check that date is really ",
                        time.strftime("%B %d, %Y"),
                )
                if flash_messages:
                    flash('<code>File ' + fname + '</code>' + ' Time deducted. Check that date is really ' + time.strftime("%B %d, %Y"), "warning")
        except ValueError:
            if flash_messages:
                    flash('<code>File ' + fname + '</code>' + ' Invalid date or time', "danger")
            raise ValueError("Invalid date or time")

    if time is None:
        if flash_messages:
            flash('<code>File ' + fname + '</code>' + ' ' + 'Cannot retrieve time from file', "danger")
        raise ValueError("Time not in file") 
                  
    if lon is None:
        if flash_messages:
            flash('<code>File ' + fname + '</code>' + ' Longitude not readable from file', "danger")
        raise ValueError("Longitude not readable from file")
            
    if lat is None:
        if flash_messages:
            flash('<code>File ' + fname + '</code>' + ' Latitude not readable from file', "danger")        
        raise ValueError("Latitude not readable from file")            


    if flash_messages:
        if message_lat is not None:
            flash('<code>File ' + fname + '</code>' + ' ' + message_lat, "warning")
        if message_lon is not None:
            flash('<code>File ' + fname + '</code>' + ' ' + message_lon, "warning")
        if message_depth is not None:
            flash('<code>File ' + fname + '</code>' + ' ' + message_depth, "warning")

    if ftype == "btl":
        # Capture stat names column.
        names.append("Statistic")
    
         
    metadata.update(
        {
            "header": "\n".join(header),
            "config": "\n".join(config),
            "names": names,
            "skiprows": skiprows,
            "time": time,
            "lon": lon,
            "lat": lat,
            "depth": depth,
            "cruise": cruise,
            "station": station,
            "instrument": instrument,
        }
    )
    return metadata


def from_bl(fname):
    """Read Seabird bottle-trip (bl) file

    Example
    -------
    >>> from pathlib import Path
    >>> import ctd
    >>> data_path = Path(__file__).parents[1].joinpath("tests", "data")
    >>> df = ctd.from_bl(str(data_path.joinpath('bl', 'bottletest.bl')))
    >>> df._metadata["time_of_reset"]
    datetime.datetime(2018, 6, 25, 20, 8, 55)

    """
    df = pd.read_csv(
        fname,
        skiprows=2,
        parse_dates=[1],
        index_col=0,
        names=["bottle_number", "time", "startscan", "endscan"],
    )
    df._metadata = {
        "time_of_reset": pd.to_datetime(
            linecache.getline(str(fname), 2)[6:-1]
        ).to_pydatetime()
    }
    return df


def from_btl(fname):
    """
    DataFrame constructor to open Seabird CTD BTL-ASCII format.

    Examples
    --------
    >>> from pathlib import Path
    >>> import ctd
    >>> data_path = Path(__file__).parents[1].joinpath("tests", "data")
    >>> bottles = ctd.from_btl(data_path.joinpath('btl', 'bottletest.btl'))

    """
    f = _read_file(fname)
    metadata = _parse_seabird(f.readlines(), ftype="btl")

    f.seek(0)

    df = pd.read_fwf(
        f,
        header=None,
        index_col=False,
        names=metadata["names"],
        parse_dates=False,
        skiprows=metadata["skiprows"],
    )
    f.close()

    # At this point the data frame is not correctly lined up (multiple rows
    # for avg, std, min, max or just avg, std, etc).
    # Also needs date,time,and bottle number to be converted to one per line.

    # Get row types, see what you have: avg, std, min, max or just avg, std.
    rowtypes = df[df.columns[-1]].unique()
    # Get times and dates which occur on second line of each bottle.
    dates = df.iloc[:: len(rowtypes), 1].reset_index(drop=True)
    times = df.iloc[1 :: len(rowtypes), 1].reset_index(drop=True)
    datetimes = dates + " " + times

    # Fill the Date column with datetimes.
    df.loc[:: len(rowtypes), "Date"] = datetimes.values
    df.loc[1 :: len(rowtypes), "Date"] = datetimes.values

    # Fill missing rows.
    df["Bottle"] = df["Bottle"].fillna(method="ffill")
    df["Date"] = df["Date"].fillna(method="ffill")

    df["Statistic"] = df["Statistic"].str.replace(r"\(|\)", "")  # (avg) to avg

    name = _basename(fname)[1]

    dtypes = {
        "bpos": int,
        "pumps": bool,
        "flag": bool,
        "Bottle": int,
        "Scan": int,
        "Statistic": str,
        "Date": str,
    }
    for column in df.columns:
        if column in dtypes:
            df[column] = df[column].astype(dtypes[column])
        else:
            try:
                df[column] = df[column].astype(float)
            except ValueError:
                warnings.warn("Could not convert %s to float." % column)

    df["Date"] = pd.to_datetime(df["Date"])
    metadata["name"] = str(name)
    setattr(df, "_metadata", metadata)
    return df


def from_edf(fname):
    """
    DataFrame constructor to open XBT EDF ASCII format.

    Examples
    --------
    >>> from pathlib import Path
    >>> import ctd
    >>> data_path = Path(__file__).parents[1].joinpath("tests", "data")
    >>> cast = ctd.from_edf(data_path.joinpath('XBT.EDF.gz'))
    >>> ax = cast['temperature'].plot_cast()

    """
    f = _read_file(fname)
    header, names = [], []
    for k, line in enumerate(f.readlines()):
        line = line.strip()
        if line.startswith("Serial Number"):
            serial = line.strip().split(":")[1].strip()
        elif line.startswith("Latitude"):
            try:
                hemisphere = line[-1]
                lat = line.strip(hemisphere).split(":")[1].strip()
                lat = np.float_(lat.split())
                if hemisphere == "S":
                    lat = -(lat[0] + lat[1] / 60.0)
                elif hemisphere == "N":
                    lat = lat[0] + lat[1] / 60.0
            except (IndexError, ValueError):
                lat = None
        elif line.startswith("Longitude"):
            try:
                hemisphere = line[-1]
                lon = line.strip(hemisphere).split(":")[1].strip()
                lon = np.float_(lon.split())
                if hemisphere == "W":
                    lon = -(lon[0] + lon[1] / 60.0)
                elif hemisphere == "E":
                    lon = lon[0] + lon[1] / 60.0
            except (IndexError, ValueError):
                lon = None
        else:
            header.append(line)
            if line.startswith("Field"):
                col, unit = [l.strip().lower() for l in line.split(":")]
                names.append(unit.split()[0])
        if line == "// Data":
            skiprows = k + 1
            break

    f.seek(0)
    df = pd.read_csv(
        f,
        header=None,
        index_col=None,
        names=names,
        skiprows=skiprows,
        delim_whitespace=True,
    )
    f.close()

    df.set_index("depth", drop=True, inplace=True)
    df.index.name = "Depth [m]"
    name = _basename(fname)[1]

    metadata = {
        "lon": lon,
        "lat": lat,
        "name": str(name),
        "header": "\n".join(header),
        "serial": serial,
    }
    setattr(df, "_metadata", metadata)
    return df


def from_cnv(fname):
    """
    DataFrame constructor to open Seabird CTD CNV-ASCII format.

    Examples
    --------
    >>> from pathlib import Path
    >>> import ctd
    >>> data_path = Path(__file__).parents[1].joinpath("tests", "data")
    >>> cast = ctd.from_cnv(data_path.joinpath('CTD_big.cnv.bz2'))
    >>> downcast, upcast = cast.split()
    >>> ax = downcast['t090C'].plot_cast()

    """
    
    f = _read_file(fname)
    try:
        metadata = _parse_seabird(f.readlines(), ftype="cnv", fname=fname.name)
    except:
        raise ValueError(
            "Could not parse cnv file"
        )        

    # Pandas may fail with duplicate names
    unique = []
    for elem in metadata["names"]:
        if elem not in unique:
            unique.append(elem)             
        else:
            count = unique.count(elem)
            unique.append(elem + '.' + str(count))
    metadata["names"] = unique

    f.seek(0)
    # df = pd.read_fwf(
    #     f,
    #     header=None,
    #     index_col=None,
    #     names=metadata["names"],
    #     skiprows=metadata["skiprows"],
    #     delim_whitespace=True,
    #     skip_blank_lines=True,
    #     widths=[11] * len(metadata["names"]),
    # )
    df = pd.read_table(
        f,
        header=None,
        index_col=None,
        names=metadata["names"],
        skiprows=metadata["skiprows"],
        delim_whitespace=True,
        skip_blank_lines=True
    )
    
    
    f.close()

    key_set = False
    prkeys = ["prDM", "prdM", "pr", "prSM"]
    for prkey in prkeys:
        try:
            df.set_index(prkey, drop=True, inplace=True)
            key_set = True
        except KeyError:
            continue
    if not key_set:
        if flash_messages:
            flash('Could not find pressure field (supported names are ' + prkeys + ')', "danger")
        raise KeyError(f"Could not find pressure field (supported names are {prkeys}).")
    df.index.name = "Pressure [dbar]"

    name = _basename(fname)[1]

    #Replace blank values (white space) with nan in pandas
    df = df.replace(r'^\s*$', np.nan, regex=True)

    dtypes = {"bpos": int, "pumps": bool, "flag": bool}
    for column in df.columns:
        if column in dtypes:        
            df[column] = df[column].astype(dtypes[column])
        else:
            try:
                df[column] = df[column].astype(float)
            except ValueError:
                print('Problem reading', column, 'column in file', fname.name)
                print('Tip: Check that all data in this column are numbers and \n' +
                      'that data are well aligned among columns')
                if flash_messages:
                    flash('Problem reading ' + column + 'column in file' + fname.name + '\n'
                          + 'Tip: Check that all data in this column are numbers and that data are well aligned among columns', "danger")
                warnings.warn("Could not convert %s to float." % column)

    metadata["name"] = str(name)
    setattr(df, "_metadata", metadata)
    return df


def from_fsi(fname, skiprows=9):
    """
    DataFrame constructor to open Falmouth Scientific, Inc. (FSI) CTD
    ASCII format.

    Examples
    --------
    >>> from pathlib import Path
    >>> import ctd
    >>> data_path = Path(__file__).parents[1].joinpath("tests", "data")
    >>> cast = ctd.from_fsi(data_path.joinpath('FSI.txt.gz'))
    >>> downcast, upcast = cast.split()
    >>> ax = downcast['TEMP'].plot_cast()

    """
    f = _read_file(fname)
    df = pd.read_csv(
        f,
        header="infer",
        index_col=None,
        skiprows=skiprows,
        dtype=float,
        delim_whitespace=True,
    )
    f.close()

    df.set_index("PRES", drop=True, inplace=True)
    df.index.name = "Pressure [dbar]"
    metadata = {"name": str(fname)}
    setattr(df, "_metadata", metadata)
    return df


def rosette_summary(fname):
    """
    Make a BTL (bottle) file from a ROS (bottle log) file.

    More control for the averaging process and at which step we want to
    perform this averaging eliminating the need to read the data into SBE
    Software again after pre-processing.
    NOTE: Do not run LoopEdit on the upcast!

    Examples
    --------
    >>> from pathlib import Path
    >>> import ctd
    >>> data_path = Path(__file__).parents[1].joinpath("tests", "data")
    >>> fname = data_path.joinpath('CTD/g01l01s01.ros')
    >>> ros = ctd.rosette_summary(fname)
    >>> ros = ros.groupby(ros.index).mean()
    >>> ros.pressure.values.astype(int)
    array([835, 806, 705, 604, 503, 404, 303, 201, 151, 100,  51,   1])

    """
    ros = from_cnv(fname)
    ros["pressure"] = ros.index.values.astype(float)
    ros["nbf"] = ros["nbf"].astype(int)
    ros.set_index("nbf", drop=True, inplace=True, verify_integrity=False)
    return ros


def parse_csr(fname):

    """
    csr = {}
    (
        custodian_code,
        custodian_contact,
        originator_code,
        originator_contact,
        pointofcontact_code,
        pointofcontact_contact,
        cruise_name,
        cruise_id,
        chief_scientist,
        water_body,
        cruise_time,
        cruise_location,
        acquisition_center,
        vessel_name,
        project_acronym,
        
    ) = ([], [], [], [], [], [], [], [], [], [], [], [], [], [], [])
    """

    csr = dict.fromkeys([
        "custodian_code",
        "custodian_contact",
        "custodian_name",
        "originator_code",
        "originator_contact",
        "pointofcontact_code",
        "pointofcontact_contact",
        "cruise_name",
        "cruise_id",
        "chief_scientist",
        "water_body",
        "cruise_time",
        "cruise_location",
        "acquisition_center",
        "vessel_name",
        "project_acronym",
        "project_code",
        "project_description"
    ], None)

    
    custodian_code = custodian_contact = custodian_name = originator_code = originator_contact = \
    pointofcontact_code = pointofcontact_contact = cruise_name = cruise_id = \
    chief_scientist = water_body = cruise_time = cruise_location = acquisition_center = \
    vessel_name = project_acronym = project_code = project_description = None     

    tree = ET.parse(
        str(fname.absolute())
    )  # modify to str to deal with pathlib.Path objects
    root = tree.getroot()
      
    try:
        full_path = "{http://www.isotc211.org/2005/gmd}contact/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}organisationName/{http://www.seadatanet.org}SDN_EDMOCode"
        custodian_code = root.find(full_path).get("codeListValue")
    except:
        print('WARNING: Cannot retrieve custodian EDMO code from CSR file')
        if flash_messages:
            flash('Cannot retrieve custodian EDMO code from CSR file', "warning")        

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}contact/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}organisationName/{http://www.seadatanet.org}SDN_EDMOCode"
        custodian_name = root.find(full_path).text
    except:
        print('WARNING: Cannot retrieve custodian EDMO name from CSR file')
        if flash_messages:
            flash('Cannot retrieve custodian EDMO name from CSR file', "warning")  

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}contact/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}contactInfo/"               
        node = root.find(full_path)
        custodian_contact =  ET.tostring(node, encoding="unicode", method="xml")    
        idx_start = custodian_contact.find(' ')
        idx_end = custodian_contact.find('>')
        custodian_contact = custodian_contact.replace(custodian_contact[idx_start:idx_end],'').rstrip("\n").rstrip()
        #Sometimes add unexpected content to the node. We made his to secure the finding
        idx_end = custodian_contact.find('</gmd:CI_Contact>')
        custodian_contact = custodian_contact.replace(custodian_contact[idx_end+17:],'').rstrip("\n").rstrip()
    except:
        print('WARNING: Cannot retrieve custodian contact information from CSR file')
        if flash_messages:
            flash('Cannot retrieve custodian contact information from CSR file', "warning")

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}citation/{http://www.isotc211.org/2005/gmd}CI_Citation/{http://www.isotc211.org/2005/gmd}citedResponsibleParty/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}organisationName/{http://www.seadatanet.org}SDN_EDMOCode"
        originator_code = root.find(full_path).get("codeListValue")
    except:
        print('WARNING: Cannot retrieve originator EDMO code from CSR file')
        if flash_messages:
            flash('Cannot retrieve originator EDMO code from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}citation/{http://www.isotc211.org/2005/gmd}CI_Citation/{http://www.isotc211.org/2005/gmd}citedResponsibleParty/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}contactInfo/{http://www.isotc211.org/2005/gmd}CI_Contact"
        node = root.find(full_path)
        originator_contact =  ET.tostring(node, encoding="unicode", method="xml")
        idx_start = originator_contact.find(' ')
        idx_end = originator_contact.find('>')
        originator_contact = originator_contact.replace(originator_contact[idx_start:idx_end],'').rstrip("\n").rstrip()
        #Sometimes add unexpected content to the node. We made his to secure the finding
        idx_end = originator_contact.find('</gmd:CI_Contact>')
        originator_contact = originator_contact.replace(originator_contact[idx_end+17:],'').rstrip("\n").rstrip()
    except:
        print('WARNING: Cannot retrieve originator contact information from CSR file')
        if flash_messages:
            flash('Cannot retrieve originator contact information from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}citation/{http://www.isotc211.org/2005/gmd}CI_Citation/{http://www.isotc211.org/2005/gmd}citedResponsibleParty/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}organisationName/{http://www.seadatanet.org}SDN_EDMOCode"        
        pointofcontact_code = root.find(full_path).get("codeListValue")
    except:
        print('WARNING: Cannot retrieve point of contact EDMO code from CSR file')
        if flash_messages:
            flash('Cannot retrieve point of contact EDMO code from CSR file', "warning") 
        
    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}pointOfContact/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}contactInfo/{http://www.isotc211.org/2005/gmd}CI_Contact"        
        node = root.find(full_path)
        pointofcontact_contact =  ET.tostring(node, encoding="unicode", method="xml")             
        idx_start = pointofcontact_contact.find(' ')
        idx_end = pointofcontact_contact.find('>')
        pointofcontact_contact = pointofcontact_contact.replace(pointofcontact_contact[idx_start:idx_end],'').rstrip("\n").rstrip()
        #Sometimes add unexpected content to the node. We made his to secure the finding
        idx_end = pointofcontact_contact.find('</gmd:CI_Contact>')
        pointofcontact_contact = pointofcontact_contact.replace(pointofcontact_contact[idx_end+17:],'').rstrip("\n").rstrip()    
    except:
        print('WARNING: Cannot retrieve point of contact information from CSR file')
        if flash_messages:
            flash('Cannot retrieve point of contact information from CSR file', "warning") 
        
    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}citation/{http://www.isotc211.org/2005/gmd}CI_Citation/{http://www.isotc211.org/2005/gmd}title/{http://www.isotc211.org/2005/gco}CharacterString"        
        cruise_name = root.find(full_path).text
    except:
        print('WARNING: Cannot retrieve cruise name from CSR file')
        if flash_messages:
            flash('Cannot retrieve cruise name from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}citation/{http://www.isotc211.org/2005/gmd}CI_Citation/{http://www.isotc211.org/2005/gmd}alternateTitle/{http://www.isotc211.org/2005/gco}CharacterString"
        cruise_id = root.find(full_path).text
    except:
        print('WARNING: Cannot retrieve Cruise ID from CSR file')
        if flash_messages:
            flash('Cannot retrieve Cruise ID from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}pointOfContact/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}individualName/{http://www.isotc211.org/2005/gco}CharacterString"        
        chief_scientist = root.find(full_path).text.upper()
    except:
        print('WARNING: Cannot retrieve name of chief scientist from CSR file')
        if flash_messages:
            flash('Cannot retrieve name of chief scientist from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}descriptiveKeywords/{http://www.isotc211.org/2005/gmd}MD_Keywords/{http://www.isotc211.org/2005/gmd}keyword/{http://www.seadatanet.org}SDN_WaterBodyCode"
        water_body = root.find(full_path).text
    except:
        print('WARNING: Cannot retrieve water body from CSR file')
        if flash_messages:
            flash('Cannot retrieve water body from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}extent/{http://www.isotc211.org/2005/gmd}EX_Extent/{http://www.isotc211.org/2005/gmd}temporalElement/{http://www.isotc211.org/2005/gmd}EX_TemporalExtent/{http://www.isotc211.org/2005/gmd}extent/{http://www.opengis.net/gml}TimePeriod/{http://www.opengis.net/gml}beginPosition"
        time_start = root.find(full_path)
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}extent/{http://www.isotc211.org/2005/gmd}EX_Extent/{http://www.isotc211.org/2005/gmd}temporalElement/{http://www.isotc211.org/2005/gmd}EX_TemporalExtent/{http://www.isotc211.org/2005/gmd}extent/{http://www.opengis.net/gml}TimePeriod/{http://www.opengis.net/gml}endPosition"
        time_end = root.find(full_path)
        if time_start is not None and time_end is not None:
            time_start = datetime.strptime(time_start.text[0:10], "%Y-%m-%d").strftime(
                "%d/%m/%Y"
            )
            time_end = datetime.strptime(time_end.text[0:10], "%Y-%m-%d").strftime(
                "%d/%m/%Y"
            )
            cruise_time = time_start + "-" + time_end
    except:
        print('WARNING: Cannot retrieve temporal coverage from CSR file')
        if flash_messages:
            flash('Cannot retrieve temporal coverage from CSR file', "warning") 
        
    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}extent/{http://www.isotc211.org/2005/gmd}EX_Extent/{http://www.isotc211.org/2005/gmd}geographicElement/{http://www.isotc211.org/2005/gmd}EX_GeographicBoundingBox/{http://www.isotc211.org/2005/gmd}westBoundLongitude/{http://www.isotc211.org/2005/gco}Decimal"
        west_bound = root.find(full_path)
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}extent/{http://www.isotc211.org/2005/gmd}EX_Extent/{http://www.isotc211.org/2005/gmd}geographicElement/{http://www.isotc211.org/2005/gmd}EX_GeographicBoundingBox/{http://www.isotc211.org/2005/gmd}eastBoundLongitude/{http://www.isotc211.org/2005/gco}Decimal"
        east_bound = root.find(full_path)
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}extent/{http://www.isotc211.org/2005/gmd}EX_Extent/{http://www.isotc211.org/2005/gmd}geographicElement/{http://www.isotc211.org/2005/gmd}EX_GeographicBoundingBox/{http://www.isotc211.org/2005/gmd}southBoundLatitude/{http://www.isotc211.org/2005/gco}Decimal"
        south_bound = root.find(full_path)
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}extent/{http://www.isotc211.org/2005/gmd}EX_Extent/{http://www.isotc211.org/2005/gmd}geographicElement/{http://www.isotc211.org/2005/gmd}EX_GeographicBoundingBox/{http://www.isotc211.org/2005/gmd}northBoundLatitude/{http://www.isotc211.org/2005/gco}Decimal"
        north_bound = root.find(full_path)
        cruise_location = [south_bound.text, north_bound.text, west_bound.text, east_bound.text]
    except:
        print('WARNING: Cannot retrieve bounding box from CSR file')
        if flash_messages:
            flash('Cannot retrieve bounding box from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}citation/{http://www.isotc211.org/2005/gmd}CI_Citation/{http://www.isotc211.org/2005/gmd}citedResponsibleParty/{http://www.isotc211.org/2005/gmd}CI_ResponsibleParty/{http://www.isotc211.org/2005/gmd}organisationName/{http://www.seadatanet.org}SDN_EDMOCode"
        acquisition_center = root.find(full_path).text
    except:
        print('WARNING: Cannot retrieve acquisition center from CSR file')
        if flash_messages:
            flash('Cannot retrieve acquisition center from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}descriptiveKeywords/{http://www.isotc211.org/2005/gmd}MD_Keywords/{http://www.isotc211.org/2005/gmd}keyword/{http://www.seadatanet.org}SDN_PlatformCode"
        vessel_name = root.find(full_path).text
    except:
        print('WARNING: Cannot retrieve vessel name from CSR file')
        if flash_messages:
            flash('Cannot retrieve vessel name from CSR file', "warning") 

    try:
        full_path = "{http://www.isotc211.org/2005/gmd}identificationInfo/{http://www.seadatanet.org}SDN_DataIdentification/{http://www.isotc211.org/2005/gmd}descriptiveKeywords/{http://www.isotc211.org/2005/gmd}MD_Keywords/{http://www.isotc211.org/2005/gmd}keyword/{http://www.seadatanet.org}SDN_EDMERPCode"
        project_element = root.find(full_path)
        #if project_element is not None:
        project_description = project_element.text
        project_acronym = project_element.text.split('{acronym="')[1].split('"')[0]
        project_code = project_element.attrib["codeListValue"]
    except:
        print('WARNING: Cannot retrieve complete project information from CSR file')
        if flash_messages:
            flash('Cannot retrieve complete project information from CSR file', "warning") 
        project_description = ''
        project_acronym = ''
        project_code = ''
        

    csr.update(
        {
            "custodian_code": custodian_code,
            "custodian_contact": custodian_contact,
            "custodian_name": custodian_name,
            "originator_code": originator_code,
            "originator_contact": originator_contact,
            "pointofcontact_code": pointofcontact_code,
            "pointofcontact_contact": pointofcontact_contact,
            "cruise_name": cruise_name,
            "cruise_id": cruise_id,
            "chief_scientist": chief_scientist,
            "water_body": water_body,
            "cruise_time": cruise_time,
            "cruise_location": cruise_location,
            "acquisition_center": acquisition_center,
            "vessel_name": vessel_name,
            "project_acronym": project_acronym,
            "project_code": project_code,
            "project_description": project_description,
        }
    )

    return csr


def cnv_CorrectHeader(filename):
    """ Parse a cnv file and correct/modify geoposition in the header
    
    Header in Sea Bird CTD post processed data (*.cnv files) contains lat and 
    lon as registered by the technician. This info is usually from the screens 
    in the vessel. However, the various technicians not always copy this info 
    following the same structure, for example: 
        St3     43 24820
        St4     43.24971
        St6     43 23.180N   --> Only this one is valid
        St8     43.606
    
    This script also removes empty lines.
    
    """

    if filename.suffix == ".cnv":

        with open(filename, "r") as infile:
            data = infile.readlines()  # read a list of lines

            # Remove empty lines in header
            data = [x for x in data if x != "\n"]

            count = 0
            for line in data:
                count += 1
                line = line.rstrip()  # remove '\n' at end of line
                if "Latitude:" in line:
                    param, value = line.split(":", 1)

                    old_value = value

                    value = value.lstrip()

                    # remove letter at the end to reduce the number of formats
                    if value.endswith(("N", "n")):
                        value = value[:-1]
                    elif value.endswith(("S", "s")):
                        value = "-" + value[:-1]

                    value = value.replace(".", " ").split()

                    grados = int(value[0])
                    if grados > -90 and grados < 90:
                        grados = "{1:0{0}d}".format(
                            2 if int(value[0]) >= 0 else 3, int(value[0])
                        )
                    else:
                        print("Impossibe latitude in file " + filename.name)
                        exit()

                    if len(value) == 3:
                        if 0 <= int(value[1]) < 100:
                            minutos = (
                                str(int(value[1])).zfill(2)
                                + "."
                                + "{:<03d}".format(int(value[2]))
                            )
                        else:
                            print("Impossibe latitude in file " + filename.name)
                            exit()
                    else:
                        # IMPORTANT: we assume that the precision on the vessel screen is 5 digits
                        # and sometimes technician forgets to write zeros to right
                        minutos = "{:<05d}".format(int(value[1]))
                        # and now, we reformat to keep precision to 5 digits
                        minutos = "{:>05d}".format(int(int(minutos) * 60 / 100))
                        minutos = minutos[0:2] + "." + minutos[2:5]

                    if int(grados) > 0:
                        new_value = grados + " " + minutos + "N"
                    else:
                        new_value = grados[1:] + " " + minutos + "S"

                    if old_value != new_value:
                        data[count - 1] = param + ":" + new_value + "\n"
                        print("Correcting position in " + filename.name)
                        print("   From: " + old_value + " To: " + new_value)

                if "Longitude:" in line:
                    param, value = line.split(":", 1)

                    old_value = value

                    value = value.lstrip()

                    # remove letter at the end to reduce the number of formats
                    # IMPORTANT: we assume that if no letter is present is to the West
                    # more common in IEO surveys
                    if value.endswith(("E", "e")):
                        value = value[:-1]
                    elif value.endswith(("W", "w")) or (
                        value.endswith("") and value.startswith("-") == False
                    ):
                        value = "-" + value[:-1]

                    value = value.replace(".", " ").split()

                    grados = int(value[0])
                    if grados > -180 and grados < 180:
                        grados = "{1:0{0}d}".format(
                            3 if int(value[0]) >= 0 else 4, int(value[0])
                        )
                    else:
                        print("Impossibe longitude in file " + filename.name)
                        exit()

                    if len(value) == 3:
                        if 0 <= int(value[1]) < 100:
                            minutos = (
                                str(int(value[1])).zfill(2)
                                + "."
                                + "{:<03d}".format(int(value[2]))
                            )
                        else:
                            print("Impossibe longitude in file " + filename.name)
                            exit()
                    else:
                        # IMPORTANT: we assume that the precision on the vessel screen is 5 digits
                        # and sometimes technician forgets to write zeros to right
                        minutos = "{:<05d}".format(int(value[1]))
                        # and now, we reformat to keep precision to 5 digits
                        minutos = "{:>05d}".format(int(int(minutos) * 60 / 100))
                        minutos = minutos[0:2] + "." + minutos[2:5]

                    if int(grados) > 0:
                        new_value = grados + " " + minutos + "E"
                    else:
                        new_value = grados[1:] + " " + minutos + "W"

                    if old_value != new_value:
                        data[count - 1] = param + ":" + new_value + "\n"
                        print("Correcting position in " + filename.name)
                        print("   From: " + old_value + " To: " + new_value)

        with open(filename, "w") as outfile:
            outfile.writelines(data)
    else:
        print("Not a CNV file")
    return

"""
    Load CSR file and parse it
"""
def load_csr(tmpdir):
    path = Path(tmpdir)
    csrfile = list(path.glob('*.xml'))
    if len(csrfile) == 0:
        print('No CSR file in directory')
        if flash_messages:
            flash('No xml (CSR) file found', "error")
        #exit()
        return None
    elif len(csrfile) == 1:
        csrfile=csrfile[0]
        csr = parse_csr(csrfile)
        print('CSR parsed')
        if flash_messages:
            flash("CSR parsed", "success")
    else:
        print('More than one xml (CSR) file found')
        if flash_messages:
            flash('More than one xml (CSR) file found', "error")
        #exit()
        return None
    return csr  
