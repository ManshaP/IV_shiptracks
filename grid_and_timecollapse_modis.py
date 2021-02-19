import numpy as np
import matplotlib.pyplot as plt
import os
import glob
import copy
import sys
import datetime
import iris
from pyhdf.SD import SD, SDC
import time
from cis.data_io.gridded_data import GriddedDataList

os.environ['CIS_PLUGIN_HOME'] = '/home/users/pete_nut/plugins/'
from cis import read_data, read_data_list, get_variables


#function that checks a list of files for overlap 
#with the coordinate interval lat=[-35,0], lon=[-90,-70]
#and deletes the filenames without overlap

def delete_no_overlap(filelist):
    delfiles=[]
    for filename in filelist:
        #print(filename)
        dataset = SD(filename, SDC.READ)
        lats = dataset.select('Latitude').get()
        lons = dataset.select('Longitude').get()
        #print(lats.min(), lats.max(), lons.min(), lons.max())
        if (lats.max() < -35.  or lats.min() > 0 or lons.max() < -90 or lons.min() > -70 or lons.max()>170 ):
            #print(filename)
            delfiles.append(filename)
        #else: print(filename)
    
    for filename in delfiles:
        filelist.remove(filename)
    return filelist

months=['00','01','02','03','04','05','06','07','08','09','10','11','12']
modis_year = '2018'
modis_dir = '/neodc/modis/data/MYD06_L2/collection61/{}/{}/{}/'
modis_month = months[10]

days=['01','02','03','04','05','06','07','08','09',
      '10','11','12','13','14','15','16','17','18','19',
      '20','21','22','23','24','25','26','27','28']#,'29', '30','31']

#modis_day = days[7]
for modis_day in ['14']:
    print('gridding for day {}/{}/{}'.format(modis_day, modis_month, modis_year))
    #ROI is UTC-5 so there is no daylight before ~1200 UTC --> Overpass time for Terra is around 1800 UTC
    #make a list of MODIS files on the day, check for overlap and delete those without 
    modis_daily = sorted(glob.glob(modis_dir.format(modis_year, modis_month, modis_day) + '*.hdf'))
    end_day = glob.glob(modis_dir.format(modis_year, modis_month, modis_day) + '*.2030.*.hdf')[0]
    end_day = modis_daily.index(end_day)
    start_time=glob.glob(modis_dir.format(modis_year, modis_month, modis_day) + '*.1300.*.hdf')[0]
    start_time=modis_daily.index(start_time)
    modis_daily = modis_daily[start_time:end_day]
    modis_daily=delete_no_overlap(modis_daily)


    #get data, need to do seperately because of different resolution
    mod_hr=read_data_list(modis_daily,
                       ['Cloud_Fraction',
                        'Cloud_Top_Temperature'])
    mod_lr=read_data_list(modis_daily,
                          ['Cloud_Effective_Radius',
                           'Cloud_Effective_Radius_Uncertainty',
                           'Cloud_Water_Path'], product='MOD06_HACK')
#     mod_hr=read_data_list(modis_daily,
#                        ['Cloud_Fraction'])
#     mod_lr=read_data_list(modis_daily,
#                           ['Cloud_Water_Path',
#                           'Cloud_Water_Path_Uncertainty',
#                           'Cloud_Optical_Thickness',
#                           'Cloud_Optical_Thickness_Uncertainty'], product='MOD06_HACK')

    #grid ungridded data to 0.1 deg grid, time dimension is collapsed (taking a mean?)
    agg_mod_lr=mod_lr.aggregate(x=[-90.05,-69.95,0.1], y=[-35.05,0.05,0.1])
    agg_mod_hr=mod_hr.aggregate(x=[-90.05,-69.95,0.1], y=[-35.05,0.05,0.1])


    #add the two datasets together and save
    all_data=GriddedDataList([agg_mod_hr[0], agg_mod_lr[0], agg_mod_lr[3],agg_mod_lr[6],  ])
    all_data.save_data('/gws/nopw/j04/eo_shared_data_vol2/scratch/pete_nut/regrid_modis_aqua/'+modis_year+ modis_month + modis_day+".nc")

