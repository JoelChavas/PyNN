"""
hardware.brainscales implementation of the PyNN API.

This simulator implements the PyNN API, for hardware and hardware simulators.

:copyright: Copyright 2006-2013 by the PyNN team, see AUTHORS.
:license: CeCILL, see LICENSE for details.
"""
#================================================================
# imports
#================================================================

import logging
import tempfile

# common PyNN modules
from pyNN import common
from pyNN.connectors import *
from pyNN.recording import *
from pyNN.random import NumpyRNG

# hardware specific python modules
from . import simulator

# hardware specific PyNN modules
from .standardmodels import *
from .populations import Population, PopulationView, Assembly
from .projections import Projection

# utility modules
from documentation import _default_args

# heidelberg specific mapping modules

import mappingutilities
import mappingdatamodels
import mapping
# TODO: mapper package needs to be restructured, e.g. two modules (manual_placer and mapping_analyzer)
# load mapper package, that contains a manual placer and a mapping analyzer
#            -> see "TA12 Mapping User Interface Draft"?
import mapper
# Note: lib debugconfigufation does not exist, if configure --without-hardware
try:
    import debugconfiguration
except:
    pass

#========================
#  VARIABLES MAPPING
#========================

STPParams=mappingdatamodels.STPParams
SynParams=mappingdatamodels.SynParams
enum_synapse_type=mappingdatamodels.synapse_type

toLog = mapping.toLog
ERROR   = mapping.ERROR
WARNING = mapping.WARNING
INFO    = mapping.INFO
DEBUG0  = mapping.DEBUG0
DEBUG1  = mapping.DEBUG1
DEBUG2  = mapping.DEBUG2
DEBUG3  = mapping.DEBUG3

#========================
#  VARIABLES DEFINITION
#========================

# loglevel and name of the logfile for the global logger 
_logfile = 'logfile.txt'
_loglevel = 2 # INFO
## the list of hardwares
_hardware_list = None
## this module's random number generator
_globalRNG = NumpyRNG().rng
## flag to check if the setup() method has been called already
_calledSetup = False
## use executable system simulation instead of real hardware
_useSystemSim = False
## flag to check, whether the SystemC simulation has already been intialized, which can happen only once.
_initializedSystemC = False
## flag to check, whether the SystemC simulation has already been run, which can happen only once.
_runSystemC = False
## the mapping preprocessor
_preprocessor = None
## the mapping algorithm controller
_mapper = None
## the mapping postprocessor
_postprocessor = None
## the mapping statistics
_statistics = None
## the hardware configuration controller
_configurator = None
## the number of neurons created so far
_numberOfNeurons = 0
## the number of neuron parameter sets created so far
_numberOfNeuronParameterSets = 0
## the number of current source parameter sets created so far
_numberOfCurrentSourceParameterSets = 0
## the number of current sources created so far
_numberOfCurrentSources = 0
## the number of synapse parameter sets created so far
_numberOfSynapseParameterSets = 0
## flag for signalling a neuron parameter change, helps to reduce PC <-> chip traffic
_neuronsChanged = True
## flag for signalling a synapse parameter change, helps to reduce PC <-> chip traffic
_synapsesChanged = True
## flag for signalling a connectivity parameter change, helps to reduce PC <-> chip traffic
_connectivityChanged = True
## flag for signalling an input parameter change, helps to reduce PC <-> chip traffic
_inputChanged = True
## flag to check whether _run_mapping() has been called already
_calledRunMapping = False
## counts the number of experiment runs
_iteration = 0
## container for external input objects (not IDs)
_externalInputs = []
## speedup factor of the (virtual) hardware system
_speedupFactor = 10000.
## if True: use the small hardware capacitance (500fF instead of 2pF)
_useSmallCap = False
## container for the random number generation seeds
_rng_seeds = [0]
## temporal resolution of the acquisition of the analog data (currently via oscilloscope), in msec
_dt = simulator.state.dt
## simulation duration of the current run
_simtime = 0.
## enable the interactive Mapping mode
_interactiveMappingMode = False
## enable the interactive Mapping mode's GUI
_interactiveMappingModeGUI = False
## a meaningful name for the experiment
_experimentName = 'no name'
## the chosen mapping strategy
_mappingStrategy = 'normal'
## the list of mapping quality weights
_mapping_quality_weights = None
## time step of virtual hardware SystemC simulation
_systemSimTimeStepInPS = 10
## file for mapping statistics
_mappingStatisticsFile = None
## the mapping statistics class c accessor (GMStats)
_statistics = None
## file for writing the full connection matrix of the entire network
_fullConnectionMatrixFile = None
## file for writing a matrix with all connections that were realized during mapping.
_realizedConnectionMatrixFile = None
## file for writing a matrix with all connections that were lost during mapping.
_lostConnectionMatrixFile = None
## folder containing all temporary files (PyNN and / or system simulation)
_tempFolder = None
## this flag is true, when elements in the temporary folder shall not be deleted after simulation
_deltempFolder = True
## holds the time stamp of the setup start
_setupstart = 0
                          
logger = logging.getLogger("PyNN")

# ==============================================================================
#   Utility functions
# ==============================================================================


def _set_speedup_factor(speedup):
    """!
    sets speedup factor and scales the allowed parameter ranges for all models to the current speedup.
    @param speedup - new speedup factor
    """
    global _speedupFactor
    _speedupFactor = speedup
    # scaling parameter ranges
    for model in [EIF_cond_exp_isfa_ista,IF_cond_exp,SpikeSourcePoisson,TsodyksMarkramMechanism]:
        model.scaleParameterRangesTime(_speedupFactor)
    # also update the allowed periods of PeriodicCurrentSource
    PeriodicCurrentSource.ALLOWED_PERIODS = FG_ALLOWED_PERIODS(_speedupFactor)

# make sure all models are on the same time base
_set_speedup_factor(_speedupFactor)


# ==============================================================================
#   Functions for simulation set-up and control
# ==============================================================================

def setup(timestep=0.1, min_delay=0.1, max_delay=10.0, **extra_params):
    """!
    Set up all necessary data structures.

    Should be called at the very beginning of a script.

        @param timestep     - unlike for the software simulators that support PyNN, this hardware back-end
                              does not interpret the timestep argument as the numerical integration step size,
                              but as the sampling time step for analog signal recordings (e.g. membrane potentials
                              via oscilloscopes).
        @param min_delay    - not used.
        @param max_delay    - not used.
        @param extra_params - any keyword arguments that are required by this PyNN back-end but not necessarily by others.\n\n
                              Currently supported:\n\n
{kwargs}
    """
    # REMARK: the doc for the kwargs is appended to existing docstring direclty after the function definition 
    
    common.setup(timestep, min_delay, max_delay, **extra_params)
    simulator.state.clear()
    simulator.state.dt = timestep  # move to common.setup?
    simulator.state.min_delay = min_delay
    simulator.state.max_delay = max_delay
    return 0

# re format docstring of setup function

setup.__doc__ = setup.__doc__.format(kwargs=_default_args.pprint(indent=8))

def list_standard_models():
    """Return a list of all the StandardCellType classes available for this simulator."""
    return [obj.__name__ for obj in globals().values() if isinstance(obj, type) and issubclass(obj, StandardCellType)]


def end(compatible_output=True):
    """Do any necessary cleaning up before exiting."""
    for (population, variables, filename) in simulator.state.write_on_end:
        io = get_io(filename)
        population.write_data(io, variables)
    simulator.state.write_on_end = []
    # should have common implementation of end()

run, run_until = common.build_run(simulator)
run_for = run

reset = common.build_reset(simulator)

initialize = common.initialize

get_current_time, get_time_step, get_min_delay, get_max_delay, \
                    num_processes, rank = common.build_state_queries(simulator)

#            )

create = common.build_create(Population)

connect = common.build_connect(Projection, FixedProbabilityConnector, StaticSynapse)

#set = common.set

record = common.build_record(simulator)

record_v = lambda source, filename: record(['v'], source, filename)

record_gsyn = lambda source, filename: record(['gsyn_exc', 'gsyn_inh'], source, filename)
