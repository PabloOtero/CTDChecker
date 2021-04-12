# -*- coding: utf-8 -*-
"""
Created on Wed Jul  3 14:23:11 2019
Last update on 15 March 2021

@author: pablo.otero@ieo.es
         Instituto Español de Oceanografía
         
This is a Flask version. To run it, open a terminal, activate your environment
and type in the working directory 'python app.py'. 
Open your browser at http://localhost:5000/

To run locally, you have to modify some parts:
    1) Turn flash_messages variable to False in checking.py, read.py and extras.py
    2) Set your path with your files (line after import statements)
    3) Uncomment the last block of lines at the end of this file
         
"""

import os
import shutil
from pathlib import Path
import ctd
from ctd import *
from gsw import conversions  
import matplotlib.pyplot as plt
from matplotlib import style
import matplotlib.cbook
import numpy as np
import warnings
import pandas_profiling
from flask import flash
flash_messages = True

plt.ioff()
matplotlib.use('Agg')
warnings.filterwarnings("ignore",category=matplotlib.cbook.mplDeprecation)
warnings.simplefilter(action="ignore", category=FutureWarning)
warnings.simplefilter(action="ignore", category=DeprecationWarning)

#path = Path('D:/Pablo/CentroDatos/Datos/PENDIENTES/test/')
#path = Path('D:/Pablo/CentroDatos/Datos/PENDIENTES/CAREVA0316/')
#path = Path('D:/Pablo/CentroDatos/Datos/PENDIENTES/DEMERSALES2020/')


"""
    Process CTD files
"""
def check_casts(tmpdir, csr = None):
    
    if csr is None:
        tonemo = True
        tomedatlas = False
        plotting = True
        metadating = False
        coupling = False
    else:
        tonemo = False
        tomedatlas = True
        plotting = True
        metadating = True
        coupling = True        
    feda = False
    preprocessing = False
    
    path = Path(tmpdir)
    filenames = list(path.glob('*.cnv'))
    
    # Be sure to delete previous files
    outpath = path / "ctdcheck_output"   
    shutil.rmtree(outpath, ignore_errors=True)
    os.makedirs(outpath)    
      
    if tomedatlas:
        outpath_medatlas = outpath / "data-medatlas"
        if not os.path.exists(outpath_medatlas):
            os.makedirs(outpath_medatlas)
    if plotting:
        outpath_img = outpath / "figures"
        if not os.path.exists(outpath_img):
            os.makedirs(outpath_img)
    if tonemo:    
        outpath_flagged = outpath / "data-flagged"
        if not os.path.exists(outpath_flagged):
            os.makedirs(outpath_flagged)
    if metadating:
        outpath_cdi = outpath / "metadata"
        if not os.path.exists(outpath_cdi):
            os.makedirs(outpath_cdi)    
    
    """
    Load QC configuration and replicate for secondary sensors. By the moment,
    only temperature has secondary sensor in P09 vocabulary
    """
    cfg = ctd.load_cfg()
    cfg['TE01'] = cfg['TEMP']
    cfg['TE02'] = cfg['TEMP']
    
    """
    Load mapping between local variables and P09 vocabulary
    https://vocab.seadatanet.org/v_bodc_vocab_v2/search.asp?lib=p09&screen=0
    """
    mapping_P09_dict = ctd.load_mapping_P09()
    
    """
        Load CTD files
    """
    # Order files (list was unordered when running in server)
    filenames = sorted([f.name for f in filenames])


    # Turn off plotting if there are too many files
    if flash_messages and (len(filenames) > 150):
        if flash_messages:
                flash('Too many files. I am not going to make plots' 
                      + ' to not overload the server. If you need plots'
                      + ' upload files in several batches.', "danger")
        plotting = False
        

    casts = list()
    metadata = list()

    for idx, filename in enumerate(filenames):
        
        fname = path / filename  
        print('Processing file: ' + filename)
        
        # Load cast
        #cast = from_cnv(fname)
        try:
            cast = from_cnv(fname)
        except:
            print('Cannot properly parse CNV file. This file will be skipped.')
            if flash_messages:
                flash('<code>File ' + filename + '</code>' + ' This file will be skipped. We strongly encourage you to revise the file and repeat the process.', "danger")
            continue
        
        # Check if Dataframe is empty using dataframe's shape attribute
        if cast.shape[0] == 0:
            print('WARNING: No data in file ' + filename.name)
            if flash_messages:
                flash('<code>File ' + filename.name + '</code>' + ' No data in file. This file will be skipped', "danger")
            filenames = filenames.pop(idx)
            continue
        else:
            casts.append(cast)
            metadata.append(cast._metadata)
            del cast
      
            
    if not casts:
        if flash_messages:
            flash('File[s] no valid', "danger")
        return
        


    """
        Add pxylookup info to metadata
    """
    try:
        add_pxylookup_info(metadata)
    except:       
        print('Cannot retrieve info from XYLOOKUP API service')
        if flash_messages:
            flash('Cannot retrieve info from XYLOOKUP API service' 
                  + ' Distances from stations to coast and bathymetry data will not be tested', "warning")
    for idx, station in enumerate(metadata):
        if('shoredistance' in  metadata[idx] and metadata[idx]['shoredistance'] < 0):
            print('Station', metadata[idx]['name'], 'is', str(abs(metadata[idx]['shoredistance']/1000)), 'km inland')
            if flash_messages:
                flash('<code>Station ' + metadata[idx]['name'] + '</code> ' + str(abs(metadata[idx]['shoredistance']/1000)) + ' km inland. We strongly recommend that you check the position and repeat the quality check again', "danger")
     
    """
        Process dataframes
    """
    for idx, profile in enumerate(casts):
           
        #Rename stations
        metadata[idx]['station'] = str(idx+1)
                
        # Split cast
        down, up = profile.split()
        
        # Select downcast whenever possibe
        # If there are only upcast data, it still appears one row of data in downcast
        # In that case, select upcast
        if (len(down) <= 1) and (len(up)>1):
            df=up
            print('Upcast instead downcast selected in station ', metadata[idx]['name'])
            if flash_messages:
                flash('<code>File ' + metadata[idx]['name'] + '</code>' + ' Selected upcast instead downcast', "warning")
        else:    
            df = down
        
        # Split cast
        del down, up, profile
        
        """  PREPROCESSING 
            Check if profiling CTD Data processing is neccesary 
            Valid for SBE 9plus, 19, 19plus, 19plus V2, 25, 25plus, and 49
            
            According to SeaSoft Data Processing manual, steps to apply in cnv
            files:
            1) Low-pass filter
            2) Align CTD
            3) Cell thermal mass
            4) Loop edit
            5) Derive salinity
            6) Bin average
        """
        
        
        unique_depths = df.index.astype(int).drop_duplicates()       
        if len(df) > len(unique_depths):
            preprocessing = True
        
        if preprocessing:
            print('Ooops, it seems like preprocessing is required. I will try it for you!')
            if flash_messages:
                flash('<code>File ' + metadata[idx]['name'] + '</code>' + ' Ooops, it seems like preprocessing is required. I will try it for you!', "info")
            try:
                df = df.remove_above_water()
                if 'wildedit_in' not in metadata[idx]['config']:
                    print('Despike - Wild Edit Seabird-like function with Standard deviation 2 and 20 with window size 100')
                    df = df.despike(n1=2, n2=20, block=100)
                if 'filter_in' not in metadata[idx]['config']:
                    print('Filter a series with time constant of 0.15 s for pressure and sample rate 24 Hz')
                    df = df.lp_filter()
                if 'celltm_in' not in metadata[idx]['config']:
                    print('Cell thermal mass')
                    try:
                        df['c0S/m'] = cell_thermal_mass(df['t090C'].values,df['c0S/m'].values)
                    except:
                        pass
                if 'loopedit_in' not in metadata[idx]['config']:
                    print('Remove pressure reversals')
                    df = df.press_check()
                if 'sal00' not in df.columns:
                    try:                   
                        df['sal00'] = conversions.SP_from_C(df['c0S/m']*10,df['t090C'],df.index)
                        if flash_messages:
                            flash('<code>File ' + metadata[idx]['name'] + '</code>' + ' Derive practical salinity', "info")
                    except:
                        pass
                if 'binavg_in' not in metadata[idx]['config']:
                    print('Bin average the index to an interval of 1')
                    df = df.bindata(delta=1, method='interpolate')                    
            except:
                if flash_messages:
                    flash('<code>File ' + metadata[idx]['name'] + '</code>' + ' Preprocessing required and I could not do it for you', "danger")
                raise('Preprocessing required and I could not do it for you')


        # Pressure is stored as index. Rename, move to column and change to integer
        df.index.names = ['PRES']
        df = df.reset_index()
        df['PRES'] = df['PRES'].astype('int16')
        
        # Rename variables according with P09 vocabularies
        for column in df.columns:
            if column in mapping_P09_dict.keys():
                df = df.rename({column:mapping_P09_dict[column]['name_P09']}, axis=1)
               
        # Remove duplicate sensors by removing columns with same name in dataframe   
        keep_names = set()
        keep_icols = list()
        for icol, name in enumerate(df.columns):
            if name not in keep_names:
                 keep_names.add(name)
                 keep_icols.append(icol)
        df = df.iloc[:, keep_icols]
        if len(keep_names) != len(keep_icols):
            print('Duplicate sensors have been removed.')
            if flash_messages:
                flash('<code>File ' + metadata[idx]['name'] + '</code>' + ' Duplicate sensors have been removed', "warning")

        # Reorder columns
        # Columns will follow the order in the SBE2P09.json file
        columnsTitles = [d['name_P09'] for d in mapping_P09_dict.values()]
        keep_names = list()
        for name in columnsTitles:
            if name not in keep_names:
                keep_names.append(name)
        columnsTitles = keep_names 
        excluded_vars = [x for x in (set(df.columns)-set(columnsTitles)) if x != 'flag']
        if len(excluded_vars) > 0:
            print(metadata[idx]['name'], 'Following variables will not be processed: ', excluded_vars)
            if flash_messages:
                flash('<code>File ' + metadata[idx]['name'] + '</code>' + ' Following variables will not be processed: ' + ', '.join([x for x in excluded_vars]), "warning")
        df = df.reindex(columns=columnsTitles)
        df = df.dropna(axis=1, how='all')
        
        # Rename if secundary sensors exist
        if 'TEMP' and 'TE02' in df.columns:
            df = df.rename({'TEMP':'TE01'}, axis=1)
        
        # Find missing values in original data
        try:
            lines=metadata[idx]['config']
            matched_lines = [line for line in lines.split('\n') if "bad_flag" in line]    
            if matched_lines:               
                bad_flag = matched_lines[0].split("=")[1].strip()             
                df = df.replace(float(bad_flag), np.nan)
        except:
            print('Could not obtain missing flag from file')
        
        
        """             
           FLAGGING                
        """
        # Initialize flags in DataFrame
        df.init_flags()
        
        # Common tests (valid geoposition is included in location at sea)
        # Stored in df.flags['main']
        #df = df.valid_datetime(metadata[idx]).location_at_sea(metadata[idx])
        #df = df.valid_datetime(metadata[idx]).location_at_sea(metadata[idx], 'xylookup')
        df = df.valid_datetime(metadata[idx])


        # Apply tests (note that profile_envelop is not available for PSAL)
        # Stored in df.flags['TEMP'] and df.flags['PSAL']
        # Only works with TEMP and PSAL, not TE01 and TE02
        if 'TEMP' in df and 'PSAL' in df:
            df = df.density_inversion_test()

        for varname in df.keys():
            if varname == 'TEMP' or varname == 'TE01' or varname == 'TE02':
               
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
                result += str(df.flags[variable]["overall"][irow])
            flags[irow] = result
        df["FLAGS"] = flags.values()
             
        
        """    Exploratory Data Analysis (FEDA)   """
        if feda:
            feda = metadata[idx]['name']+'.html'
            fname = outpath / feda
            cast_report = pandas_profiling.ProfileReport(df, minimal=True)
            cast_report.to_file(fname)


        """               PLOTTING                """ 
        if plotting:
            style.use("seaborn-whitegrid")
            
            df.index = df["PRES"]  # Copy again PRES to index to use plotting functions
            
            fimg = metadata[idx]["name"] + ".png"
            fname = outpath_img / fimg
            
            
            if ('TEMP' or 'TE01') and 'PSAL' in df.columns:
                plot_cast_panel(df, metadata, idx, fname)
                        
            if idx == len(casts) - 1:
                fig, ax = plt.subplots()
                fig.suptitle("CTD stations")
                ax = plot_all_casts(metadata, ax=ax)
                fimg = "AllStations" + ".png"
                fname = outpath_img / fimg
                plt.savefig(fname)
                plt.close()

        """             FORMATTING                """

        # Write cnv files with flagged files
        # There is an option to create a file to be ingested in NEMO software
        # to_cnv_medatlas(df, metadata, output_file, edmo_code)
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
                
            
        
    """             REPORT TO USER                """
    #       Out of the loop to report once      

    if flash_messages:
        flash('Rename variables according to <a href="https://vocab.seadatanet.org/v_bodc_vocab_v2/search.asp?lib=P09">P09 vocabulary</a>' , "success")
        flash('Test: valid date and time' , "success")
        flash('Test: density inversion' , "success")
        flash('Test: instrument range' , "success")
        flash('Test: global range' , "success")
        flash('Test: regional range based on EuroGOOS manual' , "success")
        flash('Test: gradient depth conditional' , "success")
        flash('Test: spike depth conditional' , "success")
        flash('Test: digital roll over' , "success")
        flash('Test: deviation from World Ocean Atlas climate values', "success")
        flash('Test: profile envelop (only temperature)', "success")
        flash('Test: stuck data', "success")
        
    
    """             TEST POSITIONS                """
    #       Out of the loop to test once        
    # 1) Test if CTDs are inside the bounding box reported in the CSR
    # 2) Test the time between consecutive samplings (vessel speed test)  
    
    if csr and metadata:
        try:
            csr_bounding_box_test(metadata, csr)
        except:
            if flash_messages:
                flash('Test: CTDs inside CSR bounding box', "danger")
    try:
        speed_test(metadata, cfg)
    except:
        if flash_messages:
            flash('Test: speed of vessel', "danger")
    
               
    """             METADATING (CDIs)                """
    if metadating:
        fname = "CTD_" + csr["cruise_id"] + ".dat"
        fname = outpath_medatlas / fname
        create_cdi_from_medatlas(fname, outpath_cdi, csr)
        if flash_messages:
            flash('CDI metadata generated', "success")
        if coupling:
            if csr['custodian_code'] == '353':        
                coupling_file = outpath_cdi / "coupling_table.txt"                   
                with open(coupling_file, "w") as outfile:                      
                    for filename in list(outpath_cdi.glob("*.xml")):
                        cdi_filename = os.path.splitext(filename.name)[0]
                        outfile.write(cdi_filename + ';3;MEDATLAS;CTD/' +  csr['cruise_time'][6:10] + '/' + fname.name + '\n')               
                if flash_messages:
                    flash('Coupling table generated for IEO-NODC', "success")
            else:
                print('Coupling table can be only generated for IEO-NODC')

    return metadata


# ## Load CSR file and check CTDs (Uncomment if run locally)
# csr = load_csr(path)
# metadata = check_casts(path, csr)


