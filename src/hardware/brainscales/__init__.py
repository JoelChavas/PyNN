"""
hardware.brainscales implementation of the PyNN API.

This simulator implements the PyNN API, for hardware and hardware simulators.

:copyright: Copyright 2006-2013 by the PyNN team, see AUTHORS.
:license: CeCILL, see LICENSE for details.
"""
#================================================================
# imports
#================================================================

import time
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
from .standardmodels.cells import EIF_cond_exp_isfa_ista, IF_cond_exp, SpikeSourcePoisson
from .standardmodels.synapses import TsodyksMarkramMechanism, StaticSynapse
from .populations import Population, PopulationView, Assembly
from .projections import Projection
from electrodes import PeriodicCurrentSource, FG_ALLOWED_PERIODS


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

# =============================================================================
#   Utility functions and classes
# =============================================================================

get_current_time, get_time_step, get_min_delay, get_max_delay, \
                    num_processes, rank = common.build_state_queries(simulator)
                    
# =============================================================================
#  Low-level API for creating, connecting and recording from individual neurons
# =============================================================================
initialize = common.initialize
connect = common.build_connect(Projection, FixedProbabilityConnector, StaticSynapse)
build_record = common.build_record
create = common.build_create(Population)

set = common.set
record = common.build_record(simulator)
record_v = lambda source, filename: record(['v'], source, filename)
record_gsyn = lambda source, filename: record(['gsyn_exc', 'gsyn_inh'], source, filename)

run, run_until = common.build_run(simulator)
run_for = run

reset = common.build_reset(simulator)

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
    global _hardware_list
    global _useSystemSim
    global _initializedSystemC
    global _preprocessor
    global _mapper
    global _postprocessor
    global _configurator
    global _neuronsChanged
    global _synapsesChanged
    global _connectivityChanged
    global _inputChanged
    global _externalInputs
    global _calledSetup
    global _dt
    global _rng_seeds
    global _systemSimTimeStepInPS
    global _speedupFactor
    global _tempFolder
    global toLog
    global ERROR
    global WARNING
    global INFO
    global DEBUG0
    global DEBUG1
    global DEBUG2
    global DEBUG3
    global _logfile
    global _loglevel
    global _setupstart
        
    _setupstart = time.time()
    
    common.setup(timestep, min_delay, max_delay, **extra_params)
    simulator.state.clear()
    
    # start of specific setup
    
    if extra_params.has_key('hardware'):
        _hardware_list = extra_params['hardware']
    else:
        _hardware_list = _default_extra_params['hardware']

    if 'loglevel' in extra_params.keys():
        _loglevel = extra_params['loglevel']
    else:
        _loglevel = 1

    if 'logfile' in extra_params.keys():
        _logfile = extra_params['logfile']
    else: 
        _logfile = 'logfile.txt'

    global logger
    logger = mapping.createLogger(_loglevel, _logfile)

    _preprocessor = mapping.preprocessor()
    _mapper = mapping.mapper()
    _postprocessor = mapping.postprocessor()

    # check for random number generator seed
    if 'rng_seeds' in extra_params.keys():
        _rng_seeds = extra_params['rng_seeds']
        _globalRNG.seed(extra_params['rng_seeds'][0])

    # print the available hardware version
    if _preprocessor.hardwareAvailable():
        toLog(INFO, 'Neuromorphic hardware is of type BrainSales HMF!')
    else:
        toLog(INFO, 'The assumed neuromorphic hardware is of type BrainScales HMF, but a real device is not available!')

    if _preprocessor.virtualHardwareAvailable():
        toLog(INFO, 'A virtual hardware, i.e. an executable system simulation, is available!')

    # check if system simulation shall be used
    if 'useSystemSim' in extra_params.keys():
        if not isinstance(extra_params['useSystemSim'], bool):
            raise TypeError, 'ERROR: pyNN.setup: argument useSystemSim must be of type bool!'
        _useSystemSim = extra_params['useSystemSim']
        if not _preprocessor.virtualHardwareAvailable() and _useSystemSim : 
            raise Exception("ERROR: Argument 'useSystemSim' of command setup() is set to True, but no virtual hardware is available!")
        if _useSystemSim :
            toLog(INFO, 'A virtual, i.e. purely simulated hardware system is used instead of a real device!')

    # check if speedup factor of the system is specified by user
    if 'speedupFactor' in extra_params.keys():
        # if yes, we have to scale the parameter ranges of neurons and synapses and update the the global parameter _speedupFactor
        _set_speedup_factor(extra_params['speedupFactor'])

    _set_trafo_params(extra_params)

    # set all changed-flags to true
    _neuronsChanged = True
    _synapsesChanged = True
    _connectivityChanged = True
    _inputChanged = True

    # the time step: for membrane traces used as sampling interval, for system simulation as integration time step
    _dt = timestep
    simulator._dt = timestep
    simulator.state._dt = timestep

    # create containers for input sources
    _externalInputs = []

    # create temp folder
    _create_temp_folder(extra_params)

    '''
    SETUP THE MAPPING PROCESS 1) HW MODEL
    '''

    _init_preprocessor(extra_params)

    # initialize the mapper
    _mapper.SetHWModel(_preprocessor.GetHWModel())
    _mapper.SetBioModel(_preprocessor.GetBioModel())
    _mapper.Initialize()

    # initialize the postprocessor
    _postprocessor.SetHWModel(_mapper.GetHWModel())
    _postprocessor.SetBioModel(_mapper.GetBioModel())
    _postprocessor.Initialize()

    _insert_global_hw_params(extra_params)

    # create and initialize the hardware configuration controller
    # if we are using the ESS, the configurator can be initialized only once, as the SystemC kernel can not be reset
    if _useSystemSim:
        if _initializedSystemC:
            raise Exception("ERROR: The System Simulation can be started only once per python program. Hence multiple calls of function 'setup()' are not possible.")
        else: _initializedSystemC = True
    _configurator = mapping.stage2configurator()

    for hardware in _hardware_list:
        assert isinstance(hardware, dict)
        if hardware['setup'] == "vertical_setup":
            wafer_id = hardware["wafer_id"]
            _configurator.setUseVerticalSetup(wafer_id, True);
            # check for IP and number of HICANNs in the jtag chain for vertical setup
            if hardware.has_key('setup_params'):
                vs_params = hardware['setup_params']
                if vs_params.has_key('ip'):
                    _configurator.setIPv4VerticalSetup(wafer_id, vs_params['ip']);
                if vs_params.has_key('num_hicanns'):
                    _configurator.setNumHicannsVerticalSetup(wafer_id, vs_params['num_hicanns'])
        else: # wafer
            wafer_id = hardware["wafer_id"]
            _configurator.setUseVerticalSetup(wafer_id, False);

    _configurator.init(_mapper.GetHWModel(), _mapper.GetBioModel(), _useSystemSim, _systemSimTimeStepInPS, _tempFolder)
    _configurator.setAcceleration(_speedupFactor)

    _init_mapping_statistics(extra_params)

    _calledSetup = True
    
    # end of specific setup
    
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
