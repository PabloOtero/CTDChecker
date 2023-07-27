# -*- coding: utf-8 -*-
"""
Created on Wed Jul  3 14:23:11 2019
Last update on 10 March 2023

@author: pablo.otero@ieo.csic.es
         Centro Nacional Instituto Español de Oceanografía (IEO-CSIC)
         
This is a Flask version. To run it, open a terminal, activate your environment
and type in the working directory 'python app.py'. 
Open your browser at http://localhost:5000/

IMPORTANT: To run locally, you have to modify config.py.
  
WARNING Oct 2021 Fails with some updates in libraries
 lxml==4.6.1
 pandas==1.1.4    
         e.g. pip install lxml==4.6.1
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
#import pandas_profiling
from flask import flash
import xarray as xr
import numpy as np

import config
if config.RUN_LOCALLY:
    flash_messages = False
else:
    flash_messages = True


plt.ioff()
matplotlib.use('Agg')
warnings.filterwarnings("ignore",category=matplotlib.cbook.mplDeprecation)
warnings.simplefilter(action="ignore", category=FutureWarning)
warnings.simplefilter(action="ignore", category=DeprecationWarning)


"""
    Process CTD files
"""
def check_casts(tmpdir, csr = None, tonetcdf = False, merged_ncfile = False):
    
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
            
    if tonetcdf:
        outpath_netcdf = outpath / "data-netcdf"
        if not os.path.exists(outpath_netcdf):
            os.makedirs(outpath_netcdf)             


    """
    Load mapping between SBE local variables and P09 vocabulary
    You can find the P09 vocabulary here:
    https://vocab.seadatanet.org/v_bodc_vocab_v2/search.asp?lib=p09&screen=0
    """
    mapping_SBEtoP09_dict = ctd.load_mapping_SBEtoP09()
    
    """
    Load QC configuration and replicate for secondary sensors. By the moment,
    only temperature has secondary sensor in P09 vocabulary
    This file also includes additional information for variables, 
    as P09 to P01 mapping
    """
    cfg = ctd.load_cfg()
    cfg['TE01'] = cfg['TEMP']
    cfg['TE02'] = cfg['TEMP']
    cfg['TE02']['name_P01'] = 'TEMPPR02'
    
  
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
            filenames.pop(idx)
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
        # In the upcast is at least the double size than downcast, select it
        #if (len(down) <= 1) and (len(up)>1):
        if (len(up)>(len(down)*2)):
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

        # # After preprocessing, the length of data could be not enough. 
        # if len(df) < 2:
        #     print('WARNING: After preprocessing, not enough data to continue with file ' + metadata[idx]['name'])
        #     if flash_messages:
        #         flash('<code>File ' + metadata[idx]['name'] + '</code>' + ' After some preprocessing, not enough bin-averaged depths to continue. Drop this file and start again.', "danger")
        #     return

        # Pressure is stored as index. Rename, move to column and change to integer
        df.index.names = ['PRES']
        df = df.reset_index()
        df['PRES'] = df['PRES'].astype('int16')
        
        # Rename variables according with P09 vocabularies
        for column in df.columns:
            if column in mapping_SBEtoP09_dict.keys():
                df = df.rename({column:mapping_SBEtoP09_dict[column]['name_P09']}, axis=1)
               
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
        columnsTitles = [d['name_P09'] for d in mapping_SBEtoP09_dict.values()]
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
            df = df.density_inversion_test_improved()

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
                result += str(df.qc_flags[variable]["overall"][irow])
            flags[irow] = result
        df["FLAGS"] = flags.values()
                       
        
        """    Exploratory Data Analysis (FEDA)   """
        # if feda:
        #     feda = metadata[idx]['name']+'.html'
        #     fname = outpath / feda
        #     cast_report = pandas_profiling.ProfileReport(df, minimal=True)
        #     cast_report.to_file(fname)


        """               PLOTTING                """ 
        if plotting:
            style.use("seaborn-whitegrid")
            
            df.index = df["PRES"]  # Copy again PRES to index to use plotting functions
            
            fimg = metadata[idx]["name"] + ".png"
            fname = outpath_img / fimg
            
            
            if ('TEMP' or 'TE01') and 'PSAL' in df.columns:
                try:
                    plot_cast_panel(df, metadata, idx, fname)
                except:
                    if flash_messages:
                        flash('<code>File ' + metadata[idx]['name'] + '</code>' + ' Failed to plot.', "warning")
                    print('Failed to plot. Maybe there is a problem with dimensions.')
                    continue
                        
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
               
        # Warning, we are passing a non-unmutable dataframe
        # this only works for the last profile.
        netcdf_files = []        
        if tonetcdf:
            fname = csr["cruise_id"] + "_" + metadata[idx]["station"].zfill(5) + "_H10" + ".nc"            
            try:
                netcdf_files.append(fname)
                fname = outpath_netcdf / fname
                df2nc(df, fname, metadata[idx], cfg, csr)              
            except:
                if flash_messages:
                    flash('<code>Cannot create netcdf file for station' + metadata[idx]["station"] + '</code>', "warning")
                else:
                    print('Cannot create netcdf file for', fname)
  
    
    if tonetcdf and merged_ncfile:
        try:            
            fname = csr["cruise_id"] + "_merged_H10" + ".nc"
            output_file = outpath_netcdf / fname
            
            filenames = list(outpath_netcdf.glob('*.nc'))
        
            # Load the files into a list of xarray datasets
            datasets = [xr.open_dataset(file_path, mask_and_scale=False) for file_path in filenames]
        
            # Find the maximum value of MAXZ across all datasets
            max_maxz = max([ds.MAXZ.max() for ds in datasets])
           
            # Create a new array with a range of values from 0 to max_maxz
            new_maxz = xr.DataArray(np.arange(0, max_maxz+1), dims=('MAXZ',))
        
            # Interpolate each dataset to the new_maxz values along the MAXZ dimension
            resampled_datasets = [ds.interp(MAXZ=new_maxz, kwargs={"fill_value": None}) for ds in datasets]
               
            # Replace any NaN values with the corresponding FillValue
            filled_datasets = []
            for ds in resampled_datasets:
                filled_vars = {}
                for var_name, var in ds.variables.items():
                    if '_FillValue' in var.attrs:
                        fill_value = var.attrs['_FillValue']
                        filled_var = var.fillna(fill_value)
                        filled_vars[var_name] = filled_var
                    else:
                        filled_vars[var_name] = var                    
                filled_datasets.append(xr.Dataset(filled_vars, coords=ds.coords))
                
            # Merge the filled datasets along the INSTANCE dimension
            merged_dataset = xr.concat(filled_datasets, dim='INSTANCE')      
            merged_dataset.to_netcdf(output_file, unlimited_dims='INSTANCE')

            # Make sure netcdf files are not in use
            for ds in datasets:
                ds.close()            
            for ds in resampled_datasets:
                ds.close()
            for ds in filled_datasets:
                ds.close()                
            
            if merged_ncfile:
                for f in filenames:
                    os.remove(f)
            
        except:
            if flash_messages:
                flash('Something was wrong during netcdf merging. We will try to provide you with nc individual files. Cross fingers!', "danger")
            else:
                print('Something was wrong during netcdf merging')
    
    
        
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


if config.RUN_LOCALLY:    
    tmpdir = config.PATH_LOCAL   
    csr = load_csr(tmpdir)
    metadata = check_casts(tmpdir, csr, tonetcdf = config.TO_NETCDF, merged_ncfile = config.MERGED_NCFILE)


