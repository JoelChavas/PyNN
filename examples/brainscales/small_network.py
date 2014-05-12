# encoding: utf-8
"""
Small network created with the Population and Projection classes

Andrew Davison, UNIC, CNRS
May 2006

"""

import numpy
from pyNN.utility import get_simulator, init_logging, normalized_filename
from pyNN.parameters import Sequence
from pyNN.random import RandomDistribution as rnd

sim, options = get_simulator(("--plot-figure", "Plot the simulation results to a file."),
                             ("--debug", "Print debugging information"))

if options.debug:
    init_logging(None, debug=True)    

# === Define parameters ========================================================

n = 20      # Number of cells
w = 0.005  # synaptic weight (µS)
cell_params = {
    'tau_m'      : 20.0,   # (ms)
    'tau_syn_E'  : 2.0,    # (ms)
    'tau_syn_I'  : 4.0,    # (ms)
    'e_rev_E'    : 0.0,    # (mV)
    'e_rev_I'    : -100.0,  # (mV)
    'tau_refrac' : 2.0,    # (ms)
    'v_rest'     : -50.0,  # (mV)
    'v_reset'    : -70.0,  # (mV)
    'v_thresh'   : -45.0,  # (mV)
    'cm'         : 0.2}    # (nF)
dt         = 0.1           # (ms)
syn_delay  = 1.0           # (ms)
input_rate = 50.0          # (Hz)
simtime    = 200.0        # (ms)

# === Build the network ========================================================

extra={}
if sim.__name__ == "pyNN.hardware.brainscales":
  extra = {'loglevel':2, 'useSystemSim':True, 'hardware': sim.hardwareSetup['one-hicann'],
	'maxNeuronLoss':0., 'maxSynapseLoss':0.4,
	'hardwareNeuronSize':8}
sim.setup(timestep=dt, max_delay=syn_delay, **extra)

cells = sim.Population(n, sim.IF_cond_exp(**cell_params),
                       initial_values={'v': rnd('uniform', (-60.0, -50.0))},
                       label="cells")

number = int(2*simtime*input_rate/1000.0)
numpy.random.seed(26278342)
def generate_spike_times(i):
    gen = lambda: Sequence(numpy.add.accumulate(numpy.random.exponential(1000.0/input_rate, size=number)))
    if hasattr(i, "__len__"):
        return [gen() for j in i]
    else:
        return gen()
assert generate_spike_times(0).max() > simtime

spike_source = sim.Population(n, sim.SpikeSourceArray(spike_times=[float(i) for i in range(5,105,10)]))

#spike_source.record('spikes')
cells.record('spikes')
cells[0:2].record(('v'))

syn = sim.StaticSynapse(weight=w*4,delay=syn_delay)
input_conns = sim.Projection(spike_source, cells, sim.FixedProbabilityConnector(0.5), syn)

# === Run simulation ===========================================================

sim.run(simtime)

filename = normalized_filename("Results", "small_network", "pkl",
                               options.simulator, sim.num_processes())
cells.write_data(filename, annotations={'script_name': __file__})

print "Mean firing rate: ", cells.mean_spike_count()*1000.0/simtime, "Hz"

if options.plot_figure:
    from pyNN.utility.plotting import Figure, Panel
    data = cells.get_data().segments[0]
    vm = data.filter(name="v")[0]
    Figure(
        Panel(vm, ylabel="Membrane potential (mV)"),
        Panel(data.spiketrains, xlabel="Time (ms)", xticks=True),
    ).save(options.plot_figure)

# === Clean up and quit ========================================================

sim.end()
