#!/usr/bin/python
import sys
import os
import matplotlib.pyplot as plt
import numpy
import warnings
import glob
from pyNN.recording import get_io
from pyNN.utility import get_script_args

filename = get_script_args(1)[0] 
simulator_name = get_script_args(2)[0]

plt.ion() #.rcParams['interactive'] = True

blocks = {}
pattern = filename
datafiles = glob.glob(pattern)
print "datafiles =", datafiles
if datafiles:
    for datafile in datafiles:
        base = os.path.basename(datafile)
        root = base[:base.find(simulator_name)-1]
        if root not in blocks:
            blocks[root] = {}
        blocks[root][simulator_name] = get_io(datafile).read_block()
else:
    print "No data found for pattern %s" % pattern

print "-"*79
from pprint import pprint
pprint(blocks)

def raster(event_times_list, color='k'):
    """
    Creates a raster plot
    
    http://scimusing.wordpress.com/2013/05/06/making-raster-plots-in-python-with-matplotlib/
    
    Parameters
    ----------
    event_times_list : iterable
    a list of event time iterables
    color : string
    color of vlines
    
    Returns
    -------
    ax : an axis containing the raster plot
    """
    ax = plt.gca()
    for ith, trial in enumerate(event_times_list):
	plt.vlines(trial, ith + .5, ith + 1.5, color=color)
    plt.ylim(.5, len(event_times_list) + .5)
    return ax

if len(blocks) > 0:
    for name in blocks:
        plt.figure()
        for simulator, block in blocks[name].items():
	    i = 0
	    for sp in block.segments[0].spiketrains:
                print sp
		plt.vlines(sp, i, i+1.)
		i = i +1
        plt.legend()
        plt.title(name)
        plt.xlabel("Time (ms)")
        plt.ylabel("neurons")
        plt.savefig("Results/%s.png" % name)
        print "\n--- Visualize using the following command ---"
        print "eog Results/%s.png" % name