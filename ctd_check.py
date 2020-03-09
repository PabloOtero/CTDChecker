# -*- coding: utf-8 -*-
"""
Created on Wed Jul  3 14:23:11 2019

@author: pablo.otero@ieo.es
         Instituto Español de Oceanografía
"""

from pathlib import Path
import ctd
from ctd import (
    parse_csr,
    from_cnv,
    to_cnv_flagged,
    to_cnv_medatlas,
    speed_test,
    plot_all_casts,
    get_cdi_from_medatlas,
)
import os
import matplotlib.pyplot as plt
import cartopy.feature as cfeature
import cartopy.crs as ccrs
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import matplotlib.ticker as mticker
from matplotlib import style
import sys
from datetime import datetime
import shutil
import math
import copy
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)

style.use("seaborn-whitegrid")


path = Path("D:\CentroDatos\Datos\PENDIENTES", "test_rocio")

#Choose if you want a cnv flagged file (ASCII) to use in NEMO software
nemo = None

csrfile = list(path.glob("*.xml"))
if len(csrfile) == 0:
    sys.exit("ERROR. No CSR file in directory")
elif len(csrfile) == 1:
    csr = parse_csr(csrfile[0])
else:
    sys.exit("ERROR. More than one xml (CSR) in directory")


filenames = list(path.glob("*.cnv"))
if filenames:
    filenames = sorted([f.name for f in filenames])  # Unordered in server

    outpath = path / "out"
    shutil.rmtree(outpath, ignore_errors=True)
    os.makedirs(outpath)

    outpath_img = path / "out" / "figures"
    if not os.path.exists(outpath_img):
        os.makedirs(outpath_img)
    if nemo is not None:    
        outpath_flagged = path / "out" / "data-cnvFlagged"
        if not os.path.exists(outpath_flagged):
            os.makedirs(outpath_flagged)
    outpath_medatlas = path / "out" / "data-MedAtlasSDN"
    if not os.path.exists(outpath_medatlas):
        os.makedirs(outpath_medatlas)
    outpath_cdi = path / "out" / "metadata-CDI"
    if not os.path.exists(outpath_cdi):
        os.makedirs(outpath_cdi)
else:
    sys.exit("No *.cnv files found in directory")


cfg = ctd.load_cfg()  # Load quality control configuration


casts, metadata = list(), list()

filenames_deepcopy = copy.deepcopy(filenames)
for idx, filename in enumerate(filenames):

    print("Reading file: " + filename)

    fname = path / filename
    cast = from_cnv(fname)
    if cast.shape[0] == 0:  # Check if dataframe is empty
        print("WARNING: No data in file " + filename)
        filenames_deepcopy.pop(idx)
    else:
        casts.append(cast)
        metadata.append(cast._metadata)
   
    if csr['cruise_location'] is not None:
        if metadata[idx]['lat'] < float(csr['cruise_location'][0]) or metadata[idx]['lat'] > float(csr['cruise_location'][1]):
            raise ValueError(
                "Latitude is out the bounding box of the campaign"
            )             
        if metadata[idx]['lon'] < float(csr['cruise_location'][2]) or metadata[idx]['lon'] > float(csr['cruise_location'][3]):
            raise ValueError(
                "Longitude is out the bounding box of the campaign"
            )         
        
filenames = filenames_deepcopy

speed_test(metadata, cfg)



# Process dataframes
for idx, profile in enumerate(casts):

    metadata[idx]["station"] = str(idx + 1)  # Rename stations

    down, up = profile.split()

    df = down

    df = df.press_check()  # Remove pressure reversals

    #          PREPROCESSING
    # For example:
    # df = df.remove_above_water()\
    #       .despike(n1=2, n2=20, block=100)\
    #       .lp_filter()\
    #       .interpolate() \
    #       .bindata(delta=1, method='interpolate')

    # Pressure is stored as index. Rename, move to column and change to integer
    df.index.names = ["PRES"]
    df = df.reset_index()
    df["PRES"] = df["PRES"].astype("int16")

    # Rename variables according with P02 vocabularies
    # http://seadatanet.maris2.nl/v_bodc_vocab_v2/vocab_relations.asp?lib=P02
    df = df.rename(
        {
            "t090C": "TEMP",
            "t190C": "TEMP",
            "sal00": "PSAL",
            "sal11": "PSAL",
            "c0S/m": "CNDC",
            "c1S/m": "CNDC",
            "flECO-AFL": "FLU2",
            "par": "LGHT",
            "turbWETntu0": "TUR4",
            "oxsatML/L": "OSAT",
        },
        axis=1,
    )

    # Remove duplicate sensors
    keep_names = set()
    keep_icols = list()
    for icol, name in enumerate(df.columns):
        if name not in keep_names:
            keep_names.add(name)
            keep_icols.append(icol)
    df = df.iloc[:, keep_icols]

    # Reorder columns to make uniform and nice files
    columnsTitles = ["PRES", "TEMP", "PSAL", "CNDC", "OSAT", "FLU2", "TUR4", "LGHT"]
    df = df.reindex(columns=columnsTitles)
    df = df.dropna(axis=1, how="all")

    # Initialize flags in DataFrame
    df.init_flags()

    # Common tests (valid geoposition is included in location at sea)
    # Stored in df.flags['main']
    df = df.valid_datetime(metadata[idx]).location_at_sea(metadata[idx])


    # Apply tests (note that profile_envelop is not available for PSAL)
    # Stored in df.flags['TEMP'] and df.flags['PSAL']
    df = df.density_inversion_test()

    varname = "TEMP"
    df = (
        df.instrument_range(varname, cfg)
        .global_range(varname, cfg)
        .regional_range(varname, metadata[idx], cfg)
        .gradient_depthconditional(varname, cfg)
        .spike_depthconditional(varname, cfg)
        .tukey53H_norm(varname, cfg)
        .digit_roll_over(varname, cfg)
        .profile_envelop(varname, cfg)
        .woa_normbias(varname, metadata[idx], cfg)
        .stuck_value(varname)
        .overall(varname)
    )

    varname = "PSAL"
    df = (
        df.global_range(varname, cfg)
        .regional_range(varname, metadata[idx], cfg)
        .gradient_depthconditional(varname, cfg)
        .spike_depthconditional(varname, cfg)
        .tukey53H_norm(varname, cfg)
        .digit_roll_over(varname, cfg)
        .woa_normbias(varname, metadata[idx], cfg)
        .stuck_value(varname)
        .overall(varname)
    )
    
    for varname in df.keys():
        if varname != 'PSAL':
            df = df.instrument_range(varname, cfg)

    for varname in df.keys():
        df = df.overall(varname)               
    
    # Add overall flags to DataFrame
    flags = {}
    for irow, item in enumerate(df.index.values):
        result = ""
        for variable in df.keys():
            """
            if variable == "TEMP" or variable == "PSAL" or variable == "CNDC" or variable == "OSAT":
                result += str(df.flags[variable]["overall"][irow])
            else:
                result += "1"  # SeaDataNet demands non-zero flags
            """
            result += str(df.flags[variable]["overall"][irow])
        flags[irow] = result
    df["FLAGS"] = flags.values()


    # Exploratory Data Analysis
    # feda = metadata[idx]['name']+'.html'
    # fname = outpath / feda
    # cast_report = pandas_profiling.ProfileReport(df)
    # cast_report.to_file(fname)

    # FORMATTING
    # Write cnv files to be used in NEMO software
    # Pass a explicit copy of 'df' to make it unmutable -> df[:]
    if nemo:
        fname = outpath_flagged / filenames[idx]
        to_cnv_flagged(df[:], metadata[idx], fname)

    # Write MEDATLAS file
    # Create new file and append casts. Write header at the end to take into
    # account number of valid casts
    fname = "CTD_" + csr["cruise_id"] + ".dat"
    fname = outpath_medatlas / fname

    if len(casts) == 1:
        open(fname, "w").close()

    
    to_cnv_medatlas(df[:], metadata[idx], fname)

    if idx == len(casts) - 1:
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
            + str(len(casts)).ljust(5)
            + "QC=Y"
            + "\n"
            + "COMMENT"
            + "\n"
            + "SeaDataNet MEDATLAS profile - Generated with Python by IEO - "
            + datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            + "\n"
        )
        with open(fname, "r+", encoding="utf8", newline="") as f:
            content = f.read()
            f.seek(0, 0)
            f.write(header.rstrip("\r\n") + "\n" + content)

    # PLOTTING
    df.index = df["PRES"]  # Copy again PRES to index to use plotting functions

    fig = plt.figure(figsize=(6, 6))

    # FIRST PANEL: temperature and salinity profiles
    ax = plt.subplot2grid((2, 2), (0, 0), rowspan=2)
    ax = df.plot_cast_woa("TEMP", label="Temp.", ax=ax)
    ax.set_xlabel(u"Temperature [\u00b0C]")
    ax.set_ylabel("Pressure [dbar]")
    [ymin, ymax] = ax.get_ylim()
    ax.set_ylim([ymin, 0])
    ax1 = df.plot_cast_woa(
        "PSAL", ax=ax, label="Sal.", color="green", secondary_y=True,
    )
    ax1.set_xlabel("Salinity")
    lines = ax.get_lines() + ax1.get_lines()

    # Exclude markers with bad flags to properly label the legend
    leg = {line: line.get_label() for line in lines}
    filtered_leg = {}
    for key, value in leg.items():
        if value not in filtered_leg.values():
            filtered_leg[key] = value

    ax.legend(filtered_leg.keys(), filtered_leg.values(), loc="lower left")
    ax.grid(False)
    ax1.grid(False)

    # SECOND PANEL: Geolocation
    lats = [d["lat"] for d in metadata]
    lons = [d["lon"] for d in metadata]
    lat = metadata[idx]["lat"]
    lon = metadata[idx]["lon"]

    offset = 1
    ax2 = plt.subplot2grid((2, 2), (0, 1), projection=ccrs.PlateCarree())
    ax2.set_extent(
        [min(lons) - offset, max(lons) + offset, min(lats) - offset, max(lats) + offset]
    )
    ax2.stock_img()
    ax2.coastlines("10m")
    ax2.plot(lons, lats, marker="o", linestyle="", color="white", markersize=1, alpha=1)
    ax2.plot(lon, lat, marker="o", color="red", markersize=5, alpha=1)
    gl = ax2.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=True,
        linewidth=1,
        color="gray",
        alpha=0.5,
        linestyle="--",
    )
    gl.xlabels_top = False
    gl.ylabels_left = False
    tick_separator = int(math.ceil((max(lons) - min(lons) + offset * 2) / 4))
    gl.xlocator = mticker.FixedLocator(list(range(-180, 180, tick_separator)))
    gl.ylocator = mticker.FixedLocator(list(range(-90, 90, tick_separator)))
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    gl.ylabel_style = {"color": "gray"}
    gl.xlabel_style = {"color": "gray"}

    ax2B = plt.axes([0.8, 0.8, 0.1, 0.1], projection=ccrs.Orthographic(lon, lat))
    ax2B.add_feature(cfeature.OCEAN, zorder=0, facecolor="None")
    ax2B.add_feature(cfeature.LAND, zorder=0, facecolor="#e6eaed", edgecolor="#cbced1")
    ax2B.set_global()
    ax2B.gridlines()
    ax2B.plot(lon, lat, marker="o", color="red", markersize=12, alpha=0.2)

    # THIRD PANEL: T/S diagram
    ax3 = plt.subplot2grid((2, 2), (1, 1))
    ax3 = df.plot_ts_diagram(ax=ax3)

    # Title
    if metadata[idx]["lat"] > 0:
        latstr = "{:.2f}".format(metadata[idx]["lat"]) + "ºN"
    else:
        latstr = "{:.2f}".format(abs(metadata[idx]["lat"])) + "ºS"
    if metadata[idx]["lon"] > 0:
        lonstr = "{:.2f}".format(metadata[idx]["lon"]) + "ºE"
    else:
        lonstr = "{:.2f}".format(abs(metadata[idx]["lon"])) + "ºW"

    info = (
        "Station: "
        + metadata[idx]["name"]
        + " | "
        + metadata[idx]["time"].strftime("%c")
        + " | "
        + latstr
        + " "
        + lonstr
    )
    if metadata[idx]["cruise"] is not None:
        info = metadata[idx]["cruise"] + "\n" + info
    fig.suptitle(info, fontsize=10)

    fimg = metadata[idx]["name"] + ".png"
    fname = outpath_img / fimg
    plt.savefig(fname)
    plt.close()


# Plot all stations
fig, ax = plt.subplots()
fig.suptitle("CTD stations")
ax = plot_all_casts(metadata, ax=ax)
fimg = "AllStations" + ".png"
fname = outpath_img / fimg
plt.savefig(fname)
plt.close()

# Create CDIs
fname = "CTD_" + csr["cruise_id"] + ".dat"
fname = outpath_medatlas / fname
get_cdi_from_medatlas(fname, outpath_cdi, csr)
