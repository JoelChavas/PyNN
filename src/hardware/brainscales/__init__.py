# encoding: utf-8
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
from pyNN import common, standardmodels
from pyNN.connectors import *
from pyNN.recording import *
from pyNN.random import NumpyRNG

# hardware specific python modules
from . import simulator

# hardware specific PyNN modules
from .standardmodels.cells import EIF_cond_exp_isfa_ista, IF_cond_exp, SpikeSourcePoisson, supportedNeuronTypes
from .standardmodels.synapses import TsodyksMarkramMechanism, StaticSynapse
from .populations import Population, PopulationView, Assembly
from .projections import Projection
from electrodes import PeriodicCurrentSource, FG_ALLOWED_PERIODS


# utility modules
from documentation import _default_args, _default_extra_params, \
                        _hardware_args, _default_extra_params_ess

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
_useSystemSim = True
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

def _set_trafo_params(extra_params):
    """
    sets the parameter range and trafo settings from the extra_params.
    to be called from setup()
    Must be called before _init_preprocessor (for _useSmallCap)
    """
    global _useSmallCap
    import range_checker
    # check if we ignore the ranges of the hw parameters
    if 'ignoreHWParameterRanges' in extra_params.keys():
        if not isinstance(extra_params['ignoreHWParameterRanges'], bool):
            raise TypeError, 'ERROR: pyNN.setup: argument ignoreHWParameterRanges must be of type bool!'
        range_checker._ignoreHWParameterRanges = extra_params['ignoreHWParameterRanges']

    # check if we shall use the small capacitance
    if 'useSmallCap' in extra_params.keys():
        if not isinstance(extra_params['useSmallCap'], bool):
            raise TypeError, 'ERROR: pyNN.setup: argument useSmallCap must be of type bool!'
        if extra_params['useSmallCap'] == True:
            # if yes, we have to scale the parameter ranges of neurons and synapses.
            for model in [EIF_cond_exp_isfa_ista,IF_cond_exp]:
                model.scaleParameterRangesCap(SMALL_HW_CAP, BIG_HW_CAP)
        _useSmallCap = extra_params['useSmallCap']
        
def _create_temp_folder(extra_params):
    """
    creates tmp folder for ess simulation data
    looks for param 'tempFolder' in extra params
    if it exists, it is used as temporary folder
    otherwise a  folder under /tmp is created
    """
    global _tempFolder
    global _deltempFolder
    # check if name for temporary folder is specified by user
    if 'tempFolder' in extra_params.keys():
        _tempFolder = extra_params['tempFolder']
        # if folder already exists, clean it
        if os.access(_tempFolder, os.F_OK):
            import shutil
            shutil.rmtree(_tempFolder)
        os.makedirs(_tempFolder)
        _deltempFolder = False
    else:
        import tempfile
        _tempFolder = tempfile.mkdtemp(prefix='FacetsHW')
    toLog(DEBUG0, "Created folder " + str(_tempFolder) + " for temporary files needed by PyNN and Systemsim")

def _init_preprocessor(extra_params):
    """
    initialize preprocessor
    """
    global _hardware_list
    global _preprocessor
    global _rng_seeds
    global _interactiveMappingMode
    global _interactiveMappingModeGUI
    global _experimentName
    assert _preprocessor

    def user_or_default(param, user=extra_params, default=_default_extra_params, log=False):
        if user.has_key(param):
            val = user[param]
            assert isinstance(val, type(default[param])) # check for right type
        else:
            val = default[param]
        if log:
            toLog(INFO, '%s is set to %s' % (param, str(val)))
        return val

    _interactiveMappingMode = user_or_default('interactiveMappingMode')
    _interactiveMappingModeGUI = user_or_default('interactiveMappingModeGUI')
    _experimentName = user_or_default('experimentName')
    _mapping_quality_weights = user_or_default('mappingQualityWeights')

# FIXME -- ME: find a more elegant way for the conversion
    weigthdict = dict(_mapping_quality_weights[0])
    weightinput = mappingutilities.mapStringFloat()
    weightinput['G_HW'] = weigthdict['G_HW']
    weightinput['G_PR'] = weigthdict['G_PR']
    weightinput['G_T'] = weigthdict['G_T']
    _preprocessor.setMappingQualityWeights(weightinput)

    # check if hwinit filename is specified by user
    if 'hwinitFilename' in extra_params.keys():
        err_str = "pynn.setup(): parameter 'hwinitFilename' is not supported anymore"
        err_str += "\nuse *pynn.setup(hardware=<X>)' to specify your hardware setup"
        raise APIChangeError(err_str)

    # initialize the preprocessor
    _preprocessor.setRandomSeed(_rng_seeds[0])

    default_extra_params = _default_extra_params
    if _useSystemSim:
        default_extra_params = _default_extra_params_ess
    elif (len(_hardware_list) > 1):
        default_extra_params = _default_extra_params_multiwafer

    _preprocessor.setAlgoInitFileName(user_or_default('algoinitFilename', default=default_extra_params))
    _preprocessor.setJSONPathName(user_or_default('jsonPathname', default=default_extra_params))

    _preprocessor.setDatabaseHost(user_or_default('databaseHost'))
    _preprocessor.setDatabasePort(user_or_default('databasePort'))
    _preprocessor.setIgnoreDatabase(user_or_default('ignoreDatabase'))
    _preprocessor.setInteractiveMapping(_interactiveMappingMode)

    _mappingStrategy = user_or_default('mappingStrategy')
    mappingStrategyOptions = ['valid','normal','best','user']
    if _mappingStrategy in mappingStrategyOptions:
        _preprocessor.setMappingStrategy(_mappingStrategy)
    else :
        raise TypeError("Value for mappingStrategy is: " + _mappingStrategy + " but must be one of: " + str(mappingStrategyOptions))

    # when using the ESS: make sure there is not more than one Wafer
    if extra_params.has_key("useSystemSim"):
        if extra_params["useSystemSim"]:
            assert(len(_hardware_list) == 1), "When using the ESS, there can be maximally 1 hardware setup"

    # if hicannsMax is spefied, check if valid and set it, otherwise use the default
    if extra_params.has_key('hicannsMax'):
        hicannsMax = extra_params['hicannsMax']
        _default_args['hicannsMax'].check(hicannsMax)
        _preprocessor.setHicannsMax(hicannsMax)

    # settings for each wafer / vertical setup
    used_wafer_ids = []
    for hardware in _hardware_list:
        assert isinstance(hardware, dict)
        assert hardware.has_key("wafer_id") # in each 'hardware' dictionary, there must be the wafer_id
        wafer_id = hardware["wafer_id"]
        if wafer_id in used_wafer_ids:
            raise Exception("Hardware setup with wafer_id " + wafer_id + "already used in list of wafer setups")
        else:
            used_wafer_ids.append(wafer_id)
        if hardware.has_key("hicannIndices"):
            hicannIndices = hardware["hicannIndices"]
            _hardware_args["hicannIndices"].check(hicannIndices)
            _preprocessor.setHicannIndicesForWafer(wafer_id, list_to_vectorInt(hicannIndices))
    
    _preprocessor.setMaxSynapseLoss(user_or_default('maxSynapseLoss'))
    _preprocessor.setMaxNeuronLoss(user_or_default('maxNeuronLoss'))
    _preprocessor.setHardwareNeuronSize(user_or_default('hardwareNeuronSize'))
    # check if hwinit filename is specified by user
    if 'maxNeuronCountPerAnnCore' in extra_params.keys():
        err_str = "pynn.setup(): parameter 'maxNeuronCountPerAnnCore' is not supported anymore"
        err_str += "\nuse parameter 'hardwareNeuronSize' instead."
        err_str += "\nHint: the following relation holds: hardwareNeuronSize=512/maxNeuronCountPerAnnCore"
        raise APIChangeError(err_str)

    # now create the hwmodel
    _preprocessor.Initialize()


def _insert_global_hw_params(extra_params):
    global _preprocessor
    global _graphModelGlobalHardwareParameters
    global _speedupFactor
    global _dt
    global _useSmallCap
    global _useSystemSim

    _graphModelGlobalHardwareParameters = _preprocessor.HWModelInsertGlobalParameterSet('GlobalParameters')

    # insert speedup factor information
    _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"speedupFactor",str(_speedupFactor))
    toLog(DEBUG0, "Inserted global parameter speedupFactor " + str(_speedupFactor) + " into HWModel.")

    # insert capacitor choice information
    _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"useSmallCap",str(int(_useSmallCap)))
    toLog(DEBUG0, "Inserted global parameter useSmallCap" + str(int(_useSmallCap)) + " into HWModel.")

    if _useSystemSim :
        _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"use_systemsim",str(int(_useSystemSim)))

    if extra_params.has_key('ess_params'):
        ess_params = extra_params['ess_params']
        if 'weightDistortion' in ess_params.keys():
            weight_distortion = ess_params['weightDistortion']
            if not isinstance(weight_distortion, float):
                raise TypeError("Value for weightDistortion must be of type float")
            _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"weight_distortion",str(weight_distortion))
            toLog(DEBUG0, "Synaptic weights on the ESS are distorted by " + str(weight_distortion))
        if 'pulseStatisticsFile' in ess_params.keys():
            pulse_statistics_file = ess_params['pulseStatisticsFile']
            if not isinstance(pulse_statistics_file, str):
                raise TypeError("Value for pulseStatisticsFile must be of type str")
            _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"pulse_statistics_file",pulse_statistics_file)
            toLog(DEBUG0, "ESS pulse statistics are written to file " + pulse_statistics_file)
        if 'perfectSynapseTrafo' in ess_params.keys():
            perfect_synapse_trafo = ess_params['perfectSynapseTrafo']
            if not isinstance(perfect_synapse_trafo, bool):
                raise TypeError("Value for perfectSynapseTrafo must be of type bool")
            _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"perfect_synapse_trafo",str(int(perfect_synapse_trafo)))
            if perfect_synapse_trafo:
                toLog(DEBUG0, "Using a perfect synaptic weight transformation with the ESS")
                # change weight ranges to be arbitrary:
                for model in [EIF_cond_exp_isfa_ista,IF_cond_exp]:
                    model.parameter_ranges['weight']= (0.,float('inf'))
        if ess_params.has_key('hardwareSetup'):
            err_str = "pyNN.setup(): parameter 'hardwareSetup' in 'ess_params' is not supported anymore."
            err_str += "\nInstead of \n\t'pynn.setup(ess_params={'hardwareSetup':'small'})'"
            err_str += "\nuse\n\t'pynn.setup(hardware=pynn.hardwareSetup['small'])'"
            raise APIChangeError(err_str)

    if 'programFloatingGates' in extra_params.keys():
        programFG = None
        programFGoptions = ['never','once','always']
        if isinstance(extra_params['programFloatingGates'], bool):
            programFG = "always" if extra_params['programFloatingGates'] else "never"
            print "REMARK: the options for setup parameter 'programFloatingGates' have changed."
            print "New options are ['never','once','always']."
            print "'False' will be treated as 'never' and 'True' as 'always'"
            print "With option 'once' the FGs are only programmed once, when run() is called multiple times"
        elif extra_params['programFloatingGates'] in programFGoptions:
            programFG = extra_params['programFloatingGates']
        else:
            raise TypeError("Value for programFloatingGates must be one of: " + programFGoptions)
        _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"programFloatingGates", programFG)
        toLog(DEBUG0, "If using the real hardware, programFloatingGates equals " + programFG)

    if 'weightBoost' in extra_params.keys():
        if not isinstance(extra_params['weightBoost'], float):
            raise TypeError("Value for weightBoost must be of type float")
        if  extra_params['weightBoost'] < 0. or extra_params['weightBoost'] > 5.:
            raise ParameterValueOutOfRangeError('weightBoost', extra_params['weightBoost'], (0.,5.))
        _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"weightBoost",str(extra_params['weightBoost']))
        toLog(DEBUG0, "If using the real hardware, all weights(V_gmax) are boosted by " + str(extra_params['weightBoost']) )

    # For virtual hardware: simulation time step is used as integration time step in systemC
    if _preprocessor.virtualHardwareAvailable():
        _preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"timestep",str(_dt))
        toLog(DEBUG0, "Inserted global parameter timestep " + str(_dt) + " into HWModel.")


def _init_mapping_statistics(extra_params):
    """
    parses the mapping statistics related parameters from extra params
    and initializes the statistics instance, if needed.
    Must be called after initialization of preprocessor and models.
    """
    global _interactiveMappingMode
    global _mappingStatisticsFile
    global _fullConnectionMatrixFile
    global _realizedConnectionMatrixFile
    global _lostConnectionMatrixFile
    global _statistics
    global _mapper
    
    statistics_needed = False; # flag indicating whether statistics are needed

    if _interactiveMappingMode:
        toLog(INFO, 'PyNN: Mapping will be interactive')
        statistics_needed = True
        
    if 'mappingStatisticsFile' in extra_params.keys() and not extra_params['mappingStatisticsFile'] == None :
        _mappingStatisticsFile = extra_params['mappingStatisticsFile']
        logstring = 'Mapping Statistics are written to: ./mapping_statistics/'+_mappingStatisticsFile
        toLog(INFO,logstring)
        statistics_needed = True

    if 'fullConnectionMatrixFile' in extra_params.keys():
        _fullConnectionMatrixFile = extra_params['fullConnectionMatrixFile']
        statistics_needed = True
        
    if 'realizedConnectionMatrixFile' in extra_params.keys():
        _realizedConnectionMatrixFile = extra_params['realizedConnectionMatrixFile']
        statistics_needed = True
        
    if 'lostConnectionMatrixFile' in extra_params.keys():
        _lostConnectionMatrixFile = extra_params['lostConnectionMatrixFile']
        statistics_needed = True

    # if statistics are requested initialize statistics class
    if statistics_needed:
        _statistics = mapping.statistics()
        _statistics.SetHWModel(_mapper.GetHWModel())
        _statistics.SetBioModel(_mapper.GetBioModel())
        _statistics.Initialize()

class NoDelayWarning():
    """!
    Gives a Warning that there are currently no delay available on the hardware.
    """
    warning_called = False
    def __init__(self):
        if not NoDelayWarning.warning_called:
            delay_range_at_104 = numpy.array([1.2,4.4]) # cf. bss-neuron-parameters
            delay_range = delay_range_at_104*(_speedupFactor/1.e4)
            toLog(WARNING,"Synaptic Delays are currently not adjustable in the hardware. They will amount to values between {0} and {1} ms for your speedup factor of {2}.\n(This WARNING is raised only once!)\n".format(delay_range[0], delay_range[1], _speedupFactor))
            NoDelayWarning.warning_called = True


def _createSynapseParameterSet(weight=None, delay=None, synapse_type=None, mapping_priority=None, stp_parameters=None):
    """!
    Creates a new parameter set for a specific synapse or synapse group.

        Creates a parameter set for one or many synapses within the BioModel.

        @param weight           - the maximum of the transient conductance at this synapse, given in uS.
        @param delay            - the delay of this synapse, given in ms.
        @param synapse_type     - the type of this synapse, possible values are currently 'excitatory' and 'inhibitory'
        @param mapping_priority - a priority value between 0 and 1 that describes the importance of realizing this synapse in hardware
        @param stp_parameters   - a dictionary that keeps all STP parameters
    """

    if not _calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")

    global _numberOfSynapseParameterSets
    global _preprocessor

    newParameterSet = _preprocessor.BioModelInsertSynapseParameterSet(str(_numberOfSynapseParameterSets))
    _numberOfSynapseParameterSets += 1

    if not weight: weight = 0.0
    if not delay: delay = 0.0
    if not synapse_type:
        if weight < 0.0:
            synapse_type = "inhibitory"
        else:
            synapse_type = "excitatory"
    if synapse_type not in ["excitatory","inhibitory"]: raise Exception("ERROR: Argument synapse_type of function connect must be either 'excitatory' or 'inhibitory'!")
    if (weight < 0.0):
        weight = - weight;
    if not mapping_priority: mapping_priority = 1.0

    syn_params = SynParams()
    syn_params.weight = weight
    syn_params.mapping_priority = mapping_priority
    # TODO: what about delay?
    if synapse_type == "excitatory":
        syn_params.syn_type = enum_synapse_type.excitatory
    elif synapse_type == "inhibitory":
        syn_params.syn_type = enum_synapse_type.inhibitory
    if stp_parameters:
        syn_params.stp_enabled = True
        stp_params = STPParams()
        stp_params.U = stp_parameters['U']
        stp_params.tau_rec = stp_parameters['tau_rec']
        stp_params.tau_facil = stp_parameters['tau_facil']
        syn_params.stp_params = stp_params
    _preprocessor.BioModelAttachParamsToSynapseParameterNode(newParameterSet, syn_params)
    return newParameterSet

# =============================================================================
#   Utility low-level functions
# =============================================================================

def list_to_vectorInt(lst):
    """
    converts a python list into a boost python wrapped stl vector of ints
    """
    assert isinstance(lst,list)
    rv = mappingutilities.vectorInt()
    rv.extend(lst)
    return rv


# =============================================================================
#   Utility functions and classes
# =============================================================================

get_current_time, get_time_step, get_min_delay, get_max_delay, \
                    num_processes, rank = common.build_state_queries(simulator)
                    
# =============================================================================
#  Low-level API for creating, connecting and recording from individual neurons
# =============================================================================
initialize = common.initialize
build_record = common.build_record
create = common.build_create(Population)

set = common.set
record = common.build_record(simulator)
record_v = lambda source, filename: record(['v'], source, filename)
record_gsyn = lambda source, filename: record(['gsyn_exc', 'gsyn_inh'], source, filename)


def build_connect(projection_class, connector_class, static_synapse_class):

    def connect(source, target, weight=0.0, delay=None, receptor_type=None, p=1., rng=None, sharedParameters=True, **extra_params):
        """!
        Connects cells, e.g. neurons or spike sources.
    
        Connect a source of spikes to a synaptic target.
    
        source and target can both be individual cells or lists of cells, in which case all possible
        connections are made with probability p, using either the random number generator supplied,
        or the default rng otherwise. extra_params contains any keyword arguments that are required
        by a given simulator but not by others.
    
            @param source           - ID or list of IDs from which connections shall be established.
            @param target           - ID or list of IDs to which connections shall be established.
            @param weight           - maximum value of the transient synaptic conductance that is caused by spikes
                                      running into the established synapse. The unit of this value is uS (micro Siemens).
            @param delay            - delays are currently not supported by the hardware. If it is not None, it will be set to global min delay and a warning is raised.
            @param receptor_type     - "excitatory" or "inhibitory"
            @param p                - the connection probability, a value between 0.0 and 1.0
            @param rng              - optionally: a random number generator that implements the function "uniform"
            @param sharedParameters - if this is True, all n cells will get the same parameter node within the GraphModel.
                                      Otherwise for every cell an individual parameter node will be created and connected.
            @param synapse_dynamics - takes SynapseDynamics object to configure fast and short aka STP and STDP parameters
            @param extra_params     - any keyword arguments that are required by this PyNN back-end but not by others.
                                      Currently supported:
                                          @param mapping_priority - a float value between 0 and 1 that determines the importance
                                                                    of this synapse to be actually realized in the hardware system;
                                                                    defaults to 1.
                                          @param parameter_set    - an already existing synapse_parameter_set, i.e. a reference to a GMNode,
                                                                    created by _createSynapseParameterSet(...)
                                                                    if this parameter is passed and sharedParameters is True, all synapses will share this parameter set.
    
        """
    
        if not _calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")
        if _calledRunMapping: raise Exception("ERROR: Cannot connect cells after _run_mapping() has been called")
        if p > 1.: toLog(WARNING, "A connection probability larger than 1 has been passed as connect argument!")
    
        # check if mapping priority (a value between 0 and 1) has been passed
        if "mapping_priority" in extra_params.keys():
            priority = extra_params["mapping_priority"]
            if priority > 1.0 or priority < 0.0: raise Exception("ERROR: Only values between 0.0 and 1.0 are allowed for argument mapping_priority of function connect!")
        else: priority = 1.0
    
        # check if a parameter_set has been passed
        if "parameter_set" in extra_params.keys():
            existing_parameter_set = extra_params["parameter_set"]
        else:
            existing_parameter_set = None
            # if there is not yet a parameter set, we have to check the delays:
            if delay and (delay is not common.build_state_queries(simulator)[2]):
                delay = common.build_state_queries(simulator)[2];
                NoDelayWarning()
    
        synapse = static_synapse_class(weight=weight, delay=delay)
        if isinstance(synapse,StaticSynapse):
            stp_parameters = None
        elif isinstance(synapse,TsodyksMarkramMechanism):
            stp_parameters = TsodyksMarkramMechanism.parameters
        else:
            raise Exception("ERROR: The only short-term synaptic plasticity type supported by the BrainscaleS hardware is TsodyksMarkram!")
    
        if isinstance( source, (common.BasePopulation, Assembly) ):
            source = source.all_cells
        elif not isinstance( source, list):
            source = [source]
        if isinstance( target, (common.BasePopulation, Assembly) ):
            target = target.all_cells
        elif not isinstance( target, list):
            target= [target]
    
        global _synapsesChanged
        _synapsesChanged = True
        global _connectivityChanged
        _connectivityChanged = True
    
#         # Check for proper source cell type:
#         for src in source:
#             if not isinstance(src, simulator.ID): raise errors.ConnectionError("ERROR: Source element %s is not of type ID." %str(src))
#             if type(src.cell) not in supportedNeuronTypes:
#                 if type(src.cell) in [SpikeSourcePoisson, SpikeSourceArray]:
#                     global _inputChanged
#                     _inputChanged = True
#                 else: raise errors.ConnectionError("ERROR: Element %d of source is of type: %s. It is neither a supported neuron type nor a spike source." %(src, str(src.cellclass)))
#         # Check for proper target cell type:
#         for tgt in target:
#             if not isinstance(tgt, simulator.ID): raise errors.ConnectionError("ERROR: Target element %s is not of type ID." %str(tgt))
#             if type(tgt.cell) not in supportedNeuronTypes: raise errors.ConnectionError("ERROR: Element %d of target is of type: %s. It is not a supported neuron type." %(src, str(tgt.cellclass)))
#             tgt.cell.checkConductanceRange('weight',weight)
    
        global _preprocessor
    
        try:
            if sharedParameters:
                newParameterSet = existing_parameter_set or _createSynapseParameterSet(weight, delay, receptor_type, priority, stp_parameters)
            for src in source:
                if p < 1.:
                    if rng: # use the supplied RNG
                        rarr = rng.uniform(0.,1.,len(target))
                    else:   # use the default RNG
                        rarr = _globalRNG.uniform(0.,1.,len(target))
                for j,tgt in enumerate(target):
                    # evaluate if a connection has to be created
                    if p >= 1. or rarr[j] < p:
                        toLog(DEBUG1, 'Connecting ' + str(src) + ' with ' + str(tgt) + ' and weight ' + str(weight))
                        if not sharedParameters: newParameterSet = _createSynapseParameterSet(weight, delay, receptor_type, priority, stp_parameters)
                        _preprocessor.BioModelInsertSynapse(src.graphModelNode,tgt.graphModelNode,newParameterSet)

            connector = connector_class(p_connect=p, rng=rng)
            return projection_class(source, target, connector, receptor_type=receptor_type,
                                    synapse_type=synapse)
    
        except Exception,e:
            raise errors.ConnectionError(e)
    
    return connect

connect = build_connect(Projection, FixedProbabilityConnector, StaticSynapse)

# ==============================================================================
#   Functions for simulation set-up and control
# ==============================================================================

run, run_until = common.build_run(simulator)
run_for = run

reset = common.build_reset(simulator)

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
    return [obj.__name__ for obj in globals().values() if isinstance(obj, type) and issubclass(obj, standardmodels.StandardCellType)]


def end(compatible_output=True):
    """Do any necessary cleaning up before exiting."""
    
    # gain access to the objects which are to be cleaned
    global _preprocessor
    global _mapper
    global _postprocessor
    global _statistics
    global _configurator
    global _calledSetup
    global _calledRunMapping
    global _numberOfNeurons
    global _iteration
    
    # clear list of place instances
    mapper.placer_list = []
    
    # Destroy the mapping and configuration instances
    if _postprocessor is not None:
        toLog(INFO, "Erasing GraphModels.")
        _postprocessor.EraseModels()
    _preprocessor = None
    _mapper = None
    _postprocessor = None
    _statistics = None
    _configurator = None
    _calledSetup = False
    _calledRunMapping = False

    # reset the number of neurons created so far
    _numberOfNeurons = 0
    
    for (population, variables, filename) in simulator.state.write_on_end:
        io = get_io(filename)
        population.write_data(io, variables)
    simulator.state.write_on_end = []
    # should have common implementation of end()
