{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 31,
   "metadata": {},
   "outputs": [],
   "source": [
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "import os\n",
    "import glob\n",
    "import copy\n",
    "import sys\n",
    "import datetime\n",
    "import iris\n",
    "from pyhdf.SD import SD, SDC\n",
    "import time\n",
    "from cis.data_io.gridded_data import GriddedDataList\n",
    "\n",
    "os.environ['CIS_PLUGIN_HOME'] = '/home/users/pete_nut/plugins/'\n",
    "from cis import read_data, read_data_list, get_variables\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 32,
   "metadata": {},
   "outputs": [],
   "source": [
    "#function that checks a list of files for overlap \n",
    "#with the coordinate interval lat=[-35,0], lon=[-90,-70]\n",
    "#and deletes the filenames without overlap\n",
    "\n",
    "def delete_no_overlap(filelist):\n",
    "    delfiles=[]\n",
    "    for filename in filelist:\n",
    "        #print(filename)\n",
    "        dataset = SD(filename, SDC.READ)\n",
    "        lats = dataset.select('Latitude').get()\n",
    "        lons = dataset.select('Longitude').get()\n",
    "        #print(lats.min(), lats.max(), lons.min(), lons.max())\n",
    "        if (lats.max() < -35.  or lats.min() > 0 or lons.max() < -90 or lons.min() > -70 or lons.max()>170 ):\n",
    "            #print(filename)\n",
    "            delfiles.append(filename)\n",
    "        #else: print(filename)\n",
    "    \n",
    "    for filename in delfiles:\n",
    "        filelist.remove(filename)\n",
    "    return filelist\n",
    "\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "gridding for day 01/01/2018\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/01/01/MYD06_L2.A2018001.1745.061.2018003211213.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/01/01/MYD06_L2.A2018001.1750.061.2018003211441.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/01/01/MYD06_L2.A2018001.1755.061.2018003211422.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/01/01/MYD06_L2.A2018001.1925.061.2018003211429.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/01/01/MYD06_L2.A2018001.1930.061.2018003211235.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/01/01/MYD06_L2.A2018001.1935.061.2018003211424.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/01/01/MYD06_L2.A2018001.2100.061.2018003212248.hdf\n"
     ]
    }
   ],
   "source": [
    "months=['00','01','02','03','04','05','06','07','08','09','10','11','12']\n",
    "modis_year = '2018'\n",
    "modis_dir = '/neodc/modis/data/MYD06_L2/collection61/{}/{}/{}/'\n",
    "modis_month = months[1]\n",
    "\n",
    "days=['01','02','03','04','05','06','07','08','09',\n",
    "      '10','11','12','13','14','15','16','17','18','19',\n",
    "      '20','21','22','23','24','25','26','27','28','29', '30','31']\n",
    "\n",
    "#modis_day = days[0]\n",
    "for day in days:\n",
    "    print('gridding for day {}/{}/{}'.format(modis_day, modis_month, modis_year))\n",
    "    #ROI is UTC-5 so there is no daylight before ~1200 UTC --> Overpass time for Terra is around 1800 UTC\n",
    "    #make a list of MODIS files on the day, check for overlap and delete those without \n",
    "    modis_daily = sorted(glob.glob(modis_dir.format(modis_year, modis_month, modis_day) + '*.hdf'))\n",
    "    end_day = glob.glob(modis_dir.format(modis_year, modis_month, modis_day) + '*.2355.*.hdf')[0]\n",
    "    end_day = modis_daily.index(end_day)\n",
    "    start_time=glob.glob(modis_dir.format(modis_year, modis_month, modis_day) + '*.1500.*.hdf')[0]\n",
    "    start_time=modis_daily.index(start_time)\n",
    "    modis_daily = modis_daily[start_time:end_day]\n",
    "    modis_daily=delete_no_overlap(modis_daily)\n",
    "\n",
    "    \n",
    "    #get data, need to do seperately because of different resolution\n",
    "    mod_hr=read_data_list(modis_daily,\n",
    "                       ['Cloud_Fraction',\n",
    "                        'Cloud_Top_Temperature'])\n",
    "    mod_lr=read_data_list(modis_daily,\n",
    "                          ['Cloud_Effective_Radius','Cloud_Water_Path'], product='MOD06_HACK')\n",
    "    \n",
    "    \n",
    "    #grid ungridded data to 0.1 deg grid, time dimension is collapsed (taking a mean?)\n",
    "    agg_mod_lr=mod_lr.aggregate(x=[-90.0,-70.,0.1], y=[-35.0,0.0,0.1])\n",
    "    agg_mod_hr=mod_hr.aggregate(x=[-90.0,-70.,0.1], y=[-35.0,0.0,0.1])\n",
    "    \n",
    "    \n",
    "    #add the two datasets together and save\n",
    "    all_data=GriddedDataList([agg_mod_hr[0],agg_mod_hr[3], agg_mod_lr[0], agg_mod_lr[3]])\n",
    "    all_data.save_data('/gws/nopw/j04/eo_shared_data_vol2/scratch/pete_nut/regrid_modis/'+modis_year+ modis_month + modis_day+\".nc\")\n",
    "   \n",
    "    "
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 28,
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "/neodc/modis/data/MYD06_L2/collection61/2018/02/01/MYD06_L2.A2018032.1840.061.2018033162742.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/02/01/MYD06_L2.A2018032.1845.061.2018033163753.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/02/01/MYD06_L2.A2018032.1850.061.2018033163352.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/02/01/MYD06_L2.A2018032.2020.061.2018033162809.hdf\n",
      "/neodc/modis/data/MYD06_L2/collection61/2018/02/01/MYD06_L2.A2018032.2025.061.2018033163225.hdf\n"
     ]
    }
   ],
   "source": []
  },
  {
   "cell_type": "code",
   "execution_count": 30,
   "metadata": {},
   "outputs": [
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Attempted to set invalid unit 'none'.\n",
      "WARNING:root:Units are not cf compliant, not setting them. Units none\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Attempted to set invalid unit 'none'.\n",
      "WARNING:root:Units are not cf compliant, not setting them. Units none\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Attempted to set invalid unit 'none'.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n",
      "WARNING:root:Standard name 'None' not CF-compliant, this standard name will not be used in the output file.\n"
     ]
    },
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Time passed: 273.6826615333557\n"
     ]
    }
   ],
   "source": []
  },
  {
   "cell_type": "code",
   "execution_count": 25,
   "metadata": {},
   "outputs": [],
   "source": [
    "#agg_mod_lr[3].plot()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 27,
   "metadata": {},
   "outputs": [
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "/home/users/pete_nut/miniconda3/lib/python3.8/site-packages/iris/fileformats/netcdf.py:2122: UserWarning: 'history' is being added as CF data variable attribute, but 'history' should only be a CF global attribute.\n",
      "  warnings.warn(msg)\n"
     ]
    }
   ],
   "source": []
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.8.3"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
