import numpy as np
import glob
import copy
import sys
import datetime
import iris
from pyhdf.SD import SD, SDC
import time
import xarray as xr
from cis import read_data, read_data_list, get_variables



def load_emis(emis_dir, month, crop_max=10):
    filelist=glob.glob(emis_dir + month + ".nc")
    da=xr.open_mfdataset(filelist)
    da['SOx']=xr.where(da['SOx']<0, 0, da['SOx'])
    da['SOx']=xr.where(da['SOx']>crop_max, 0, da['SOx'])
    return da['SOx'].transpose('latitude', 'longitude', 'time')

def load_modis(modis_dir, month, crop_max=100, uncert_thresh=8):
    filelist=glob.glob(modis_dir + '2018' + month + "*.nc")
    ds=xr.open_mfdataset(filelist)
    #print('loading done, starting to process')

    re=ds['Cloud_Effective_Radius'].where(ds['Cloud_Top_Temperature'] > 272.15-15, np.nan)
    print(np.isnan(re).values.sum()/(np.logical_not(np.isnan(re)).values.sum()+np.isnan(re).values.sum()))
    
    re=re.where(ds['Cloud_Effective_Radius_Uncertainty']<uncert_thresh, np.nan)
    print(np.isnan(re).values.sum()/(np.logical_not(np.isnan(re)).values.sum()+np.isnan(re).values.sum()))
    
    re=xr.where(re>1000, np.nan, re)
    re=xr.where(re<4, np.nan, re)
    print(np.isnan(re).values.sum()/(np.logical_not(np.isnan(re)).values.sum()+np.isnan(re).values.sum()))
    
    ctt=ds['Cloud_Top_Temperature'].where(ds['Cloud_Top_Temperature'] < 500, np.nan)
    
    return re, ctt


def load_modis_outcome(modis_dir, month, target='Cloud_Water_Path', uncert_thresh=8):
    filelist=glob.glob(modis_dir + '2018' + month + "*.nc")
    ds=xr.open_mfdataset(filelist)
    #print('loading done, starting to process')

    re=ds[target]#.where(ds['Cloud_Top_Temperature'] > 272.15-15, np.nan)
    
    print(np.isnan(re).values.sum()/(np.logical_not(np.isnan(re)).values.sum()+np.isnan(re).values.sum()))
    
    if target=='Cloud_Fraction': re=re.where(ds[target]<=1., np.nan)
    if target=='Cloud_Optical_Thickness': re=re.where(ds[target]<=1e10, np.nan)
    if target=='Cloud_Water_Path': re=re.where(ds[target]<=1e10, np.nan)


    print(np.isnan(re).values.sum()/(np.logical_not(np.isnan(re)).values.sum()+np.isnan(re).values.sum()))
    return re

def condensation_rate(T):
    cr=0.0192*T - 4.293
    return cr

def drop_num(r, cot, temp):
   
    r=np.power(r*10**(-6),-5/2)
    cot=np.power(cot,1/2)
    drop_num=np.multiply(r, cot)
    drop_num=np.multiply(drop_num, condensation_rate(temp))
    #prop constant
    drop_num*=1.37e-5
    #convert to per cm^3
    drop_num/=1e6
    return drop_num


def coarsened_emis(emis, window_size=3):
    emis_coarsened=emis.rolling(latitude=window_size, longitude=window_size,
                                min_periods=1, center=True).reduce(np.mean)
    return emis_coarsened

#expects one variable xr.DaraArray, returns this array filtered for those values that occur 
#'hours' before the modis overpass which is around 18-19h UTC
def time_collapse_emis(da, hours, overpass_hour=19):
    days_in_month=len(da.time.values)//24
    hours_ind=[]
    #print(da.isel(time=slice(24+hours_ind[0].astype(int),hours_ind[-1].astype(int))))
    if overpass_hour-hours<0:
        for i in range(days_in_month-1):
            for j in range(hours):
                hours_ind=np.append(hours_ind,(i+1)*24+overpass_hour-hours+j)
        emis=da.isel(time=hours_ind.astype(int))
        #print(emis.time)
        emis=emis.resample(time='24H', base=24+overpass_hour-hours, closed='left')
        #print("Caution: No data for the first day of the month")
    elif overpass_hour>24:
        for i in range(days_in_month-1):
            for j in range(hours):
                hours_ind=np.append(hours_ind,i*24+overpass_hour-hours+j)
        emis=da.isel(time=hours_ind.astype(int))
        #print(emis.isel(time=0).mean().values)
        emis=emis.resample(time='24H', base=overpass_hour-hours, closed='left')
        #print("Caution: No data for the first day of the month")
    else:
        for i in range(days_in_month):
            for j in range(hours):
                hours_ind=np.append(hours_ind,i*24+overpass_hour-hours+j)
        emis=da.isel(time=hours_ind.astype(int))
        #print(emis.isel(time=0).mean().values)
        emis=emis.resample(time='24H', base=overpass_hour-hours, closed='left')

    emis=emis.reduce(np.mean)
    return emis

def select_lonlats(emissions_da, r_eff_da, lats, lons):
    emis=emissions_da.sel(longitude=lons,latitude=lats)
    re=r_eff_da.sel(longitude=lons,latitude=lats)
    return re, emis

def select_data(r_eff_da,emissions_da, 
                lats=slice(-35,0), lons=slice(-90,-70), 
                coarsening=3, 
                end_h=19, emis_h=1):
    
    re, emis=select_lonlats(emissions_da, r_eff_da, lats, lons)
    #print(re.mean().values)
    emis=time_collapse_emis(emis, emis_h, overpass_hour=end_h)
    
    # if the emis collapse does not reach into the day before, we need to 
    if end_h-emis_h>=0: emis=emis.isel(time=slice(1, len(emis.time)))
    # if the end_hour of emission collapse is after midnight, everything good,
    # because we get rid of the last modis day anyway. If not, we need to get rid of the last emis day
    if end_h<=24: emis=emis.isel(time=slice(0, len(emis.time)-1))
    
    #always crop the first day of sat_image
    re=re.isel(time=slice(1, len(re.time)-1))
    #print(re.mean().values)
    if coarsening != 1: emis=coarsened_emis(emis, window_size=coarsening)
    #print(re.mean().values)

    
    return re, emis

# returns the effect of pollution on the size of cloud droplets 
def re_diff_emis(threshold, re, emis):
    
    #print("division middle")
    prist=np.where(emis > threshold, np.nan, re)

    #prist=np.where(emis == 0., np.nan, prist)
    re_prist=np.nanmean(prist)
    pristpoints=np.logical_not(np.isnan(prist)).sum()

#     s=np.shape(re)
#     x=np.random.rand(s[0],s[1],s[2])
#     poll=np.where(x <= 0.02, np.nan, re)
    poll=np.where(emis <= threshold, np.nan, re)
    re_poll=np.nanmean(poll)
    re_pollvar=np.nanvar(poll)
    pollpoints=np.logical_not(np.isnan(poll)).sum()
    
    return re_prist,re_poll, pollpoints, pristpoints, re_pollvar

def re_diff_emis2(threshold, re, emis):
    
    #print("division middle")
    prist=np.where(emis > threshold, np.nan, re)
    poll=np.where(emis <= threshold, np.nan, re)
    
    re_prist=[]
    pristpoints=[]
    re_poll=[]
    re_pollvar=[]
    pollpoints=[]
    
    for d in range(np.shape(prist)[2]):
        re_prist.append(np.nanmean(prist[:,:,d]))
        pristpoints.append(np.logical_not(np.isnan(prist[:,:,d])).sum())
        
        re_poll.append(np.nanmean(poll[:,:,d]))
        re_pollvar.append(np.nanvar(poll[:,:,d]))
        pollpoints.append(np.logical_not(np.isnan(poll[:,:,d])).sum())
    
    return re_prist,re_poll, pollpoints, pristpoints, re_pollvar


# returns a list values of mean droplet sizes in different emission bins 
def re_emis_bins(re, emis, up_to=1, bins=20):
    binsize=up_to/bins
    re_mean=[]
    for i in range(bins):
        ra=np.where(emis < i*binsize, np.nan, re)
        #print(ra)
        ra=np.where(emis >= (i+1)*binsize, np.nan, ra)
        ra_mean=np.nanmean(ra)
        ra_points=np.nansum(ra)/ra_mean
        re_mean.append([i*binsize ,ra_mean, ra_points])
    return np.transpose(re_mean)