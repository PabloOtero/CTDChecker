import csv
from PIL import Image
from fpdf import FPDF
import json
import pkg_resources
import math
from pathlib import Path
import numpy as np
from datetime import datetime
import warnings

def load_mapping_SBEtoP09():
    try:
        # If cfg is available in ctd, use it
        mapping = json.loads(pkg_resources.resource_string("ctd", "SBEtoP09.json"))
        return mapping
    except:
        warnings.warn("Could not load mapping between SBE variables and P09 vocabulary")

def load_mapping_P09toP01():
    try:
        # If cfg is available in ctd, use it
        mapping = json.loads(pkg_resources.resource_string("ctd", "P09toP01.json"))
        return mapping
    except:
        warnings.warn("Could not load mapping between P09 variables and P01 vocabulary")

def to_cnv_flagged(df, metadata, output_file):
    """ Write a taylor-made cnv file, formatted to facilitate the input in 
       NEMO software (SeaDataNet). Column names follow SeaDataNet convention
       and FLAGS are included.
       
       Input: - Dataframe obtained from a previous read with 'from_cnv'
              - metadata info as obatined with 'from_cnv'
              - output file including the route
    """

    # Find missing values in original data previous to any reformat
    try:
        lines=metadata['config']
        matched_lines = [line for line in lines.split('\n') if "bad_flag" in line]    
        if matched_lines:
            bad_flag = matched_lines[0].split("=")[1].strip()
    except:
        pass
    
    for column in df.columns:
        if column != "FLAGS":
            totalnum = []
            decimals = []
            kk = df[column].to_string(index=False).replace(' ', '').split("\n")
            for element in kk:
                integral, fractional = (
                    element.split(".") if "." in element else (element, "")
                )
                totalnum.append(len(element))
                decimals.append(len(fractional))
            maxprec = max(decimals)
            # Output from SeaBird has 11 characters for each variable
            # df[column] = df[column].map(lambda x: '{:>{width}.{prec}f}'.format(x, width=11, prec=maxprec) )
            df[column] = df[column].map(lambda x: "{:.{prec}f}".format(x, prec=maxprec))
            if bad_flag:           
                df[column] = df[column].replace('nan',bad_flag, regex=True)

    if "FLAGS" in df.columns:
        # df.iloc[:,-1] = df.iloc[:,-1].map(lambda x: '{:>11}'.format(x.replace(" ", "")) )
        df.iloc[:, -1] = df.iloc[:, -1].map(lambda x: "{:}".format(x.replace(" ", "")))

    # Use it if you want to insert spaces in the first column
    # df_formatted.insert(0, 'tabulation', '    ')

    with open(output_file, "w", encoding="utf8", newline="") as outfile:
        # Insert configuration info before last row
        header = metadata["header"]
        outfile.write(header[: header.rfind("\n")] + "\n")
        outfile.write(metadata["config"] + "\n")
        outfile.write("*END*\n")
        # df.to_csv(outfile, sep='\t', header=False, index=False, quoting=csv.QUOTE_NONE)
        df.to_csv(outfile, header=False, index=False, quoting=csv.QUOTE_NONE)
    return


def to_cnv_medatlas(df, metadata, output_file, edmo_code):
    """ Write a *.dat file, formatted following MEDATLAS format and SeaDataNet
        conventions
       
       Input: - Dataframe obtained from a previous read with 'from_cnv'
              - metadata info as obtained with 'from_cnv'
              - output file including the route
              - EDMO code from custodian organization
    """

    mapping_P01_dict = json.loads(pkg_resources.resource_string("ctd", "P09toP01.json"))


    # Find missing values in original data previous to any reformat
    try:
        lines=metadata['config']
        matched_lines = [line for line in lines.split('\n') if "bad_flag" in line]    
        if matched_lines:
            bad_flag = float(matched_lines[0].split("=")[1].strip())
            df = df.replace(bad_flag, np.nan)
    except:
        pass
         
    # Remove previous index and prevent include it in a new column
    df = df.reset_index(drop=True)

    # Format values
    for column in df.columns:
        if column != "FLAGS":

            fractional = mapping_P01_dict[column]["fractional_part"]

            if column == "PRES":
                # MedAtlas format adds one space to pressure 
                #(to hold minus sign in default value)
                width = min(len(str(df[column].max()).strip()), 4) + 1
                df[column] = df[column].map(
                    lambda x: "{:>{width}d}".format(
                        x, width=width
                    )
                )
            else:
                totalint = []
                decimals = []
                
                df.loc[df[column].notnull(), column].to_string(index=False).replace(' ', '').split("\n")
                
                kk = df.loc[df[column].notnull(), column].to_string(index=False).replace(' ', '').split("\n")
                for n, element in enumerate(kk):
                    #Skip column names
                    # if n > 0:
                    #     to_left, to_right = (
                    #         element.split(".") if "." in element else (element, "")
                    #     )
                    #     totalint.append(len(to_left))
                    #     decimals.append(len(to_right))
                    to_left, to_right = (
                            element.split(".") if "." in element else (element, "")
                        )
                    totalint.append(len(to_left))
                    decimals.append(len(to_right))

                fractional = min(max(decimals), fractional)
                whole = max(totalint)
                
                if fractional == 0:
                    width = whole
                else:
                    width = whole + fractional + 1   
                df.loc[df[column].notnull(), column] = df.loc[df[column].notnull(), column].map(
                    lambda x: "{:{width}.{frac}f}".format(x, width=width, frac=fractional)
                )

                
    # Add default values at the end. First append a new row
    width = len(str(df["PRES"].iloc[-1]))
    new_row = {"PRES": "{:.{width}}".format("-9999", width=width)}
    df = df.append(new_row, ignore_index=True)

    
    for column in df.columns:
        if column != "PRES":        
            last_value = max(df[column][df[column].notnull()])
            number = last_value.strip().split(".") if "." in element else (element, "")
            integral = len(number[0])
            if len(number) == 1:
                df.iloc[-1, df.columns.get_loc(column)] = "{:9>{width}}".format(
                    "9", width=integral
                )
            else:
                fractional = len(number[1])
                df.iloc[-1, df.columns.get_loc(column)] = (
                    "{:9>{width}}".format("9", width=integral)
                    + "."
                    + "{:9>{width}}".format("9", width=fractional)
                )
    
    # Change flags for those missing values
    if matched_lines:
        for column_index, variable in enumerate(df.keys()):
            # Change flag to 9 if a NaN is present
            s = list(df['FLAGS'][df[variable].isnull()])
            new_s = []
            for idx, element in enumerate(s):
                numbers_in_flag = list(element)
                numbers_in_flag[column_index] = '9'
                new_s.append(''.join(numbers_in_flag))
            df['FLAGS'][df[variable].isnull()] = new_s
            # And modify the NaN value for MedAtlas format (last line)
            df[variable] = df[variable].fillna(df.iloc[-1][variable])

    # Octopus software warns about lines with all values missing with exception
    # of the reference value. If 
    df = df[df['FLAGS'] != '1'+(len(df.columns)-2)*'9']
    
    # Use it if you want to insert spaces in the first column
    # df_formatted.insert(0, 'tabulation', '    ')

    # output_file=fname
    cruise_id = output_file.name[4:17]
    station_id = cruise_id + metadata["station"].zfill(5)
    station_date = metadata["time"].strftime("%d%m%Y")
    station_time = metadata["time"].strftime("%H%M")
    local_cdi_id = cruise_id + "_" + metadata["station"].zfill(5) + "_H10"

    lat = math.modf(metadata["lat"])
    if lat[1] > 0:
        station_lat = (
            "N"
            + str(int(lat[1])).zfill(2)
            + " "
            + "{:02.{prec}f}".format(abs(lat[0]) * 60, prec=2).zfill(5)
        )
    else:
        station_lat = (
            "S"
            + str(abs(int(lat[1]))).zfill(2)
            + " "
            + "{:02.{prec}f}".format(abs(lat[0]) * 60, prec=2).zfill(5)
        )

    lon = math.modf(metadata["lon"])
    if lon[1] > 0:
        station_lon = (
            "E"
            + str(int(lon[1])).zfill(3)
            + " "
            + "{:02.{prec}f}".format(abs(lon[0]) * 60, prec=2).zfill(5)
        )
    else:
        station_lon = (
            "W"
            + str(abs(int(lon[1]))).zfill(3)
            + " "
            + "{:02.{prec}f}".format(abs(lon[0]) * 60, prec=2).zfill(5)
        )

    # Compute Global Parameter Quality Flag following Maillard et al.
    flagglobal = ""
    for idx in range(len(str(df['FLAGS'].iloc[0]))):
        flagparam = []
        for element in df["FLAGS"].iloc[0:-1]:
            flagparam.append(element[idx])
        if flagparam.count("4") / len(flagparam) > 0.2:
            flagglobal = flagglobal + "4"
        elif (
            (flagparam.count("4") / len(flagparam))
            + (flagparam.count("3") / len(flagparam))
        ) > 0.2:
            flagglobal = flagglobal + "3"
        elif (
            (flagparam.count("4") / len(flagparam))
            + (flagparam.count("3") / len(flagparam))
            + (flagparam.count("2") / len(flagparam))
        ) > 0.2:
            flagglobal = flagglobal + "2"
        else:
            flagglobal = flagglobal + "1"

    # Build a station header (note that depth is not mandatory)
    header = ""
    header = "*" + station_id + " Data Type=H10\n"
    if metadata["depth"] is None:
        header = (
            header
            + "*DATE="
            + station_date
            + " TIME="
            + station_time
            + " LAT="
            + station_lat
            + " LON="
            + station_lon
            + " DEPTH=       QC=1119"
            + "\n"
        )
    else:
        header = (
            header
            + "*DATE="
            + station_date
            + " TIME="
            + station_time
            + " LAT="
            + station_lat
            + " LON="
            + station_lon
            + " DEPTH="
            + str(metadata["depth"]).ljust(7)
            + "QC=1111"
            + "\n"
        )
    header = (
        header
        + "*NB PARAMETERS="
        + str(len(df.columns) - 1).zfill(2)
        + " RECORD LINES="
        + str(len(df) - 1).zfill(5)
        + "\n"
    )
    for column in df.columns:
        if column != 'FLAGS':
            header = (
                header
                + '*' 
                + column 
                + ' ' 
                + mapping_P01_dict[column]['name_IOC'].ljust(30)
                + '('
                + mapping_P01_dict[column]['units_IOC'].ljust(28)
                + ') def.='
                + str(df[column].iloc[-1])
                + "\n"
            )
        
    header = (
        header
        + "*GLOBAL PROFILE QUALITY FLAG=1 GLOBAL PARAMETERS QC FLAGS="
        + flagglobal
        + "\n"
    )
    header = (
        header
        + "*DC HISTORY= " + str(metadata["instrument"]) + "\n"
        + "*\n"
        + "*DM HISTORY= Station name in original data sheet: " + str(metadata["name"]) + "\n"  
        + "*\n"
        + "*COMMENT\n*\n*SDN_parameter_mapping\n"
    )
    
    for column in df.columns:
        if column != 'FLAGS':
            header = (
                header 
                + '*<subject>SDN:LOCAL:' 
                + column 
                + '</subject><object>SDN:P01::' 
                + mapping_P01_dict[column]['name_P01'] 
                + '</object><units>SDN:P06::' 
                + mapping_P01_dict[column]['name_P06'] 
                + '</units>' + "\n"
            )

    header = header + "*EDMO_CODE=" + edmo_code + "\n"
    header = header + "*LOCAL_CDI_ID=" + local_cdi_id + "\n"
    header = (
        header
        + '*<sdn_reference xlink:href="https://csr.seadatanet.org/report/edmo/'
        + edmo_code 
        + '/'
        + cruise_id
        + '/xml" xlink:role="isObservedBy" xlink:type="SDN:L23::CSR"/>'
        + "\n"
    )
    header = (
        header
        + '*<sdn_reference xlink:href="https://www.seadatanet.org/urnurl/SDN:C17::'
        + cruise_id[0:4]
        + '" xlink:role="isObservedBy" xlink:type="SDN:L23::NVS2CON"/>'
        + "\n"
    )
    header = (
        header
        + '*<sdn_reference xlink:href="https://cdi.seadatanet.org/report/edmo/'
        + edmo_code 
        + '/'
        + local_cdi_id
        + '/xml" xlink:role="isDescribedBy" xlink:type="SDN:L23::CDI"/>'
        + "\n"
    )
    header = header + "*SURFACE SAMPLES=\n*\n"
    header = header + "*"
    for column in df.columns:
        if column != "FLAGS":
            header = header + column + "  "

    with open(output_file, "a", encoding="utf8", newline="") as outfile:
        outfile.write(header + "\n")
        # to_csv does not allow to use space character as delimiter
        for index, rows in df.iterrows():
            outfile.write(' '.join(rows.values) + '\n')

    return


def add_cruise_header(csr, ncasts, fname):
    """ Add cruise header to a SeaDataNet MedAtlas file
       
       Input: - csr object obtained from function "parse_csr"
              - number of stations (length casts)
              - output file including the route
    """
    header = (
        "*"
        + csr["cruise_id"]
        + " "
        + csr["cruise_name"][0:33].ljust(33)
        + csr["cruise_id"][0:4]
        + " "
        + csr["vessel_name"].ljust(25)
        + "\n"
        + csr["cruise_time"]
        + " "
        + csr["water_body"].ljust(50)
        + "\n"
        + csr["cruise_id"][0:2]
        + " "
        + csr["acquisition_center"].ljust(75)
        + "\n"
        + csr["chief_scientist"].ljust(41)
        + "Project="
        + csr["project_acronym"].ljust(28)
        + "\n"
        + "Regional Archiving= SI                   Availability=L"
        + "\n"
        + "Data Type=H10 n="
        + str(ncasts).ljust(5)
        + "QC=Y"
        + "\n"
        + "COMMENT"
        + "\n"
        + "SeaDataNet MEDATLAS profile - Generated with CTDCheck by IEO - "
        + datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        + "\n"
    )
    with open(fname, "r+", encoding="utf8", newline="") as f:
        content = f.read()
        f.seek(0, 0)
        f.write(header.rstrip("\r\n") + "\n" + content)
        
    return    

def imglist_to_pdf(imglist, pdf_file):

    pdf = FPDF()

    for image in imglist:

        cover = Image.open(image)
        width, height = cover.size

        # convert pixel in mm with 1px=0.264583 mm
        width, height = float(width * 0.264583), float(height * 0.264583)

        # given we are working with A4 format size
        pdf_size = {"P": {"w": 210, "h": 297}, "L": {"w": 297, "h": 210}}

        # get page orientation from image size
        orientation = "P" if width < height else "L"

        #  make sure image size is not greater than the pdf format size
        width = (
            width if width < pdf_size[orientation]["w"] else pdf_size[orientation]["w"]
        )
        height = (
            height
            if height < pdf_size[orientation]["h"]
            else pdf_size[orientation]["h"]
        )
        if width == height:
            orientation = "P"
        pdf.add_page(orientation=orientation)

        align_center = True
        if align_center == True:
            left = (pdf_size[orientation]["w"] - width) / 2
            top = (pdf_size[orientation]["h"] - height) / 2
        else:
            left = 0
            top = 0

        pdf.image(image, left, top, width, height)

    pdf.output(pdf_file, "F")
