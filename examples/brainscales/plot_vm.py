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

if len(blocks) > 0:
    for name in blocks:
        plt.figure()
        for simulator, block in blocks[name].items():
	    vm = block.segments[0].filter(name="v")[0]
	    plt.plot(vm.times, vm[:, 0], label=simulator_name)
	    print vm
        plt.legend()
        plt.ylim(-65,-45)
        plt.title(name)
        plt.xlabel("Time (ms)")
        plt.ylabel("Votage (mV)")
        plt.savefig("Results/%s.png" % name)
        print "\n--- Visualize using the following command ---"
        print "eog Results/%s.png" % name