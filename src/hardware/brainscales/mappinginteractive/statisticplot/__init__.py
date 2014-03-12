# encoding: utf-8
#
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: Statistics for the mapping process
#
# ***************************************************************************
#
## @namespace hardware::brainscales::statisticsplot
##
## @short Statistics for the mapping process.
##
## @detailed Several plot functions to produce brainscales mapping statistics 
##           specific plots.
##            - plot the neuron based fan-in histogram
##            - plot the hicanns per hw-neuron configuration group
##            - plot the fan-in, fan-out, scatter plot

import pyNN.hardware.brainscales

import numpy as np
import matplotlib.pyplot as plt
import os
import subprocess

"""

 class providing HICANN specific plots from fan-in and fan-out info

"""
class Statisticplotter() :
    
    def __init__(self,folder = 'temp/') :
        
        self.folder = folder
        if not os.path.exists(self.folder) :
            os.makedirs(self.folder)
            
        self.fanin = None
        self.fanout = None
        self.apriorisynapseloss = None
        self.devnull = open(os.devnull, 'wb')
 
    # remove statistics on object destruction
    # def __del__(self) :
        # subprocess.call('rm -rf '+str(self.folder), shell=True, stdout=self.devnull, stderr=subprocess.STDOUT)

    def plottest(self) :
        """
        create random data for debug
        """
        import random as rand
        
        NeuronCount = 30000
        StimuliCount = 100
        MaxFanOut = 3000
        MaxFanIn = 14336
       
        """
        rand.seed(142323)
        ffanin = open('output/fan_in.dat','w')
        ffanout = open('output/fan_out.dat','w')
        ffanin.write('// fan_in.dat with fan-in of each neuron per line \n')
        ffanout.write('// fan_out.dat with fan-out of each neuron per line \n')
        for i in range(NeuronCount) :
            ffanin.write(str(rand.randint(1,int(NeuronCount/2)))+'\n')
            #ffanout.write(str(rand.randint(int(NeuronCount/10),int(NeuronCount/5)))+'\n')
            #ffanin.write(str(int(rand.gauss(NeuronCount/8,NeuronCount/50)))+'\n')
            ffanout.write(str(int(rand.gauss(NeuronCount/20,NeuronCount/40)))+'\n')
        ffanin.close()
        ffanout.close()
        """
       
        """
        data input
        """
        
        #read fan-in data
        fanin = []
        fp = file(str(self.folder)+'fan_in.dat','rb')
        for line in fp :
            # split values if necessary
            array = line.split()
            # skip comments
            if array[0] != '//' :
                fanin.append(int(array[0]))
        self.set_fan_in(fanin)
                
        #read fan-out data
        fanout = []
        fp = file(str(self.folder)+'fan_out.dat','rb')
        for line in fp :
            # split values if necessary
            array = line.split()
            # skip comments
            if array[0] != '//' :
                fanout.append(int(array[0]))
        self.set_fan_out(fanout)

    def set_fan_in(self,fanin):
        '''

        '''
        self.fanin = fanin
        # bins depending on configuration
        # when grouping membrane circuits 
        # the number of synapses per hw neuron increases but
        # the number of hw neurons per FPNA decreases
        self.bins = [0,224*2**0,224*2**1,224*2**2,224*2**3,224*2**4,224*2**5,224*2**6]
        
        # calculate the histogram for the elements to the maximum
        self.faninhist, self.bin_edges = np.histogram(fanin,bins=self.bins)
        
        # add the elements above fan-in maximum to the last bin with the maximum fan-in
        # and accumulate the synapses that will be lost due to cut off
        self.faninhist = np.append(self.faninhist,np.array([0])) # the original one w/o losses
        self.faninhistfull = self.faninhist.copy() # with losses 
        self.faninhistloss = self.faninhist.copy() # with losses to maximum fan-in 
        self.apriorisynapseloss = 0
        self.lastbin = np.size(self.faninhistloss)-2
        for element in fanin :
            if element > (224*2**6) :
                self.faninhistfull[self.lastbin+1] += 1 # count in the bin where a loss appears
                self.apriorisynapseloss += element-224*2**6 # calculate and accumulate synapse loss
                self.faninhistloss[self.lastbin] += 1 # count in the the bin with the maximum-fan in
    
        self.NeuronCount = np.size(self.fanin)
        
        #normalize histograms
        self.normfaninhist = []
        self.normfaninhistfull = []
        self.normfaninhistloss = []
        for bindings in range(0,np.size(self.faninhist)) :
            self.normfaninhist.append(float(self.faninhist[bindings])/self.NeuronCount)
            self.normfaninhistfull.append(float(self.faninhistfull[bindings])/self.NeuronCount) 
            self.normfaninhistloss.append(float(self.faninhistloss[bindings])/self.NeuronCount)
            
    def set_fan_out(self,fanout):
        '''

        '''
        self.fanout = fanout
        
    def hicann_fan_in_histogramm(self,outputfile='fanin_groups.png') :
        """!
        
        fan-in histogram in synapse per hw-neuron bins
        """
        if self.fanin == None :
            raise Exception("Statisticplotter::ERROR attempting to plot figure w/o data")
        
        # print "A-priori synapse loss due to cut-off: ", apriorisynapseloss
        
        # print the histogram
        fig = plt.figure()
        p = fig.add_subplot(1,1,1)
        p.set_xlabel('$Fan-In$', fontsize=20)
        p.set_ylabel('#$Neurons$', fontsize=20)
        p.get_xaxis().set_ticks([])
        ticks = np.arange(0,np.size(self.bins),1)
        p.set_xlim(0,1.0*np.size(ticks))
        width = 1.0 # barwidth
        p.bar(ticks, self.normfaninhistfull, width, color='#ff0000')
        p.bar(ticks, self.normfaninhistloss, width, color='#bdbdbd')
        p.bar(ticks, self.normfaninhist, width, color='#cccccc')
        plt.xticks(ticks, ('1','224','448','896','1792','3584','7168','14336','loss'))
        plt.savefig(str(self.folder)+str(outputfile), format='png', orientation='portrait',dpi=300)
        plt.close(fig)
    
    def get_aprioriloss(self):
        return self.apriorisynapseloss
    
    def hicann_config_groups(self,outputfile='hicann_groups.png') :
        """!
        
        plot the number of HICANNs with a specific 
        HW-neuron configuration required
        
        """
        if self.fanin == None :
            raise Exception("Statisticplotter::ERROR attempting to plot figure w/o data")
        
        #calculate the required HICANNs for each group
        hicanns = []
        configindex = 9
        for bindings in range(0,np.size(self.faninhistloss)-1) :
            if self.faninhistloss[bindings] != 0 :
                hicanns.append(self.faninhistloss[bindings]/(2**configindex))
                if self.faninhistloss[bindings] % (2**configindex) != 0 :
                    hicanns[-1]+=1
            else :
                hicanns.append(0)
            configindex-=1
    
        fig = plt.figure()
        p = fig.add_subplot(1,1,1)
        p.get_xaxis().set_ticks([])
        p.set_xlabel('#$Neurons/HICANN$', fontsize=20)
        p.set_ylabel('#$HICANN$', fontsize=20)
        ticks = np.arange(0,np.size(hicanns),1)
        width = 1.0 # spacing
        p.vlines(ticks,[0],hicanns)
        p.plot(ticks,hicanns,'wo')
        for index in range(0,np.size(hicanns)) :
            plt.text(ticks[index], hicanns[index]+1, str(hicanns[index]))
        p.set_xlim(0-width,7*width)
        p.set_ylim(0,np.max(hicanns)+5)
        plt.xticks(ticks, ('512','256','128','64','32','16','8'))
        plt.grid(True)
        plt.savefig(str(self.folder)+str(outputfile), format='png', orientation='portrait',dpi=300)
        plt.close(fig)
        
    def fanin_fanout_scatter_plot(self,outputfile='fan_in_out_scatter.png') :
        """!
        
        fan-in/fan-out scatter plot 
        
        """
        
        if self.fanin == None or self.fanout == None:
            raise Exception("Statisticplotter::ERROR attempting to plot figure w/o data")

        from mpl_toolkits.axes_grid1 import make_axes_locatable
        fig = plt.figure()
        
        # create a fan-in and fan-out scatterplot 
        # and set the axeslimit to 
        # the largest fan-in or fan-out value
        scatterp = fig.add_subplot(1,1,1)
        scatterp.scatter(self.fanin,self.fanout,c='#cccccc')
        MaxFanIn = np.max(self.fanin)
        MaxFanOut = np.max(self.fanout)
        axislimit = np.max([MaxFanIn,MaxFanOut])
        scatterp.set_xlim(0,axislimit)
        scatterp.set_ylim(0,axislimit)
        
        plt.axhspan(ymin=MaxFanOut,ymax=axislimit,facecolor='#cccccc',edgecolor='#000000',alpha=0.4)
        plt.axvspan(xmin=MaxFanIn,xmax=axislimit,facecolor='#cccccc',edgecolor='#000000',alpha=0.4)
        scatterp.set_xlabel('$Fan-In$', fontsize=20)
        scatterp.set_ylabel('$Fan-Out$', fontsize=20)
        #scatterp.set_aspect(1.) # ensures aspect ration 1:1 for the axis
        # create new axes on the right and on the top of the current axes
        # The first argument of the new_vertical(new_horizontal) method is
        # the height (width) of the axes to be created in inches.
        divider = make_axes_locatable(scatterp)
        axFanInHist = divider.append_axes("top", 1.5, pad=0.2, sharex=scatterp)
        axFanInHist.set_xlim(0,axislimit)
        axFanInHist.set_ylim(0,1.0)
        axFanOutHist = divider.append_axes("right", 1.5, pad=0.2, sharey=scatterp)
        axFanOutHist.set_xlim(0,1.0)
        axFanOutHist.set_ylim(0,axislimit)
        
        # hide shared axes for the histograms
        plt.setp(axFanInHist.get_xticklabels() + axFanOutHist.get_yticklabels(),visible=False)
        
        # have 100 bins in the range of the scatter plot
        
        
        if (axislimit > 100) :
            binwidth = axislimit/100
        else : 
            binwidth = 1
            axislimit = 100
        
        self.scatterbins = np.arange(0,axislimit,binwidth)
        # calculate the histograms for fan-in/fan-out
        #axFanInHist.hist(fanin, bins=scatterbins, color='#cccccc')
        #axFanOutHist.hist(fanout, bins=scatterbins, color='#cccccc', orientation='horizontal')
        self.scatfaninhist, bin_edges = np.histogram(self.fanin,bins=self.scatterbins)
        self.scatfanouthist, bin_edges = np.histogram(self.fanout,bins=self.scatterbins)
        #normalize
        self.normscatfaninhist = []
        self.normscatfanouthist = []
        for bindings in range(0,np.size(self.scatfaninhist)) :
            self.normscatfaninhist.append(float(self.scatfaninhist[bindings])/self.NeuronCount)
            self.normscatfanouthist.append(float(self.scatfanouthist[bindings])/self.NeuronCount)
        ticks = np.arange(0,axislimit-axislimit/100,axislimit/100)
        
        axFanInHist.bar(ticks, self.normscatfaninhist,width=binwidth, color='#cccccc', linewidth=0.3)
        axFanOutHist.barh(ticks, self.normscatfanouthist, height=binwidth, color='#cccccc', linewidth=0.3)
        
        plt.savefig(str(self.folder)+str(outputfile), format='png', orientation='portrait',dpi=300)
        plt.close(fig)