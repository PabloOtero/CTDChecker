# -*- coding: utf-8 -*-
"""
Created on Wed Oct  2 12:41:24 2019

@author: pablo.otero@ieo.es
         Instituto Español de Oceanografía
"""


from pathlib import Path
from io import StringIO
from datetime import datetime, timedelta
import requests
import dateutil.parser
import os
import lxml.etree as ET


CSR_URL = "http://seadata.bsh.de/isoCodelists/sdnCodelists/csrCodeList.xml"
CSR_LOCAL_FILE = "csrCodeList.xml"
CDI_TEMPLATE = "cdi_ctd_ieo_template.xml"


def download_sdn_lists():
    print("INFO: Downloading CSR list file")
    response = requests.get(CSR_URL)
    with open(CSR_LOCAL_FILE, "wb") as file:
        file.write(response.content)

    return


def check_sdn_lists():

    response = requests.head(CSR_URL)

    if response.status_code == 200:

        remote_modified = response.headers.get("Last-Modified")

        if remote_modified:
            remote_modified = dateutil.parser.parse(remote_modified)
            remote_modified = datetime(
                year=remote_modified.year,
                month=remote_modified.month,
                day=remote_modified.day,
            )

            if os.path.isfile(CSR_LOCAL_FILE):
                local_modified = datetime.fromtimestamp(
                    os.stat(CSR_LOCAL_FILE).st_mtime
                )
                local_modified = datetime(
                    year=local_modified.year,
                    month=local_modified.month,
                    day=local_modified.day,
                )

                if remote_modified > local_modified:
                    download_sdn_lists()
                else:
                    print("INFO: CSR list file up to date")
            else:
                download_sdn_lists()
    else:
        print("WARNING: cannot retrieve CSR list from BSH server")

    return


def _parse_cnv_medatlas(file):

    contents = file.read_bytes()
    text = contents.decode(encoding="utf-8", errors="replace")
    lines = StringIO(text).readlines()
    lines = [x.strip() for x in lines]

    medatlas = {}

    (
        dataset_id,
        dataset_name,
        start_date_of_cruise,
        projects,
        dataset_access,
        dataset_rev_date,
        cruise_name,
        cruise_id,
        station_name,
    ) = (None, None, None, None, None, None, None, None, None)

    (
        local_cdi_id,
        p02_code,
        station_date,
        station_date_start,
        station_date_end,
        station_latitude,
        station_longitude,
    ) = ([], [], [], [], [], [], [])

    for irow, line in enumerate(lines):
        if irow == 0:
            [dataset_id, line] = line[1:].split(" ", 1)
            if "ZZ99" in line:
                [dataset_name, line] = line.split("ZZ99")
            else:
                [dataset_name, line] = line.split("29")
            dataset_name = dataset_name.rstrip()
            cruise_name = dataset_name
            cruise_id = dataset_id
        if irow == 1:
            [start_date_of_cruise, line] = line.split("-")
            # start_date_of_cruise = start_date_of_cruise.replace("/", "-")
        if "Project=" in line:
            projects = line.split("Project=")[1].strip()
        if "Availability=" in line:
            dataset_access = line.split("Availability=")[1].strip()
            if dataset_access == "L":
                dataset_access = "RS"

    local_cdi_id = [s.split("=")[1].strip() for s in lines if "LOCAL_CDI_ID" in s]
    station_name = [str(int(s.split("_")[1])) for s in local_cdi_id]

    matching = [s.split("*")[1].strip() for s in lines if "*PRES" in s]
    p02_code = matching[1::2]
    p02_code = [
        s.replace("PRES", "AHGT")
        .replace("OSAT", "DOXY")
        .replace("FLU2", "CPWC")
        .replace("TUR4", "TSED")
        for s in p02_code
    ]

    matching = [s.split("*DATE=")[1] for s in lines if "*DATE" in s]
    date = [s.split("TIME=")[0].strip() for s in matching]
    matching = [s.split("TIME=")[1].strip() for s in matching]
    time = [s.split("LAT=")[0].strip() for s in matching]
    matching = [s.split("LAT=")[1] for s in matching]
    # station_date = [i[0:2] + '/' + i[2:4] + '/' + i[4:] for i in date]
    station_date = [i[4:] + "-" + i[2:4] + "-" + i[0:2] for i in date]
    station_date_start = [
        i[4:] + "-" + i[2:4] + "-" + i[0:2] + "T" + j[0:2] + ":" + j[2:4] + ":00"
        for i, j in zip(date, time)
    ]

    lat = [s.split("LON=")[0].rstrip() for s in matching]
    hemisphere = [s[0] for s in lat]
    lat = [s.rstrip() for s in lat]
    lat_degree = [s[1:].split()[0] for s in lat]
    lat_minutes = [float(s[1:].split()[1]) / 60 for s in lat]
    hemisphere = [s.replace("N", "").replace("S", "-") for s in hemisphere]
    lat = [float(i) + float(j) for i, j in zip(lat_degree, lat_minutes)]
    station_latitude = [i + "{:.3f}".format(j) for i, j in zip(hemisphere, lat)]

    matching = [s.split("LON=")[1] for s in matching]
    lon = [s.split("DEPTH=")[0].rstrip() for s in matching]
    hemisphere = [s[0] for s in lon]
    lon_degree = [s[1:].split()[0] for s in lon]
    lon_minutes = [float(s[1:].split()[1]) / 60 for s in lon]
    hemisphere = [s.replace("E", "").replace("W", "-") for s in hemisphere]
    lon = [float(i) + float(j) for i, j in zip(lon_degree, lon_minutes)]
    station_longitude = [i + "{:.3f}".format(j) for i, j in zip(hemisphere, lon)]

    matching = [s.split("DEPTH=")[1] for s in matching]
    depth = [s.split("QC=")[0].rstrip() for s in matching]

    # Just an approximation: the profile takes two time the depth (down and up) and add 10' extra
    # and if not depth is found, add 1h
    date_object = [
        datetime(int(i[4:]), int(i[2:4]), int(i[0:2]), int(j[0:2]), int(j[2:4]))
        for i, j in zip(date, time)
    ]
    depth = ["1800" if x == "" else x for x in depth]
    date_object2 = [
        i + timedelta(seconds=(int(j) * 2 + 600)) for i, j in zip(date_object, depth)
    ]
    station_date_end = [i.strftime("%Y-%m-%dT%H:%M:%S") for i in date_object2]

    dataset_rev_date = datetime.now().strftime("%Y-%m-%d")

    medatlas.update(
        {
            "edmo_author": "353",
            "edmo_originator": "353",
            "edmo_custodian": "353",
            "edmo_distributor": "353",
            "area_type": "Point",
            "dataset_abs": "CTD collection",
            "platform_type": "31",
            "instruments": "CTD",
            "format_type": ["MEDATLAS", "ODV", "CFPOINT"],
            "format_version": ["2", "0.4", "1"],
            "data_size": "0.011",
            "dist_methode": "CDIMTH02",
            "dist_website": "http://www.sdn-taskmanager.org/",
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "start_date_of_cruise": start_date_of_cruise,
            "projects": projects,
            "dataset_access": dataset_access,
            "dataset_rev_date": dataset_rev_date,
            "cruise_name": cruise_name,
            "cruise_id": cruise_id,
            "station_name": station_name,
            "local_cdi_id": local_cdi_id,
            "p02_code": p02_code,
            "station_date": station_date,
            "station_date_start": station_date_start,
            "station_date_end": station_date_end,
            "station_latitude": station_latitude,
            "station_longitude": station_longitude,
        }
    )

    return medatlas


def get_nemo_summary(medatlas):
    """ Creates a summary file to be used in NEMO software (SeaDataNet) as
        intermediate step to create CDI medadata
        
        Input: dictionary obtained from _parse_cnv_medatlas
        Output: summary_cdi_for_mikado.txt
    """

    with open("summary_cdi_for_mikado.txt", "w+", encoding="utf8") as f:
        header = "LOCAL_CDI_ID\tEDMO_AUTHOR\tAREA_TYPE\tDATASET_NAME\tDATASET_ID\tDATASET_REV_DATE\tEDMO_ORIGINATOR\tDATASET_ABS\tEDMO_CUSTODIAN\tP02_CODE\tPLATFORM_TYPE\tDATASET_ACCESS\tCRUISE_NAME\tCRUISE_ID\tSTART_DATE_OF_CRUISE\tSTATION_NAME\tSTATION_LATITUDE\tSTATION_LONGITUDE\tSTATION_DATE\tSTATION_DATE_START\tEDMO_DISTRIBUTOR\tFORMAT\tFORMAT_VERSION\tDATA_SIZE\tDIST_WEBSITE\tDIST_METHODE\tSTATION_DATE_END\tINSTRUMENTS\tPROJECTS\n"
        f.write(header)
        for k, cast in enumerate(medatlas["local_cdi_id"]):
            measurements = medatlas["p02_code"][k].split()
            for param in measurements:
                for method in medatlas["format_type"]:
                    line = (
                        medatlas["local_cdi_id"][k]
                        + "\t"
                        + medatlas["edmo_author"]
                        + "\t"
                        + medatlas["area_type"]
                        + "\t"
                        + medatlas["dataset_name"]
                        + "\t"
                        + medatlas["dataset_id"]
                        + "\t"
                        + medatlas["dataset_rev_date"]
                        + "\t"
                        + medatlas["edmo_originator"]
                        + "\t"
                        + medatlas["dataset_abs"]
                        + "\t"
                        + medatlas["edmo_custodian"]
                        + "\t"
                        + param
                        + "\t"
                        + medatlas["platform_type"]
                        + "\t"
                        + medatlas["dataset_access"]
                        + "\t"
                        + medatlas["cruise_name"]
                        + "\t"
                        + medatlas["cruise_id"]
                        + "\t"
                        + medatlas["start_date_of_cruise"]
                        + "\t"
                        + medatlas["station_name"][k]
                        + "\t"
                        + medatlas["station_latitude"][k]
                        + "\t"
                        + medatlas["station_longitude"][k]
                        + "\t"
                        + medatlas["station_date"][k]
                        + "\t"
                        + medatlas["station_date_start"][k]
                        + "\t"
                        + medatlas["edmo_distributor"]
                        + "\t"
                        + method
                        + "\t"
                    )
                    if method == medatlas["format_type"][0]:
                        line = line + medatlas["format_version"][0] + "\t"
                    elif method == medatlas["format_type"][1]:
                        line = line + medatlas["format_version"][1] + "\t"
                    elif method == medatlas["format_type"][2]:
                        line = line + medatlas["format_version"][2] + "\t"
                    line = (
                        line
                        + medatlas["data_size"]
                        + "\t"
                        + medatlas["dist_website"]
                        + "\t"
                        + medatlas["dist_methode"]
                        + "\t"
                        + medatlas["station_date_end"][k]
                        + "\t"
                        + medatlas["instruments"]
                        + "\t"
                        + medatlas["projects"]
                        + "\n"
                    )
                    f.write(line)
    return


def get_cdi_from_medatlas(file, output_dir, csr):
    """
       Create CDI metadata files, one per cast in the medatlas file
       
       Input: - Data file in medatlas format
              - Output directoty for new metadata files
              - Info forem CSR file, obtained from a previous parsing:
                   csr = parse_csr(csrfile)
    """

    check_sdn_lists()

    medatlas = _parse_cnv_medatlas(file)

    dom_CSR = ET.parse(CSR_LOCAL_FILE)
    root_CSR = dom_CSR.getroot()
    target_nodes = root_CSR.findall(".//{http://www.opengis.net/gml}name")

    csr_code, csr_description = "UNKNOWN", "UNKNOWN"
    for elem in target_nodes:
        if medatlas["cruise_id"] in elem.text:
            parent = elem.getparent()
            csr_description = parent.find(
                "./{http://www.opengis.net/gml}description"
            ).text
            csr_code = parent.find("./{http://www.opengis.net/gml}identifier").text
            print(csr_description, csr_code)
            break

    # TO READ FILE DOWNLOADED BY MIKADO
    # in this case, complete route to your local file must be provided
    #
    # with open(CSR_LOCAL_FILE, 'r', encoding="utf8") as infile:
    #    data = infile.readlines()  # read a list of lines
    #    for line in data:
    #        if medatlas["cruise_id"] in line:
    #            print(line)
    #            [csr_code, text] = line.split('SDN:CSR::')[1].split('"')
    #            csr_description =  text.strip('</keyword>\n').split(']')[1].strip()
    #            break

    for k, cast in enumerate(medatlas["local_cdi_id"]):

        with open(CDI_TEMPLATE, "r", encoding="utf8") as f:
            template = f.read()

            template = template.replace("LOCAL_CDI_ID", cast)
            template = template.replace(
                "DATASET_REV_DATE", medatlas["dataset_rev_date"]
            )
            template = template.replace("CRUISE_NAME", medatlas["cruise_name"])
            template = template.replace("STATION_NAME", medatlas["station_name"][k])
            template = template.replace(
                "STATION_LATITUDE", medatlas["station_latitude"][k]
            )
            template = template.replace(
                "STATION_LONGITUDE", medatlas["station_longitude"][k]
            )
            template = template.replace(
                "STATION_DATE_START", medatlas["station_date_start"][k]
            )
            template = template.replace(
                "STATION_DATE_END", medatlas["station_date_end"][k]
            )
            template = template.replace(
                "STATION_DATE_SIMPLE", medatlas["station_date"][k]
            )
            template = template.replace(
                "START_DATE_OF_CRUISE", medatlas["start_date_of_cruise"]
            )
            template = template.replace("PROJECT_CODE", csr["project_code"])
            template = template.replace(
                "PROJECT_DESCRIPTION", csr["project_description"]
            )
            template = template.replace("CSR_CODE", csr_code)
            template = template.replace("CSR_DESCRIPTION", csr_description)

            measurements = medatlas["p02_code"][k].split()
            PARAMETERS = ""
            for param in measurements:
                if param == "AHGT":
                    line = '                  <gmd:keyword>\n                     <sdn:SDN_ParameterDiscoveryCode codeSpace="SeaDataNet"  codeListValue="AHGT"  codeList="http://vocab.nerc.ac.uk/isoCodelists/sdnCodelists/cdicsrCodeList.xml#SDN_ParameterDiscoveryCode" >Vertical spatial coordinates</sdn:SDN_ParameterDiscoveryCode>\n                  </gmd:keyword>\n'
                    PARAMETERS = PARAMETERS + line
                elif param == "TEMP":
                    line = '                  <gmd:keyword>\n                     <sdn:SDN_ParameterDiscoveryCode codeSpace="SeaDataNet"  codeListValue="TEMP"  codeList="http://vocab.nerc.ac.uk/isoCodelists/sdnCodelists/cdicsrCodeList.xml#SDN_ParameterDiscoveryCode" >Temperature of the water column</sdn:SDN_ParameterDiscoveryCode>\n                  </gmd:keyword>\n'
                    PARAMETERS = PARAMETERS + line
                elif param == "PSAL":
                    line = '                  <gmd:keyword>\n                     <sdn:SDN_ParameterDiscoveryCode codeSpace="SeaDataNet"  codeListValue="PSAL"  codeList="http://vocab.nerc.ac.uk/isoCodelists/sdnCodelists/cdicsrCodeList.xml#SDN_ParameterDiscoveryCode" >Salinity of the water column</sdn:SDN_ParameterDiscoveryCode>\n                  </gmd:keyword>\n'
                    PARAMETERS = PARAMETERS + line
                elif param == "CNDC":
                    line = '                  <gmd:keyword>\n                     <sdn:SDN_ParameterDiscoveryCode codeSpace="SeaDataNet"  codeListValue="CNDC"  codeList="http://vocab.nerc.ac.uk/isoCodelists/sdnCodelists/cdicsrCodeList.xml#SDN_ParameterDiscoveryCode" >Electrical conductivity of the water column</sdn:SDN_ParameterDiscoveryCode>\n                  </gmd:keyword>\n'
                    PARAMETERS = PARAMETERS + line
                elif param == "DOXY":
                    line = '                  <gmd:keyword>\n                     <sdn:SDN_ParameterDiscoveryCode codeSpace="SeaDataNet"  codeListValue="DOXY"  codeList="http://vocab.nerc.ac.uk/isoCodelists/sdnCodelists/cdicsrCodeList.xml#SDN_ParameterDiscoveryCode" >Dissolved oxygen parameters in the water column</sdn:SDN_ParameterDiscoveryCode>\n                  </gmd:keyword>\n'
                    PARAMETERS = PARAMETERS + line
                elif param == "CPWC":
                    line = '                  <gmd:keyword>\n                     <sdn:SDN_ParameterDiscoveryCode codeSpace="SeaDataNet"  codeListValue="CPWC"  codeList="http://vocab.nerc.ac.uk/isoCodelists/sdnCodelists/cdicsrCodeList.xml#SDN_ParameterDiscoveryCode" >Chlorophyll pigment concentrations in water bodies</sdn:SDN_ParameterDiscoveryCode>\n                  </gmd:keyword>\n'
                    PARAMETERS = PARAMETERS + line
                elif param == "TSED":
                    line = '                  <gmd:keyword>\n                     <sdn:SDN_ParameterDiscoveryCode codeSpace="SeaDataNet"  codeListValue="TSED"  codeList="http://vocab.nerc.ac.uk/isoCodelists/sdnCodelists/cdicsrCodeList.xml#SDN_ParameterDiscoveryCode" >Concentration of suspended particulate material in the water column</sdn:SDN_ParameterDiscoveryCode>\n                  </gmd:keyword>\n'
                    PARAMETERS = PARAMETERS + line

            template = template.replace("PARAMETERS", PARAMETERS[:-1])

            line = '                  <gmd:otherConstraints>\n                     <gmx:Anchor xlink:href="http://www.seadatanet.org/urnurl/SDN:L08::RS" >by negotiation</gmx:Anchor>\n                  </gmd:otherConstraints>'
            template = template.replace("DATASET_ACCESS", line)

            output_file = Path(output_dir, cast + ".xml")
            with open(output_file, "w", encoding="utf8", newline="") as outfile:
                outfile.write(template)

    return
