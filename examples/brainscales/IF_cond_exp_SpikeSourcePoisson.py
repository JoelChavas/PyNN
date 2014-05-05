"""
A single IF neuron with exponential, conductance-based synapses, fed by two
spike sources.

Run as:

$ python IF_cond_exp.py <simulator>

where <simulator> is 'neuron', 'nest', etc

Andrew Davison, UNIC, CNRS
May 2006

$Id: IF_cond_exp.py 917 2011-01-31 15:23:34Z apdavison $
"""

from pyNN.utility import normalized_filename
from pyNN.errors import RecordingError

from pyNN.hardware.brainscales import *
simulator_name = "HardwareBrainscales"

#setup(timestep=0.1,min_delay=0.1,max_delay=4.0)
setup(loglevel=2, useSystemSim=True, hardware=hardwareSetup['small'],timestep=0.1,min_delay=0.1,max_delay=4.0)
# ## enable the interactive Mapping mode
# g._interactiveMappingMode = True
# ## enable the interactive Mapping mode's GUI
# g._interactiveMappingModeGUI = True
# 
# ifcell = IF_cond_exp(cm=0.2, tau_refrac=3.0, v_thresh = -51.0, tau_syn_E=5.0, tau_syn_I=5.0, v_reset=-70.0, e_rev_E = 0., e_rev_I=-100., v_rest=-50.)
# popcell       = Population(1,ifcell)
# spike_sourceE = Population(1, SpikeSourceArray, {'spike_times': [float(i) for i in range(5,105,10)]})
# spike_sourceI = Population(1, SpikeSourceArray, {'spike_times': [float(i) for i in range(155,255,10)]})
# 
# connE = connect(spike_sourceE, popcell, weight=0.04, receptor_type='excitatory', delay=2.0)
# connI = connect(spike_sourceI, popcell, weight=0.02, receptor_type='inhibitory', delay=4.0)
#     
# filename = normalized_filename("Results", "IF_cond_exp", "pkl", simulator_name)
# record(['v', 'gsyn_exc', 'gsyn_inh'], popcell, filename,
#        annotations={'script_name': __file__})
# 
# run(200.0)

ifcell  = IF_cond_exp(cm=0.2, i_offset=0.0, tau_refrac=3.0, v_thresh=-51.0, tau_syn_E=5.0, tau_syn_I=5.0, v_reset=-70.0, e_rev_E=0., e_rev_I=-100., v_rest=-50., tau_m=20.)
popcell2 = Population(2,ifcell,label="popcell2")
#popcell2 = Population(1,ifcell,initial_values={'v':-99})
#popcell1 = Population(1, ifcell)
spike_sourceE = Population(1, SpikeSourcePoisson(rate=100, duration=100), label="poissonE")
spike_sourceI = Population(1, SpikeSourcePoisson(rate=100, start=120, duration=200), label="poissonI")
#popcell2.initialize(v=-99)
#popcell1.initialize(v=0)
#conn = connect(popcell1, popcell2, weight=0.04, receptor_type='excitatory', delay=2.0)
#conn = connect(popcell2, popcell1, weight=0.04, receptor_type='excitatory', delay=2.0)
ext_syn = StaticSynapse(weight=0.006)
rconn = 1.
ext_conn = FixedProbabilityConnector(rconn)
ext_inh_syn = StaticSynapse(weight=0.02)
ext_inh_conn = FixedProbabilityConnector(rconn)
connE = Projection(spike_sourceE, popcell2, connector=ext_conn, synapse_type=ext_syn, receptor_type='excitatory')
#connE = connect(spike_sourceE, popcell2, weight=0.006, receptor_type='excitatory', delay=2.0)
#connI = connect(spike_sourceI, popcell2, weight=0.02, receptor_type='inhibitory', delay=4.0)
connI = Projection(spike_sourceI, popcell2, connector=ext_inh_conn, synapse_type=ext_inh_syn, receptor_type='inhibitory')
filename = normalized_filename("Results", "IF_cond_exp", "pkl", simulator_name)
record(['v', 'spikes'], popcell2, filename,
       annotations={'script_name': __file__})
run(260.0)

end()


import sys
import os
import matplotlib.pyplot as plt
import numpy
import warnings
import glob
from pyNN.recording import get_io

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
        blocks[root][simulator] = get_io(datafile).read_block()
else:
    print "No data found for pattern %s" % pattern

print "-"*79
from pprint import pprint
pprint(blocks)

if len(blocks) > 0:
    for name in blocks:
        plt.figure()
        lw = 2*len(blocks[name]) - 1
        for simulator, block in blocks[name].items():
            vm = block.segments[0].filter(name="v")[0]
            plt.plot(vm.times, vm[:, 0], label=simulator_name, linewidth=lw)
            print vm
            lw -= 2
        plt.legend()
        plt.title(name)
        plt.xlabel("Time (ms)")
        plt.ylabel("Vm (mV)")
        plt.show()
        plt.savefig("Results/%s.png" % name)



