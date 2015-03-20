from atmPy.atmosphere import Air
import tkinter as tk
from tkinter import filedialog as fd
from atmPy import aerosol
import pandas as pd
from datetime import datetime as dt
from datetime import timedelta
from math import floor

import matplotlib.pyplot as plt

import sys


import numpy as np
from scipy.interpolate import interp1d
import statsmodels.api as sm


class SMPS(object):
    """
    Defines routines associated with an SMPS object

    Attributes
    ----------
    dma:    DMA object
            Defines the differential mobility analyzer specific to the SMPS
    scan_folder:    String
                    Location of scan data
    """
    def __init__(self, dma, scan_folder=''):

        self.air = Air()
        self.dma = dma

        self.diam_interp = 0

        self.gui = tk.Tk()

        # Prompt the user for a file or files to process
        self.files = fd.askopenfiles(initialdi=scan_folder)

        self.gui.destroy()

        self.buildGrid()

        self.dn_interp = np.zeros((2*len(self.files), len(self.diam_interp)))
        self.date = [None]*2*len(self.files)
        self.lag = 0

    def __chargecorr__(self, diam, dn, gas, n=3, pos_neg=-1):
        """
        Correct the input concentrations for multiple charges.

        This function does not return anything as it handles array input by reference.

        Parameters
        ----------
        diam:       array of float
                    array of diameters in nm
        dn:         array of integers
                    Array of particle concentrations corresponding to diameter 'diam'
        gas:        gas object
                    Gas object that defines the properties of the gas
        n:          int, optional
                    Number of charges to consider.  Default is 3.
        pos_neg:    int, optional
                    Positive or negative one indicating whether to consider positive or negative charges.
                    Default is -1.

        Returns
        -------
        None

        """

        #  dn_removed = np.zeros(len(dn))

        single_frac = np.zeros(len(dn))

        # Flip both the incoming diamter array and the concentration distribution
        rdiam = diam[::-1]

        dn_raw = dn
        dn_work = dn
        dn_raw = dn

        # We are working backwards, so we need to have the length to get this all right...
        l = len(dn)-1

        # Find the value closest to diameter d in the array diam
        fmin = lambda nd: (np.abs(np.asarray(diam) - nd)).argmin()

        for i, d in enumerate(rdiam):

            # Get the fraction of particles that are singly charged
            single_frac[l-i] = aerosol.ndistr(d, pos_neg, gas.t)

            for j in reversed(range(2, n+1)):  # Loop through charges 2 and higher

                ne = j*pos_neg

                # Ratio of singly charge particles to particles with charge ne
                c_rat = single_frac[l-i]/aerosol.ndistr(d, ne, gas.t)


                z_mult = abs(ne*aerosol.z(d, gas, pos_neg))

                d_mult = aerosol.z2d(z_mult, gas, 1)

                #  Do NOT try to move particles for which we don't have a diameter


                # Find the index of the multiple charges
                k = fmin(d_mult)

                # Calculate the number of particles to move from the upper bin to the lower
                n2move = min(dn_raw[l-i]/c_rat, dn_work[k])

                if d_mult >= diam[0]:
                    dn[k] += n2move
                    dn_work[k] -= n2move

                dn[l-i] -= n2move

        # Correct for single charging
        dn /= single_frac

        return single_frac

    def procFiles(self):
        """
        Process the files that are contained by the SMPS class attribute 'files'
        :return:
        """

        # TODO: Some of the processes here can be parallelized using the multiprocessing library
        #       Reading of the data and determing the lag will require a proper sequence, but
        #       we can parallelize:
        #       1) The processing of an individual file
        #       2) The processing of the up and down scans within a file
        #       WARNING:    Need to ensure that the different processes don't step on each other.
        #                   Likely we would need to make some of the instance variables local (air.t and air.p
        #                   come to mind).
        for e, i in enumerate(self.files):

            try:

                print(i.name)
                meta_data = self.__readMeta(i.name)
                up_data = self.__readData(i.name)

                tscan = meta_data['Scan_Time'].values[0]
                tdwell = meta_data['Dwell_Time'].values[0]
                
                self.date[2*e] = dt.strptime(str(meta_data.Date[0]) + ','
                                        + str(meta_data.Time[0])
                                        , '%m/%d/%y,%H:%M:%S')
                self.date[2*e + 1] = self.date[2*e] + timedelta(0,tscan + tdwell)

                # DO NOT truncate the data yet
                down_data = up_data[::-1]

                # Retrieve mean up data
                mup = up_data.mean(axis=0)
                f = self.lag

                # Shift the up data with the number of zeros padding on the end equal to the lag
                cpc_up = np.pad(up_data['CPC_1_Cnt'].values[f:tscan]/up_data['CPC_Flw'].values[f:tscan],
                                [0, f], 'constant', constant_values=(0, 0))

                up_data = up_data.iloc[:tscan]

                # Remove NaNs and infs
                cpc_up[np.where(np.isinf(cpc_up))] = 0.0
                cpc_up[np.where(np.isnan(cpc_up))] = 0.0

                # Calculate diameters from voltages
                dup = [self.dma.v2d(i, self.air, mup.Sh_Q_VLPM, mup.Sh_Q_VLPM) for i in up_data.DMA_Set_Volts.values]

                smooth_p = 0.3
                smooth_up = sm.nonparametric.lowess(cpc_up, up_data.DMA_Diam.values, frac=smooth_p, it=1, missing='none')




                # Padding the down scan is trickier - if the parameter f (should be the lag in the correlation)
                # is larger than the dwell time, we will have a negative resize parameter - this is no good.
                # Pad the front with the number of zeros that goes beyond the end (front in the reveresed array).
                # This makes sense.  I guess.
                if f > tdwell:
                    f = tdwell

                pad = abs(f-tdwell)

                # Shift the down data so that we pad the front and back appropriately
                cpc_down = np.pad(down_data['CPC_1_Cnt'].values[(tdwell-f):(tscan+tdwell-(f+pad))] /
                                  down_data['CPC_Flw'].values[(tdwell-f):(tscan+tdwell-(f+pad))],
                                  [0, pad], 'constant', constant_values=(0, 0))

                # Finished padding - truncate data now
                down_data = down_data.iloc[:tscan]

                cpc_down[np.where(np.isinf(cpc_down))] = 0.0
                cpc_down[np.where(np.isnan(cpc_down))] = 0.0
                down_data = down_data.iloc[:tscan]
                smooth_down = sm.nonparametric.lowess(cpc_down, down_data['DMA_Diam'].values,
                                                      frac=smooth_p, missing='none')



                smooth_down[np.where(np.isinf(smooth_down))] = 0.0
                smooth_down[np.where(np.isnan(smooth_down))] = 0.0
                smooth_up[np.where(np.isinf(smooth_up))] = 0.0
                smooth_up[np.where(np.isnan(smooth_up))] = 0.0




                # Get the mean of all the columns in down_data
                mdown = down_data.mean(axis=0)

                # Calculate diameters from voltages
                ddown = [self.dma.v2d(i, self.air, mup.Sh_Q_VLPM, mup.Sh_Q_VLPM) for i in down_data.DMA_Set_Volts.values]

                up_interp_dn = self.__fwhm__(dup, smooth_up[:, 1], mup)

                down_interp_dn = self.__fwhm__(ddown, smooth_down[:, 1], mdown)

                up_interp_dn[np.where(up_interp_dn < 0)] = 0
                down_interp_dn[np.where(down_interp_dn < 0)] = 0
                self.dn_interp[2*e, :] = up_interp_dn
                self.dn_interp[2*e+1, :] = down_interp_dn

            except:
                print("Issue processing file " + str(i.name))





    def __readMeta(self, file):

        """
        Parameters
        ----------
        file:   file object
                File to retrieve meta data from

        Returns
        -------
        pandas datafram containing meta data
        """
        return pd.read_csv(file, header=0, lineterminator='\n', nrows=1)

    def __readData(self, file):
        """
        Read the data from the file.

        Data starts in the third row.

        Parameters
        -----------
        file:   file object
                File containing SMPS data

        Returns
        --------
        pandas data frame
        """
        return pd.read_csv(file, parse_dates='Date_Time', index_col=0, header=2, lineterminator='\n')

    def getLag(self, index, delta=0):
        """
        This function can be called to guide the user in how to set the lag attribute.

        Parameters
        ----------
        index:  int
                Index of file in attribute files to determine the lag
        delta:  int, optional
                Fudge factor for aligning the two scans; default is 0
        """
        meta_data = self.__readMeta(self.files[index].name)
        up_data = self.__readData(self.files[index].name)

        tscan = meta_data.Scan_Time.values[0]
        tdwell = meta_data.Dwell_Time.values[0]

        # CPC concentrations will be simply the 1 s buffer divided by the
        # CPC flow
        cpc_cnt = up_data.CPC_1_Cnt.values/up_data.CPC_Flw.values

        # Truncate the upward trajectory
        up = cpc_cnt[0:tscan]
        #up_data = up_data.iloc[:tscan]

        # Get the counts for the decreasing voltage and truncate them
        down = cpc_cnt[::-1]                    # Flip the variable cpc_cnt
        down = cpc_cnt[tdwell:(tscan+tdwell)]     # Truncate the data
        down_data = up_data[::-1]
        #down_data = down_data.iloc[:tscan]

        # LAG CORRELATION #
        corr = np.correlate(up, down, mode="full")
        plt.plot(corr)
        corr = corr[corr.size/2:]
        self.lag = floor(corr.argmax(axis=0)/2+delta)

        f = self.lag


        # GET CPC DATA FOR PLOTTING #
        # Shift the up data with the number of zeros padding on the end equal to the lag
        up = np.pad(up_data['CPC_1_Cnt'].values[f:tscan]/up_data['CPC_Flw'].values[f:tscan], [0, self.lag], 'constant', constant_values=(0, 0))

        # Remove NaNs and infs
        up[np.where(np.isinf(up))] = 0.0
        up[np.where(np.isnan(up))] = 0.0

        up_data = up_data.iloc[:tscan]
        smooth_p = 0.3
        smooth_up = sm.nonparametric.lowess(up, up_data.DMA_Diam.values, frac=smooth_p, it=1, missing='none')


        # Padding the down scan is trickier - if the parameter f (should be the lag in the correlation)
        # is larger than the dwell time, we will have a negative resize parameter - this is no good.
        # Pad the front with the number of zeros that goes beyond the end (front in the reveresed array).
        # This makes sense.  I guess.

        pad = 0
        if f > tdwell:
            pad = f-tdwell
            f = tdwell



        # Shift the down data so that we pad the front and back appropriately
        down = np.pad(down_data['CPC_1_Cnt'].values[(tdwell-f):(tscan+tdwell-(f+pad))] /
                      down_data['CPC_Flw'].values[(tdwell-f):(tscan+tdwell-(f+pad))],
                      [0, pad], 'constant', constant_values=(0, 0))

        down[np.where(np.isinf(down))] = 0.0
        down[np.where(np.isnan(down))] = 0.0
        down_data = down_data.iloc[:tscan]
        smooth_down = sm.nonparametric.lowess(down, down_data.DMA_Diam.values, frac=smooth_p, missing='none')

        f2 = plt.figure(2)

        plt.plot(up, 'r.', down, 'b.', smooth_up[:, 1], 'r+', smooth_down[:, 1], 'b+')
        output = "Lag is estimated to be " + str(self.lag) + " with a delta of " + str(delta) + "."
        plt.title(output)
        plt.show()

    def buildGrid(self, type="log10", min=1, max=1000, n=300):
        """
        Define a logarithmic grid over which to interpolate output values

        Parameters
        ----------
        type:   string, optional
                this value can be log10 or natural (e); default is log10
        min:    int, optional
                minimum value in the grid; default is 1
        max:    int, optional
                maximum value in the grid; default is 1000
        n:      int, optional
                number of bins over which to divide the grid; default is 300
        """
        if type == "log10":
            self.diam_interp = np.logspace(np.log10(min),np.log10(max), n)
        else:
            self.diam_interp = np.logspace(np.log10(min),np.log10(max), n, base=np.exp(1))

        return None

    def __fwhm__(self, diam, dn, mean_data):
        ls = len(dn)
        dlogd = np.zeros(ls)    # calculate dlogd
        fwhm = np.zeros(ls)     # hold width
        self.air.t = mean_data.Aer_Temp_C
        self.air.p = mean_data.Aer_Pres_PSI

        for e, i in enumerate(diam):
            try:
                fwhm[e] = self.__xferFWHM(i, mean_data.Aer_Q_VLPM, mean_data.Sh_Q_VLPM)
                dlogd[e] = np.log10(i+fwhm[e]/2)-np.log10(i-fwhm[e]/2)
            except (ValueError, ZeroDivisionError):
                fwhm[e] = np.nan
                print('Handling divide by zero error')
            except:
                fwhm[e] = np.nan
                print('Handling unknown error: ' + str(sys.exc_info()[0]))

        output_sd = np.copy(dn)  # Space for the size distribution

        self.__chargecorr__(diam, output_sd, self.air)
        output_sd /= dlogd
        f = interp1d(diam, output_sd, bounds_error=False, kind='linear')
        #print(output_sd)

        return f(self.diam_interp)

    def __xferFWHM(self, dp, qa, qs):
        """
        Return the full-width, half-max of the transfer function in diameter space.
        This implementation ignores diffusion broadening.
        @param dp: particle size in nm
        @param qa: aerosol flow rate in lpm
        @param qs: aerosol flow rate in lpm
        @param T: temperature in degrees Celsius
        @param P: pressure in millibars
        @return: Width of transfer function in nm.
        """
        beta = float(qa)/float(qs)

        # Retrieve the center mobility
        Zc = aerosol.z(dp,self.air,1)

        # Upper bound of the mobility
        Zm = (1-beta/2)*Zc

        # Lower bound of the mobility
        Zp = (1+beta/2)*Zc

        return aerosol.z2d(Zm, self.air, 1)-aerosol.z2d(Zp, self.air, 1)

