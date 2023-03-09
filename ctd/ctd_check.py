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
    csr_bounding_box_test,
    plot_all_casts,
    create_cdi_from_medatlas,
    add_cruise_header,
    plot_cast_panel,
    
)
import os
import matplotlib.pyplot as plt

from matplotlib import style
import sys
import shutil

import copy
import warnings
import matplotlib.cbook
warnings.filterwarnings("ignore",category=matplotlib.cbook.mplDeprecation)
plt.ioff()

import pandas_profiling


warnings.simplefilter(action="ignore", category=FutureWarning)
warnings.simplefilter(action="ignore", category=DeprecationWarning)

style.use("seaborn-whitegrid")


path = Path("C:\Pablo\CentroDatos\Datos\PENDIENTES\campana_namibia0502", "cnv_corrected")

tonemo = False
tomedatlas = True
plotting = True
metadating = True
coupling = True
feda = True


# Load quality control configuration
try:
    cfg = ctd.load_cfg()  
except:
    print('Could not load quality control configuration file')  


# Load CSR file
csrfile = list(path.glob("*.xml"))
if len(csrfile) == 0:
    sys.exit("ERROR. No CSR file in directory")
elif len(csrfile) == 1:
    csr = parse_csr(csrfile[0])
else:
    sys.exit("ERROR. More than one xml (CSR) in directory")

# Load files and create output folders
filenames = list(path.glob("*.cnv"))
if filenames:
    filenames = sorted([f.name for f in filenames])  # Unordered in server

    outpath = path / "ctdcheck_output"
    shutil.rmtree(outpath, ignore_errors=True)
    os.makedirs(outpath)

    if tomedatlas:
        outpath_medatlas = outpath / "data"
        if not os.path.exists(outpath_medatlas):
            os.makedirs(outpath_medatlas)
    if plotting:
        outpath_img = outpath / "figures"
        if not os.path.exists(outpath_img):
            os.makedirs(outpath_img)
    if tonemo:    
        outpath_flagged = outpath / "data-cnvFlagged"
        if not os.path.exists(outpath_flagged):
            os.makedirs(outpath_flagged)
    if metadating:
        outpath_cdi = outpath / "metadata"
        if not os.path.exists(outpath_cdi):
            os.makedirs(outpath_cdi)
else:
    sys.exit("No *.cnv files found in directory")


# Separate data and metadata from each file
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
filenames = filenames_deepcopy


"""
# Check locations with pyxylookup service. It needs at least two points
import pyxylookup
from pyxylookup import pyxylookup
locations = []
if len(metadata)==1:
    locations.append([metadata['lon'], metadata['lat']])
    locations.append([metadata['lon'], metadata['lat']])
else:    
    for location in metadata:
        locations.append([location['lon'], location['lat']])
info_locations = pyxylookup.lookup(locations)

if len(metadata)==1:
    info_locations = info_locations[0]

for idx, location in enumerate(info_locations):
    if(location['shoredistance'] < 0):
        print('Station', metadata[idx]['name'], 'is', abs(location['shoredistance']/1000), 'km inland')
"""        


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

    # Remove duplicates. We want only one value per meter. Discard values lower than 1m
    df = df.drop_duplicates(subset=['PRES'])
    df = df[df['PRES'] >=1]

    # Rename variables according with P02 vocabularies
    # http://seadatanet.maris2.nl/v_bodc_vocab_v2/vocab_relations.asp?lib=P02
    df = df.rename(
        {
            "t090": "TEMP",
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
    df = df.valid_datetime(metadata[idx]).location_at_sea(metadata[idx], 'xylookup')


    # Apply tests (note that profile_envelop is not available for PSAL)
    # Stored in df.flags['TEMP'] and df.flags['PSAL']
    df = df.density_inversion_test()

    for varname in df.keys():
        if varname == 'TEMP':
            df = (
                df.instrument_range(varname, cfg)
                .global_range(varname, cfg)
                .regional_range(varname, metadata[idx], cfg)
                .gradient_depthconditional(varname, cfg)
                .spike_depthconditional(varname, cfg)               
                .digit_roll_over(varname, cfg)
                .profile_envelop(varname, cfg)
                .woa_normbias(varname, metadata[idx], cfg)
                .stuck_value(varname)
            )            
            #Time consuming
            #df = df.tukey53H_norm(varname, cfg)
                       

        if varname == 'PSAL':
            df = (
                df.global_range(varname, cfg)
                .regional_range(varname, metadata[idx], cfg)
                .gradient_depthconditional(varname, cfg)
                .spike_depthconditional(varname, cfg)
                .digit_roll_over(varname, cfg)
                .woa_normbias(varname, metadata[idx], cfg)
                .stuck_value(varname)
            )           
            #Time consuming
            #df = df.tukey53H_norm(varname, cfg)            
            
        if varname != 'PSAL':
            df = df.instrument_range(varname, cfg)
            
     
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
    if feda:
        feda = metadata[idx]['name']+'.html'
        fname = outpath / feda
        cast_report = pandas_profiling.ProfileReport(df, minimal=True)
        cast_report.to_file(fname)

    # FORMATTING
    # Write cnv files to be used in NEMO software
    # Pass a explicit copy of 'df' to make it unmutable -> df[:]
    if tonemo:
        fname = outpath_flagged / filenames[idx]
        to_cnv_flagged(df[:], metadata[idx], fname)

    # Write MEDATLAS file
    # Create new file and append casts. Write header at the end to take into
    # account number of valid casts
    if tomedatlas:
        fname = "CTD_" + csr["cruise_id"] + ".dat"
        fname = outpath_medatlas / fname
    
        if len(casts) == 1:
            open(fname, "w").close()
    
        
        #to_cnv_medatlas(df[:], metadata[idx], fname)
        to_cnv_medatlas(df[:], metadata[idx], fname, csr['custodian_code'])
        
        if idx == len(casts) - 1:
            add_cruise_header(csr, len(casts), fname)


    if plotting:
        
        df.index = df["PRES"]  # Copy again PRES to index to use plotting functions
        
        fimg = metadata[idx]["name"] + ".png"
        fname = outpath_img / fimg
        
        
        if 'TEMP' and 'PSAL' in df.columns:                      
            plot_cast_panel(df, metadata, idx, fname)
        
        
        if idx == len(casts) - 1:
            fig, ax = plt.subplots()
            fig.suptitle("CTD stations")
            ax = plot_all_casts(metadata, ax=ax)
            fimg = "AllStations" + ".png"
            fname = outpath_img / fimg
            plt.savefig(fname)
            plt.close()

      
csr_bounding_box_test(metadata, csr)  
speed_test(metadata, cfg)

# Create CDIs
if metadating:
    fname = "CTD_" + csr["cruise_id"] + ".dat"
    fname = outpath_medatlas / fname
    create_cdi_from_medatlas(fname, outpath_cdi, csr)
    if coupling:
        if csr['custodian_code'] == '353':        
            coupling_file = outpath_cdi / "coupling_table.txt"                   
            with open(coupling_file, "w") as outfile:                      
                for filename in list(outpath_cdi.glob("*.xml")):
                    cdi_filename = os.path.splitext(filename.name)[0]
                    outfile.write(cdi_filename + ';3;MEDATLAS;CTD/' +  csr['cruise_time'][6:10] + '/' + fname.name + '\n')               
        else:
            print('Coupling table can be only generated for IEO-NODC')


