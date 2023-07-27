# -*- coding: utf-8 -*-
"""
Created on Fri Mar 10 11:58:39 2023

@author: potero
"""

""" Export the parsed data into a NetCDF following different patterns
"""

from datetime import datetime, date, time
import netCDF4
from netCDF4 import stringtochar
import numpy as np
from numpy import dtype
import pandas as pd
import jdcal


#module_logger = logging.getLogger("seabird.netcdf")


# Example of character to byte
# s = 'A'
# b=s.encode('ascii')
## if you print whole b, it still displays it as if its original string
# print(b)
## but print first item from the array to see byte value
# print b[0]



def df2nc(data, filename, metadata, cfg, csr=None):
    """Save a CNV() object into filename as a NetCDF
    To save the CTD.cnv into a NetCDF, just run:
    profile = cnv.fCNV("CTD.cnv")
    cnv2nc(profile, "CTD.nc")
    """
    
  
    #nc = netCDF4.Dataset(filename, "w", format="NETCDF4_CLASSIC")
    nc = netCDF4.Dataset(filename, "w")

    nc.history = "Created by CTDCheck"

    nc.date_created = datetime.now().isoformat()

    # Write "Global attributes"
    #
    # title — a succinct description of the data set
    # insititute — the organisation where the data were produced
    # source — how the data were produced, e.g. model type, run number and circumstances
    # history — an audit trail of data set processing
    # references — a list of references that describe the data or the methodology used
    # comment — other useful information not covered elsewhere that adds value
    # author — the person(s) who generated the data 
    nc.__setattr__('title', 'SeaDataNet CFPoint PHYSICOCHEMICAL PROFILE - Generated by CTDCheck software by IEO-CSIC - ' + datetime.now().isoformat())
    if csr is None:
        nc.__setattr__('institute', 'Not known')
    else:
        nc.__setattr__('institute', csr['custodian_name'])           
    if csr is None:
        source = 'CTD data acquired with instrument ' +  metadata['instrument'] + ' in the ' + metadata['cruise']
    else:
        source = 'CTD data acquired with instrument ' +  metadata['instrument'] + ' by ' + csr['acquisition_center'] + ' in the ' + csr['cruise_name']
    nc.__setattr__('source', source)   
    nc.__setattr__('history', 'Data preprocessed with SeaBird software and postprocessed with CTDCheck by IEO-CSIC')       
    nc.__setattr__('references', 'http://wiki.ieo.es/books/centro-nacional-de-datos-oceanogr%C3%A1ficos/page/ieo-ctd-checker')       
    nc.__setattr__('comment', 'THESE DATA ARE PROVIDED -AS IS-, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.')  
    nc.__setattr__('author', 'National Center Spanish Institute of Oceanography (IEO-CSIC)')
    nc.__setattr__('Conventions', 'SeaDataNet_1.0 CF-1.6')
    nc.__setattr__('featureType', 'profile')
    nc.__setattr__('date_update', datetime.now().isoformat())

    #Get time and coordinates
    ctd_time = metadata['time']
    fraction_day = ((ctd_time.hour*60+ctd_time.minute)*60+ctd_time.second)/86400
    ctd_time = int(sum(jdcal.gcal2jd(ctd_time.year, ctd_time.month, ctd_time.day))) + fraction_day   
    lat = metadata['lat']
    lon = metadata['lon']
    maxz = len(data[data.keys()[0]])


    # Write DIMENSIONS
    #
    nc.createDimension('INSTANCE', 1) #UNLIMITED put None
    nc.createDimension('MAXZ', maxz)
    nc.createDimension('REFMAX', 3)
    nc.createDimension('STRING23', 23)
    nc.createDimension('STRING177', 177)
    
       
    # Write VARIABLES
    #
    cdf_variables = {}
    
    nc_name = 'csr'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, int)
    cdf_variables[nc_name].__setattr__('grid_mapping_name', 'latitude_longitude') 
    cdf_variables[nc_name].__setattr__('epsg_code', 'EPSG:4326') 
    cdf_variables[nc_name].__setattr__('semi_major_axis', 6378137.) 
    cdf_variables[nc_name].__setattr__('inverse_flattening',298.257223563) 
  
    nc_name = 'SDN_EDMO_CODE'
    cdf_variables[nc_name] = nc.createVariable(nc_name, int, ('INSTANCE'))
    cdf_variables[nc_name].__setattr__('long_name', 'European Directory of Marine Organisations code for the CDI partner')   
    if csr is None:
        cdf_variables[nc_name][:] = 353
    else:
        cdf_variables[nc_name][:] = int(csr['originator_code'])
        
    nc_name = 'SDN_CRUISE'    
    cdf_variables[nc_name] = nc.createVariable(nc_name, str, ('INSTANCE','STRING23'))
    cdf_variables[nc_name].__setattr__('long_name', 'CRUISE NAME')   
    if csr is None:
        cdf_variables[nc_name].__setattr__('shipcode', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('shipname', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('start_date', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('end_date', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('region', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('country', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('laboratories', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('chiefscientist', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('project', 'UNKNOWN')
        cdf_variables[nc_name].__setattr__('datacenter', 'UNKNOWN')
        str_out = np.array(['UNKNOWN'], dtype='object')
        cdf_variables[nc_name][:] = str_out
    else:
        cdf_variables[nc_name].__setattr__('shipcode', csr['cruise_id'][0:4])
        cdf_variables[nc_name].__setattr__('shipname', csr['vessel_name'])
        cdf_variables[nc_name].__setattr__('start_date', csr['cruise_time'][0:10].replace('/','-'))
        cdf_variables[nc_name].__setattr__('end_date', csr['cruise_time'][11:].replace('/','-'))
        cdf_variables[nc_name].__setattr__('region', csr['water_body'])
        cdf_variables[nc_name].__setattr__('country', csr['cruise_id'][0:2])
        cdf_variables[nc_name].__setattr__('laboratories', csr['acquisition_center'])
        cdf_variables[nc_name].__setattr__('chiefscientist', 'chief_scientist')
        cdf_variables[nc_name].__setattr__('project', 'project_acronym')
        cdf_variables[nc_name].__setattr__('datacenter', csr['custodian_code'])
        str_out = np.array([csr['cruise_id']], dtype='object')
        cdf_variables[nc_name][:] = str_out
    cdf_variables[nc_name].__setattr__('availability', 'unrestricted')
    
    
    nc_name = 'SDN_STATION'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, 'S1', ('INSTANCE','STRING23'))
    cdf_variables[nc_name].__setattr__('long_name', 'List of station numbers')
    str_out = np.array([metadata['station']], dtype='object')
    cdf_variables[nc_name][:] = str_out
   
    nc_name = 'SDN_LOCAL_CDI_ID'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, 'S1', ('INSTANCE','STRING23'))
    cdf_variables[nc_name].__setattr__('long_name', 'SeaDataNet CDI identifier')   
    cdf_variables[nc_name].__setattr__('cf_role', 'profile_id')   
    if csr:
        local_cdi_id = csr["cruise_id"] + "_" + metadata["station"].zfill(5) + "_H10"
    else:
        local_cdi_id = "UNKNOWN"
    str_out = np.array([local_cdi_id], dtype='object')
    cdf_variables[nc_name][:] = str_out
        
    nc_name = 'SDN_XLINK'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, 'S1', ('INSTANCE','STRING23','STRING177'))
    cdf_variables[nc_name].__setattr__('long_name', 'External resource linkages')
    if csr:        
        str_out = '*<sdn_reference xlink:href="https://csr.seadatanet.org/report/edmo/' + csr['originator_code'] + '/' + csr['cruise_id'] + '/xml" xlink:role="isObservedBy" xlink:type="SDN:L23::CSR"/>'  
    else:           
        str_out = np.array(["UNKNOWN"], dtype='object')
        cdf_variables[nc_name][:] = str_out
        
    nc_name = 'SDN_BOT_DEPTH'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, float, ('INSTANCE',), fill_value = -999.)
    cdf_variables[nc_name].__setattr__('long_name', 'Bathymetric depth at profile measurement site') 
    cdf_variables[nc_name].__setattr__('sdn_parameter_urn', 'SDN:P01::MBANZZZZ') 
    cdf_variables[nc_name].__setattr__('sdn_parameter_name', 'Sea-floor depth (below instantaneous sea level) {bathymetric depth} in the water body') 
    cdf_variables[nc_name].__setattr__('sdn_uom_urn', 'SDN:P06::ULAA') 
    cdf_variables[nc_name].__setattr__('sdn_uom_name', 'Metres') 
    cdf_variables[nc_name].__setattr__('units', 'meters') 
    cdf_variables[nc_name].__setattr__('standard_name', 'sea_floor_depth_below_sea_surface') 
    cdf_variables[nc_name][:] = metadata['depth']

    nc_name = 'LONGITUDE'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, 'f8', ('INSTANCE',), fill_value = -99999.)
    cdf_variables[nc_name].__setattr__('long_name', 'Longitude') 
    cdf_variables[nc_name].__setattr__('sdn_parameter_urn', 'SDN:P01::ALONZZ01') 
    cdf_variables[nc_name].__setattr__('sdn_parameter_name', 'Longitude east') 
    cdf_variables[nc_name].__setattr__('sdn_uom_urn', 'SDN:P06::DEGE') 
    cdf_variables[nc_name].__setattr__('sdn_uom_name', 'Degrees east') 
    cdf_variables[nc_name].__setattr__('units', 'degrees_east') 
    cdf_variables[nc_name].__setattr__('standard_name', 'longitude') 
    cdf_variables[nc_name].__setattr__('axis', 'X') 
    cdf_variables[nc_name].__setattr__('ancillary_variables', 'POSITION_SEADATANET_QC') 
    cdf_variables[nc_name].__setattr__('grid_mapping', 'csr')
    cdf_variables[nc_name][:] = lon

    nc_name = 'LATITUDE'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, 'f8', ('INSTANCE',), fill_value = -99999.)
    cdf_variables[nc_name].__setattr__('long_name', 'Latitude') 
    cdf_variables[nc_name].__setattr__('sdn_parameter_urn', 'SDN:P01::ALATZZ01') 
    cdf_variables[nc_name].__setattr__('sdn_parameter_name', 'Latitude north') 
    cdf_variables[nc_name].__setattr__('sdn_uom_urn', 'SDN:P06::DEGN') 
    cdf_variables[nc_name].__setattr__('sdn_uom_name', 'Degrees north') 
    cdf_variables[nc_name].__setattr__('units', 'degrees_north') 
    cdf_variables[nc_name].__setattr__('standard_name', 'latitude') 
    cdf_variables[nc_name].__setattr__('axis', 'Y') 
    cdf_variables[nc_name].__setattr__('ancillary_variables', 'POSITION_SEADATANET_QC') 
    cdf_variables[nc_name].__setattr__('grid_mapping', 'csr')
    cdf_variables[nc_name][:] = lat        
            
    nc_name = 'POSITION_SEADATANET_QC'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, 'b', ('INSTANCE',), fill_value = '9'.encode('ascii')[0])
    cdf_variables[nc_name].__setattr__('long_name', 'SeaDataNet quality flag') 
    cdf_variables[nc_name].__setattr__('Conventions', 'SeaDataNet measurand qualifier flags') 
    cdf_variables[nc_name].__setattr__('sdn_conventions_urn', 'SDN:L20::') 
    flagged_array = [numeric_string.encode('ascii')[0] for numeric_string in ['0','1','2','3','4','5','6','7','8','9','A','Q']]
    cdf_variables[nc_name].__setattr__('flag_values', flagged_array) 
    cdf_variables[nc_name].__setattr__('flag_meanings', 'no_quality_control good_value probably_good_value probably_bad_value bad_value changed_value value_below_detection value_in_excess interpolated_value missing_value value_phenomenon_uncertain value_below_limit_of_quantification')    
    cdf_variables[nc_name][:] = '1'.encode('ascii')[0]

    nc_name = 'TIME'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, 'f8', ('INSTANCE',), fill_value = -99999.)
    cdf_variables[nc_name].__setattr__('long_name', 'Chronological Julian Date') 
    cdf_variables[nc_name].__setattr__('sdn_parameter_urn', 'SDN:P06::UTAA') 
    cdf_variables[nc_name].__setattr__('sdn_parameter_name', 'Julian Date (chronological)') 
    cdf_variables[nc_name].__setattr__('sdn_uom_urn', 'SDN:P06::UTAA') 
    cdf_variables[nc_name].__setattr__('sdn_uom_name', 'Days') 
    cdf_variables[nc_name].__setattr__('units', 'days since -4713-01-01T00:00:00Z') 
    cdf_variables[nc_name].__setattr__('standard_name', 'time') 
    cdf_variables[nc_name].__setattr__('axis', 'T') 
    cdf_variables[nc_name].__setattr__('calendar', 'julian')
    cdf_variables[nc_name][:] = ctd_time

    nc_name = 'TIME_SEADATANET_QC'  
    cdf_variables[nc_name] = nc.createVariable(nc_name, 'b', ('INSTANCE',), fill_value = '9'.encode('ascii')[0])
    cdf_variables[nc_name].__setattr__('long_name', 'SeaDataNet quality flag') 
    cdf_variables[nc_name].__setattr__('Conventions', 'SeaDataNet measurand qualifier flags') 
    cdf_variables[nc_name].__setattr__('sdn_conventions_urn', 'SDN:L20::') 
    flagged_array = [numeric_string.encode('ascii')[0] for numeric_string in ['0','1','2','3','4','5','6','7','8','9','A','Q']]
    cdf_variables[nc_name].__setattr__('flag_values', flagged_array) 
    cdf_variables[nc_name].__setattr__('flag_meanings', 'no_quality_control good_value probably_good_value probably_bad_value bad_value changed_value value_below_detection value_in_excess interpolated_value missing_value value_phenomenon_uncertain value_below_limit_of_quantification')    
    cdf_variables[nc_name][:] = '1'.encode('ascii')[0]


    for column in data:
        if column in cfg and column != 'FLAGS':
            try:
                nc_name = column
                cdf_variables[nc_name] = nc.createVariable(nc_name, 'f8', ('INSTANCE','MAXZ'), fill_value = -99999.)
                cdf_variables[nc_name].__setattr__('long_name',cfg[column]['P01_preferred_label'])
                cdf_variables[nc_name].__setattr__('sdn_parameter_urn', 'SDN:P01::' + cfg[column]['name_P01']) 
                cdf_variables[nc_name].__setattr__('sdn_parameter_name', cfg[column]['P01_preferred_label']) 
                cdf_variables[nc_name].__setattr__('sdn_uom_urn', 'SDN:P06::' + cfg[column]['name_P06']) 
                cdf_variables[nc_name].__setattr__('sdn_uom_name', cfg[column]['P06_preferred_label']) 
                cdf_variables[nc_name].__setattr__('units', cfg[column]['P06_preferred_label'].lower() ) 
                cdf_variables[nc_name].__setattr__('axis', 'Z') 
                cdf_variables[nc_name].__setattr__('ancillary_variables', column + '_SEADATANET_QC') 
                cdf_variables[nc_name].__setattr__('positive', 'down')
                try:
                    cdf_variables[nc_name].__setattr__('standard_name', cfg[column]['cf_standard_name']) 
                except:
                    print('No CF standard name for',column,'found in config file')
                cdf_variables[nc_name][:] = data[column]
                
                nc_name = column + '_SEADATANET_QC'  
                cdf_variables[nc_name] = nc.createVariable(nc_name, 'b', ('INSTANCE','MAXZ'), fill_value = '9'.encode('ascii')[0])
                cdf_variables[nc_name].__setattr__('long_name', 'SeaDataNet quality flag') 
                cdf_variables[nc_name].__setattr__('Conventions', 'SeaDataNet measurand qualifier flags') 
                cdf_variables[nc_name].__setattr__('sdn_conventions_urn', 'SDN:L20::')
                flagged_array = [numeric_string.encode('ascii')[0] for numeric_string in ['0','1','2','3','4','5','6','7','8','9','A','Q']]
                cdf_variables[nc_name].__setattr__('flag_values', flagged_array) 
                cdf_variables[nc_name].__setattr__('flag_meanings', 'no_quality_control good_value probably_good_value probably_bad_value bad_value changed_value value_below_detection value_in_excess interpolated_value missing_value value_phenomenon_uncertain value_below_limit_of_quantification')    
                desired_array = [str(numeric_string).encode('ascii')[0] for numeric_string in data.qc_flags[column]['overall']]
                desired_df = pd.DataFrame(desired_array, columns=['variable'])
                cdf_variables[nc_name][:] = desired_df['variable']            
            except:
                print('Cannot write', column, 'variable to netcdf file')   
        

    nc.close()
    
    return