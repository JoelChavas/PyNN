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
import sys

# common PyNN modules
from pyNN import common, standardmodels
from pyNN.connectors import *
from pyNN.recording import *
from pyNN.parameters import ParameterSpace
import recording

# hardware specific python modules
from . import simulator

# hardware specific PyNN modules
from .standardmodels.cells import EIF_cond_exp_isfa_ista, IF_cond_exp, SpikeSourcePoisson, SpikeSourceArray, supportedNeuronTypes
from .standardmodels.synapses import TsodyksMarkramMechanism, StaticSynapse
from .populations import Recorder, Population, PopulationView, Assembly
from .projections import Projection
from .electrodes import PeriodicCurrentSource, FG_ALLOWED_PERIODS


# utility modules
from documentation import _default_args, _default_extra_params, \
                        _hardware_args, _default_extra_params_ess
from hardware_config import setup as hardwareSetup

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

import globals as g
                          
logger = logging.getLogger("PyNN")

# ==============================================================================
#   Utility functions
# ==============================================================================


def _set_speedup_factor(speedup):
    """!
    sets speedup factor and scales the allowed parameter ranges for all models to the current speedup.
    @param speedup - new speedup factor
    """
    g._speedupFactor = speedup
    # scaling parameter ranges
    for model in [EIF_cond_exp_isfa_ista,IF_cond_exp,SpikeSourcePoisson,SpikeSourceArray,TsodyksMarkramMechanism]:
        model.scaleParameterRangesTime(g._speedupFactor)
    # also update the allowed periods of PeriodicCurrentSource
    PeriodicCurrentSource.ALLOWED_PERIODS = FG_ALLOWED_PERIODS(g._speedupFactor)

def _set_trafo_params(extra_params):
    """
    sets the parameter range and trafo settings from the extra_params.
    to be called from setup()
    Must be called before _init_preprocessor (for g._useSmallCap)
    """
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
        g._useSmallCap = extra_params['useSmallCap']
        
def _create_temp_folder(extra_params):
    """
    creates tmp folder for ess simulation data
    looks for param 'tempFolder' in extra params
    if it exists, it is used as temporary folder
    otherwise a  folder under /tmp is created
    """
    # check if name for temporary folder is specified by user
    if 'tempFolder' in extra_params.keys():
        g._tempFolder = extra_params['tempFolder']
        # if folder already exists, clean it
        if os.access(g._tempFolder, os.F_OK):
            import shutil
            shutil.rmtree(g._tempFolder)
        os.makedirs(g._tempFolder)
        g._deltempFolder = False
    else:
        import tempfile
        g._tempFolder = tempfile.mkdtemp(prefix='FacetsHW')
    toLog(DEBUG0, "Created folder " + str(g._tempFolder) + " for temporary files needed by PyNN and Systemsim")

def _init_preprocessor(extra_params):
    """
    initialize preprocessor
    """

    def user_or_default(param, user=extra_params, default=_default_extra_params, log=False):
        if user.has_key(param):
            val = user[param]
            assert isinstance(val, type(default[param])) # check for right type
        else:
            val = default[param]
        if log:
            toLog(INFO, '%s is set to %s' % (param, str(val)))
        return val

    g._interactiveMappingMode = user_or_default('interactiveMappingMode')
    g._interactiveMappingModeGUI = user_or_default('interactiveMappingModeGUI')
    g._experimentName = user_or_default('experimentName')
    g._mapping_quality_weights = user_or_default('mappingQualityWeights')

# FIXME -- ME: find a more elegant way for the conversion
    weigthdict = dict(g._mapping_quality_weights[0])
    weightinput = mappingutilities.mapStringFloat()
    weightinput['G_HW'] = weigthdict['G_HW']
    weightinput['G_PR'] = weigthdict['G_PR']
    weightinput['G_T'] = weigthdict['G_T']
    g._preprocessor.setMappingQualityWeights(weightinput)

    # check if hwinit filename is specified by user
    if 'hwinitFilename' in extra_params.keys():
        err_str = "pynn.setup(): parameter 'hwinitFilename' is not supported anymore"
        err_str += "\nuse *pynn.setup(hardware=<X>)' to specify your hardware setup"
        raise APIChangeError(err_str)

    # initialize the preprocessor
    g._preprocessor.setRandomSeed(g._rng_seeds[0])

    default_extra_params = _default_extra_params
    if g._useSystemSim:
        default_extra_params = _default_extra_params_ess
    elif (len(g._hardware_list) > 1):
        default_extra_params = _default_extra_params_multiwafer

    g._preprocessor.setAlgoInitFileName(user_or_default('algoinitFilename', default=default_extra_params))
    g._preprocessor.setJSONPathName(user_or_default('jsonPathname', default=default_extra_params))

    g._preprocessor.setDatabaseHost(user_or_default('databaseHost'))
    g._preprocessor.setDatabasePort(user_or_default('databasePort'))
    g._preprocessor.setIgnoreDatabase(user_or_default('ignoreDatabase'))
    g._preprocessor.setInteractiveMapping(g._interactiveMappingMode)

    g._mappingStrategy = user_or_default('mappingStrategy')
    mappingStrategyOptions = ['valid','normal','best','user']
    if g._mappingStrategy in mappingStrategyOptions:
        g._preprocessor.setMappingStrategy(g._mappingStrategy)
    else :
        raise TypeError("Value for mappingStrategy is: " + g._mappingStrategy + " but must be one of: " + str(mappingStrategyOptions))

    # when using the ESS: make sure there is not more than one Wafer
    if extra_params.has_key("useSystemSim"):
        if extra_params["useSystemSim"]:
            assert(len(g._hardware_list) == 1), "When using the ESS, there can be maximally 1 hardware setup"

    # if hicannsMax is spefied, check if valid and set it, otherwise use the default
    if extra_params.has_key('hicannsMax'):
        hicannsMax = extra_params['hicannsMax']
        _default_args['hicannsMax'].check(hicannsMax)
        g._preprocessor.setHicannsMax(hicannsMax)

    # settings for each wafer / vertical setup
    used_wafer_ids = []
    for hardware in g._hardware_list:
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
            g._preprocessor.setHicannIndicesForWafer(wafer_id, list_to_vectorInt(hicannIndices))
    
    g._preprocessor.setMaxSynapseLoss(user_or_default('maxSynapseLoss'))
    g._preprocessor.setMaxNeuronLoss(user_or_default('maxNeuronLoss'))
    g._preprocessor.setHardwareNeuronSize(user_or_default('hardwareNeuronSize'))
    # check if hwinit filename is specified by user
    if 'maxNeuronCountPerAnnCore' in extra_params.keys():
        err_str = "pynn.setup(): parameter 'maxNeuronCountPerAnnCore' is not supported anymore"
        err_str += "\nuse parameter 'hardwareNeuronSize' instead."
        err_str += "\nHint: the following relation holds: hardwareNeuronSize=512/maxNeuronCountPerAnnCore"
        raise APIChangeError(err_str)

    # now create the hwmodel
    g._preprocessor.Initialize()


def _insert_global_hw_params(extra_params):

    _graphModelGlobalHardwareParameters = g._preprocessor.HWModelInsertGlobalParameterSet('GlobalParameters')

    # insert speedup factor information
    g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"speedupFactor",str(g._speedupFactor))
    toLog(DEBUG0, "Inserted global parameter speedupFactor " + str(g._speedupFactor) + " into HWModel.")

    # insert capacitor choice information
    g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"useSmallCap",str(int(g._useSmallCap)))
    toLog(DEBUG0, "Inserted global parameter useSmallCap" + str(int(g._useSmallCap)) + " into HWModel.")

    if g._useSystemSim :
        g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"use_systemsim",str(int(g._useSystemSim)))

    if extra_params.has_key('ess_params'):
        ess_params = extra_params['ess_params']
        if 'weightDistortion' in ess_params.keys():
            weight_distortion = ess_params['weightDistortion']
            if not isinstance(weight_distortion, float):
                raise TypeError("Value for weightDistortion must be of type float")
            g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"weight_distortion",str(weight_distortion))
            toLog(DEBUG0, "Synaptic weights on the ESS are distorted by " + str(weight_distortion))
        if 'pulseStatisticsFile' in ess_params.keys():
            pulse_statistics_file = ess_params['pulseStatisticsFile']
            if not isinstance(pulse_statistics_file, str):
                raise TypeError("Value for pulseStatisticsFile must be of type str")
            g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"pulse_statistics_file",pulse_statistics_file)
            toLog(DEBUG0, "ESS pulse statistics are written to file " + pulse_statistics_file)
        if 'perfectSynapseTrafo' in ess_params.keys():
            perfect_synapse_trafo = ess_params['perfectSynapseTrafo']
            if not isinstance(perfect_synapse_trafo, bool):
                raise TypeError("Value for perfectSynapseTrafo must be of type bool")
            g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"perfect_synapse_trafo",str(int(perfect_synapse_trafo)))
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
        g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"programFloatingGates", programFG)
        toLog(DEBUG0, "If using the real hardware, programFloatingGates equals " + programFG)

    if 'weightBoost' in extra_params.keys():
        if not isinstance(extra_params['weightBoost'], float):
            raise TypeError("Value for weightBoost must be of type float")
        if  extra_params['weightBoost'] < 0. or extra_params['weightBoost'] > 5.:
            raise ParameterValueOutOfRangeError('weightBoost', extra_params['weightBoost'], (0.,5.))
        g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"weightBoost",str(extra_params['weightBoost']))
        toLog(DEBUG0, "If using the real hardware, all weights(V_gmax) are boosted by " + str(extra_params['weightBoost']) )

    # For virtual hardware: simulation time step is used as integration time step in systemC
    if g._preprocessor.virtualHardwareAvailable():
        g._preprocessor.HWModelInsertParameter(_graphModelGlobalHardwareParameters,"timestep",str(g._dt))
        toLog(DEBUG0, "Inserted global parameter timestep " + str(g._dt) + " into HWModel.")


def _init_mapping_statistics(extra_params):
    """
    parses the mapping statistics related parameters from extra params
    and initializes the statistics instance, if needed.
    Must be called after initialization of preprocessor and models.
    """
    
    statistics_needed = False; # flag indicating whether statistics are needed

    if g._interactiveMappingMode:
        toLog(INFO, 'PyNN: Mapping will be interactive')
        statistics_needed = True
        
    if 'mappingStatisticsFile' in extra_params.keys() and not extra_params['mappingStatisticsFile'] == None :
        g._mappingStatisticsFile = extra_params['mappingStatisticsFile']
        logstring = 'Mapping Statistics are written to: ./mapping_statistics/'+g._mappingStatisticsFile
        toLog(INFO,logstring)
        statistics_needed = True

    if 'fullConnectionMatrixFile' in extra_params.keys():
        g._fullConnectionMatrixFile = extra_params['fullConnectionMatrixFile']
        statistics_needed = True
        
    if 'realizedConnectionMatrixFile' in extra_params.keys():
        g._realizedConnectionMatrixFile = extra_params['realizedConnectionMatrixFile']
        statistics_needed = True
        
    if 'lostConnectionMatrixFile' in extra_params.keys():
        g._lostConnectionMatrixFile = extra_params['lostConnectionMatrixFile']
        statistics_needed = True

    # if statistics are requested initialize statistics class
    if statistics_needed:
        g._statistics = mapping.statistics()
        g._statistics.SetHWModel(g._mapper.GetHWModel())
        g._statistics.SetBioModel(g._mapper.GetBioModel())
        g._statistics.Initialize()

def pynnHardwarePoisson(start, duration, freq, prng):
    """!

    Returns a poisson spike train.

    Returns an STL vector containing a Poisson type spike train that is
    to be sent to the hardware with events given in msec.

        @param start    - start of the firing activity, given in ms.
        @param duration - duration of the firing activity, given in ms.
        @param freq     - frequency of the Poissonian firing activity, given in Hz.
        @param prng     - a random number generator that supports the functions 'poisson' and 'uniform'.

        @return st     - STL vector of spike times representing doubles
    """

    # determine number of spikes
    N = prng.poisson(duration*freq/1000.0)
    p = prng.uniform(start,start+duration,N)
    p = p.tolist()
    p.sort()

    st = mappingutilities.vectorDouble()
    st.extend(p)
    return st


def pynnHardwareSpikeArray(spike_times):
    """!
    Returns a spike train.

    Returns an STL vector containing a spike train that is
    to be sent to the hardware with events given in msec.

        @param spike_times - an iterable array with spike times given in msec.

        @return st - STL vector of spike times representing doubles
    """

    st = mappingutilities.vectorDouble()
    st.extend(spike_times)
    return st

class NoDelayWarning():
    """!
    Gives a Warning that there are currently no delay available on the hardware.
    """
    warning_called = False
    def __init__(self):
        if not NoDelayWarning.warning_called:
            delay_range_at_104 = numpy.array([1.2,4.4]) # cf. bss-neuron-parameters
            delay_range = delay_range_at_104*(g._speedupFactor/1.e4)
            toLog(WARNING,"Synaptic Delays are currently not adjustable in the hardware. They will amount to values between {0} and {1} ms for your speedup factor of {2}.\n(This WARNING is raised only once!)\n".format(delay_range[0], delay_range[1], g._speedupFactor))
            NoDelayWarning.warning_called = True


def _createStimulusParameterSet(cellclass,cellparams=None):
    """!
    Creates a new GraphModel parameter set node for a specific stimulus or stimuli group.

        @param cellclass  - the cell class for which a parameter set shall be created.
        @param cellparams - a dictionary with the parameters that shall be inserted into the GraphModel.
    """

    if not g._calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")

    if cellclass in [SpikeSourcePoisson, SpikeSourceArray] or isinstance(cellclass,SpikeSourcePoisson) or isinstance(cellclass,SpikeSourceArray):
        newParameterSet = g._preprocessor.BioModelInsertNeuronParameterSet(str(g._numberOfNeuronParameterSets))
        g._numberOfNeuronParameterSets += 1

        # check if parameters are provided
        if cellparams: parameters = cellparams
        else: parameters = cellclass.default_parameters

        for p in parameters.keys():
            # spike times will be written to graph model during run() call
            if not p=='spike_times':
                toLog(DEBUG0, 'Adding parameter ' + str(p) + ' with value ' + str(parameters[p]))
                g._preprocessor.BioModelInsertParameter(newParameterSet, p, str(parameters[p]))

    else:
        exceptionString = "ERROR: Wrong cell type given to _createStimulusParameterSet!"
        raise Exception(exceptionString)
    return newParameterSet

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

    if not g._calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")

    newParameterSet = g._preprocessor.BioModelInsertSynapseParameterSet(str(g._numberOfSynapseParameterSets))
    g._numberOfSynapseParameterSets += 1

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
    g._preprocessor.BioModelAttachParamsToSynapseParameterNode(newParameterSet, syn_params)
    return newParameterSet


def assertStimulationSpikeTrain(inputID, regenerate=True):
    """!
    Asserts that a spike train is available for the external input with the ID inputID.

    The format of the spike train is an STL vector of doubles and will be attached to the input's GraphModel Node.

        @param inputID    - an ID of the spike source the spike train of which shall be returned.
        @param regenerate - if this boolean is false, the spike trains that possibly already have been generated in previous
                            runs will be used, no new vectors will be generated. Otherwise, the return vectors will be
                            fully re-generated.
    """

    global _globalRNG
    global _preprocessor
    global _simtime

    # get pyNN cell object from ID
    pynnObject = inputID.cell

    # the graphModel node from ID
    gmNode = inputID.graphModelNode

    # generate / extract spike times
    if pynnObject.__class__.__name__ == 'SpikeSourcePoisson':
        if regenerate or (not inputID.has_spikes):
            # only generate spike train, if stimulus is provided externally and not via background event generator.
            if _preprocessor.BioModelStimulusIsExternal(gmNode):
                dur = pynnObject.parameters['duration']
                if dur > _simtime:
                    dur = _simtime
                st = pynnHardwarePoisson(pynnObject.parameters['start'], dur, pynnObject.parameters['rate'], _globalRNG)
                #_preprocessor.InsertVectorDoubleToGMNodeData(gmNode, st)
                _preprocessor.BioModelAttachSpikeTrainToStimulus(gmNode, st)
                inputID.has_spikes = True
    elif pynnObject.__class__.__name__ == 'SpikeSourceArray':
        if regenerate or (not inputID.has_spikes):
            st = pynnHardwareSpikeArray(pynnObject.parameter_space._parameters['spike_times'])
            #_preprocessor.InsertVectorDoubleToGMNodeData(gmNode, st)
            g._preprocessor.BioModelAttachSpikeTrainToStimulus(gmNode, st)
            inputID.has_spikes = True
            
def _createNeuronParameterSet(cellclass,cellparams=None):
    """!
    Creates a new GraphModel parameter set node for a specific neuron or neuron group.

    Creates a parameter set for one or many neurons within the BioModel
    (a graph container for the neural network described by PyNN).

        @param cellclass  - the cell class for which a parameter set shall be created.
        @param cellparams - a dictionary with the parameters that shall be inserted into the GraphModel.
    """

    if not g._calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")


    newParameterSet = g._preprocessor.BioModelInsertNeuronParameterSet(str(g._numberOfNeuronParameterSets))
    g._numberOfNeuronParameterSets += 1
    if cellparams: parameters = cellparams
    else: parameters = cellclass.default_parameters
    for p in parameters.keys():
        toLog(DEBUG0, 'Adding parameter ' + str(p) + ' with value ' + str(parameters[p]))
        g._preprocessor.BioModelInsertParameter(newParameterSet, p, str(parameters[p]))

    # for neurons only: append information about membrane recording
    g._preprocessor.BioModelInsertParameter(newParameterSet, "record_membrane", "0")
    g._preprocessor.BioModelInsertParameter(newParameterSet, "record_membrane_filename", "")
    g._preprocessor.BioModelInsertParameter(newParameterSet, "record_spikes", "0")
    g._preprocessor.BioModelInsertParameter(newParameterSet, "record_spikes_filename", "")

    return newParameterSet


class ID(int,common.IDMixin):
    """!
    An integer ID that stores additional information about PyNN cells.

    An integer ID that stores additional information about PyNN cells
    like e.g. their corresponding node in the GraphModel.

    @param int - ...
    @param common.IDMixin - ...

    Instead of storing ids as integers, we store them as ID objects,
    which allows a syntax like:
        p[3,4].tau_m = 20.0
    where p is a Population object.

    The question is, how big a memory/performance hit is when replacing integers with ID objects?

    Hardware specific:

        The additional member .cell is of type:
            EIF_cond_alpha_isfa_ista, IF_cond_exp_gsfa_grr, SpikeSourcePoisson or SpikeSourceArray
            It is generated by create() automatically.

        The additional members graphModelNode and graphModelNodeParams are also stored to keep
        track of this ID within the GraphModel.
    """

    non_parameter_attributes = ('parent', '_cellclass', 'cellclass',
                                '_position', 'position', 'hocname', '_cell',
                                'inject', '_v_init', 'local','graphModelNode',
                                'graphModelNodeParams','tag', 'has_spikes', 'local', 'posX', 'posY', 'posZ', 'rgba')

    def __init__(self, index, cell, graphModelNode=None, graphModelNodeParams=None, **extra_params):
        """!
        Constructor of class ID.

            @param index                - an integer defining the base class value of this ID.
            @param cell                 - a reference to the PyNN cell this ID is associated with.
            @param graphModelNode       - a reference to the GraphModel node this ID is associated with.
            @param graphModelNodeParams - a reference to the GraphModel parameter node this ID is associated with.
            @param extra_params         - any keyword arguments that are required by this PyNN back-end but not by others.
                                          Currently supported:
                                              @param id_tag     - a string that helps to identify this cell within the GraphModel.
                                              @param has_spikes - a boolean that indicates if this object owns stimulation spikes
        """

        int.__init__(index)
        common.IDMixin.__init__(self)
        object.__setattr__(self,'cell',cell)
        self.cellclass = cell.__class__
        self.graphModelNode = graphModelNode
        self.graphModelNodeParams = graphModelNodeParams
        if 'id_tag' in extra_params.keys():
            toLog(DEBUG0, 'Adding tag ' + str(extra_params['id_tag']) + ' to cell ' + self.__str__())
            self.tag = extra_params['id_tag']
        if 'has_spikes' in extra_params.keys():
            self.has_spikes = extra_params['has_spikes']
        else: self.has_spikes = False

    def __new__(cls, index, cell, graphModelNode, graphModelNodeParams, **extra_params):
        inst = super(ID, cls).__new__(cls, index)
        return inst

    def __getattr__(self, name):
        if self.cell.parameters.has_key(name):
            return self.cell.parameters[name]
        else:
            return object.__getattribute__(self,name)

    def __setattr__(self,name,value):
        if name == 'position':
            self.graphModelNode.posX = value[0]
            self.graphModelNode.posY = value[1]
            self.graphModelNode.posZ = value[2]
        if name == 'rgba':
            self.graphModelNode.colR = value[0]
            self.graphModelNode.colG = value[1]
            self.graphModelNode.colB = value[2]
            self.graphModelNode.colA = value[3]
        if name in ID.non_parameter_attributes or not self.is_standard_cell():
            object.__setattr__(self, name, value)
        else:
            return self.set_parameters(**{name:value})


    def set_native_parameters(self, parameters):
        """!
        Set parameters of the hardware cell model from a dictionary.
        """

        self.cell.parameters.update(parameters)

    def get_native_parameters(self):
        """!
        Get parameters of the hardware cell model from a dictionary.
        """

        return self.cell.parameters


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


def _create(cellclass, cellparams=None, n=1, sharedParameters=True, **extra_params):
    """!

    Creates cells, e.g. neurons or spike sources.

    Creates n cells all of the same type and returns a single ID or a list of IDs for n=1 and n>1, respectively.

    The ID indices are positive, starting with 0 for the first neurons created after setup(),
    then counting up. They are negative for spike sources created, starting with -1, then
    counting down.

        @param cellclass        - the type of the cell to be created.
        @param cellparams       - parameter dictionary for the cells to be created.
        @param n                - the number of cells to be created.
        @param sharedParameters - if this is True, all n cells will get the same parameter node within the GraphModel.
                                  Otherwise for every cell an individual parameter node will be created and connected.
        @param extra_params     - any keyword arguments that are required by this PyNN back-end but not by others.
                                  Currently supported:
                                      @param cell_tag - a string that specifies a name of the cell to be created. The name will
                                                        be only used in the extracted low-level API version of a script in case
                                                        the mapping analysis is enabled.
    """

    if not g._calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")
    if g._calledRunMapping: raise Exception("ERROR: Cannot create cells after _run_mapping() has been called")
    if not (n > 0 and isinstance(n, int)): raise Exception('ERROR: Argument n of function create must be a positive integer.')

    g._neuronsChanged = True
    # TODO: if spikeSources are generated, g._inputChanged = True ?


    if not 'cell_tag' in extra_params.keys(): cell_tag_base = None
    else: cell_tag_base = extra_params['cell_tag']

    if cellclass in supportedNeuronTypes or type(cellclass) in supportedNeuronTypes:
        returnList = []
        for i in xrange(n):
            cell_tag = cell_tag_base
            pynnNeuronClass = type(cellclass)
            pynnNeuron = pynnNeuronClass(**cellparams)
            if (i == 0) or (not sharedParameters):
                # transforms a dictionary with lazyarray values (pynnNeuron.parameter_space._parameters, and cellparams) into a dictionary with real values
                # before giving it to the _createNeuronParameterSet
		#TODO: this part should be put into _createNeuronParameterSet
                pynnNeuronParam = {}
                param = pynnNeuron.translate(pynnNeuron.parameter_space)._parameters
                for key in param:
		    param[key].shape =  (1,)
		    pynnNeuronParam[key] = param[key].evaluate()[0]
                newParameterSet = _createNeuronParameterSet(pynnNeuronClass, pynnNeuronParam)
                g._preprocessor.BioModelInsertParameter(newParameterSet, "cellclass", pynnNeuronClass.__name__)
                if cell_tag_base:
                    g._preprocessor.BioModelInsertParameter(newParameterSet, "pop_label", cell_tag_base)
            bioGraphNeuron = g._preprocessor.BioModelInsertSpikeRecordableNeuron(str(g._numberOfNeurons))
            g._preprocessor.BioModelAssignElementToParameterSet(bioGraphNeuron,newParameterSet)
            returnList.append( ID(g._numberOfNeurons, pynnNeuron, bioGraphNeuron, newParameterSet, id_tag=cell_tag) )
            if cell_tag: g._preprocessor.BioModelInsertNeuronTag(bioGraphNeuron, cell_tag)
            g._numberOfNeurons += 1
        if n == 1: return returnList[0]
        else: return returnList

    elif cellclass == SpikeSourcePoisson or cellclass == SpikeSourceArray or isinstance(cellclass, SpikeSourceArray):
        returnList = []
        if cellparams and cellparams.has_key('spike_times'):
            # check type of spike times container
#            if not hasattr(cellparams['spike_times'],'__len__'): raise TypeError("ERROR: Value of 'spike_times' has to be iterable!")
            # assure that type of spike time list is a python list. If it was a numpy array, the str value will have no commas,
            # which causes problems during mapping analysis
            cellparams['spike_times'] = list(cellparams['spike_times'].base_value.value)
        for i in xrange(n):
            cell_tag = cell_tag_base
            pynnSpikeSource = cellclass
            if (i == 0) or (not sharedParameters):
                newParameterSet = _createStimulusParameterSet(cellclass)
                g._preprocessor.BioModelInsertParameter(newParameterSet, "cellclass", cellclass.__name__)
            newExternalInputSize = numpy.size(g._externalInputs)+1
            index = -newExternalInputSize
            bioGraphSpikeSourceNode = g._preprocessor.BioModelInsertStimulus(str(index))
            g._preprocessor.BioModelAssignElementToParameterSet(bioGraphSpikeSourceNode,newParameterSet)
            newID = ID(index, pynnSpikeSource, bioGraphSpikeSourceNode, newParameterSet, has_spikes=False)
            returnList.append(newID)
            # write spikes to spike source array
            # (for SpikeSourcePoisson this is done later, in run(), see comment there)
            if cellparams and cellparams.has_key('spike_times'):
                st = pynnHardwareSpikeArray(cellparams['spike_times'])
                g._preprocessor.BioModelAttachSpikeTrainToStimulus(bioGraphSpikeSourceNode, st)
                newID.has_spikes = True
            if cell_tag: g._preprocessor.BioModelInsertNeuronTag(bioGraphSpikeSourceNode, cell_tag)
            g._externalInputs.append(returnList[-1])
        if n == 1: return returnList[0]
        else: return returnList

    else:
        exceptionString = "ERROR: Has to be cell type " + EIF_cond_exp_isfa_ista.__name__ + " or " + SpikeSourcePoisson.__name__ + " or " + SpikeSourceArray.__name__ # Why does it have to be EIF_cond_alpha_isfa_ista?
        raise Exception(exceptionString)
 

def _run_mapping():
    """!
    Run mapping without starting the experiment.
    After this function has been called, the following is currently NOT possible anymore:
        - create or connect neurons, spike and current sources.
        - change neuron, synapse, or current source parameters
        - add recording of voltages or spikes
    The following is possible:
        - change input spikes
    """

    if not g._calledSetup: 
        raise Exception("ERROR: Call function 'setup(...)' first!")

    if g._interactiveMappingMode == True :
        import mappinginteractive
        from PyQt4 import QtGui
        _app = QtGui.QApplication(sys.argv)

    biomodelsize = 0
    hwmodelsize = 0
    setuptime = 0
    mappingruntime = 0

    if not g._calledRunMapping:
        # update hardware configuration
        if (g._neuronsChanged or g._synapsesChanged or g._connectivityChanged):
            if g._interactiveMappingMode == True :
                toLog(WARNING, "Interactive Mapping mode, show Pre-Processing results not yet fully implemented!")
                _widget = mappinginteractive.InteractiveMapping( statistics = g._statistics,
                        mappingstep = 0,
                        mappinglog = g._logfile,
                        experimentname = str(g._experimentName),
                        ignoredb = bool(g._preprocessor.getIgnoreDatabase()),
                        dbip = str(g._preprocessor.getDatabaseHost()),
                        dbport = str(g._preprocessor.getDatabasePort()),
                        jsons = str(g._preprocessor.getJSONPathName()) )
                if g._interactiveMappingModeGUI :
                    _widget.show()
                    _app.exec_()

            # check if there is an uncommited placement
            for manual_placer in mapper.placer_list:
                if not manual_placer.committed:
                    raise Exception("Error: Manual Mapping is not commited. run 'placer.commit()' first!")

            # get sizes of data models before mappping
            if not g._mappingStatisticsFile == None :
                biomodelsize = g._statistics.GetBioModelSize()
                hwmodelsize = g._statistics.GetHWModelSize()
                
            # mapping process is initiated here
            setuptime = time.time() - g._setupstart
            mappingstart = time.time()
            g._mapper.Run()
            mappingruntime = time.time() - mappingstart

            if g._interactiveMappingMode == True :
                toLog(WARNING, "Interactive Mapping mode, show Post-Processing results not yet fully implemented!")
                 
                _widget = mappinginteractive.InteractiveMapping(statistics = g._statistics,
                        mappingstep = 1,
                        mappinglog = g._logfile,
                        experimentname = str(g._experimentName),
                        ignoredb = bool(g._preprocessor.getIgnoreDatabase()),
                        dbip = str(g._preprocessor.getDatabaseHost()),
                        dbport = str(g._preprocessor.getDatabasePort()),
                        jsons = str(g._preprocessor.getJSONPathName()) )
                if g._interactiveMappingModeGUI :
                    _widget.show()
                    _app.exec_()

        if not g._mappingStatisticsFile == None :
            '''
            create a statistics file containing the mapping statistics
            '''
            if not os.path.exists('mapping_statistics'):
                os.makedirs('mapping_statistics')
            f = open('mapping_statistics/'+g._mappingStatisticsFile,'w')
            f.write("# neurons[abs] synapses[abs] stimuli[abs] stimsynapses[abs] mappingquality[rel] neuronloss[rel] synapseloss[rel] hwefficiency[rel] biomodelsize[Byte] hwmodelsize[Byte] setuptime[s] runtime[s]\n")
            f.write(str(g._statistics.GetBioNeuronCount())+" ")
            f.write(str(g._statistics.GetBioSynapseCount())+" ")
            f.write(str(g._statistics.GetBioStimuliCount())+" ")
            f.write(str(g._statistics.GetBioStimuliSynapseCount())+" ")
            f.write(str(g._statistics.GetMappingQuality())+" ")
            f.write(str(g._statistics.GetNeuronLoss())+" ")
            f.write(str(g._statistics.GetSynapseLoss())+" ")
            f.write(str(g._statistics.GetHardwareEfficiency())+" ")
            f.write(str(biomodelsize)+" ")
            f.write(str(hwmodelsize)+" ")
            f.write(str(setuptime)+" ")
            f.write(str(mappingruntime)+" ")
            f.write("\n")
            f.close()

        if g._fullConnectionMatrixFile is not None:
            g._statistics.writeRawConnectionMatrix(g._fullConnectionMatrixFile ,True,True)
        if g._realizedConnectionMatrixFile is not None:
            g._statistics.writeRawConnectionMatrix(g._realizedConnectionMatrixFile ,True,False)
        if g._lostConnectionMatrixFile is not None:
            g._statistics.writeRawConnectionMatrix(g._lostConnectionMatrixFile ,False,True)

        # collect hardare configuration
        g._configurator.collectConfiguration()
        g._calledRunMapping = True
    else:
        toLog(WARNING,"_run_mapping() already called, but can be called only once.")

 
    
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
    
        if not g._calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")
        if g._calledRunMapping: raise Exception("ERROR: Cannot connect cells after _run_mapping() has been called")
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
                delay = common.build_state_queries(simulator)[2]();
                NoDelayWarning()
    
        synapse = static_synapse_class(weight=weight, delay=delay)
        if isinstance(synapse,StaticSynapse):
            stp_parameters = None
        elif isinstance(synapse,TsodyksMarkramMechanism):
            stp_parameters = TsodyksMarkramMechanism.parameters
        else:
            raise Exception("ERROR: The only short-term synaptic plasticity type supported by the BrainscaleS hardware is TsodyksMarkram!")
    
        g._synapsesChanged = True
        g._connectivityChanged = True
    
#         # Check for proper source cell type:
#         for src in source:
#             if not isinstance(src, simulator.ID): raise errors.ConnectionError("ERROR: Source element %s is not of type ID." %str(src))
#             if type(src.cell) not in supportedNeuronTypes:
#                 if type(src.cell) in [SpikeSourcePoisson, SpikeSourceArray]:
#                     global g._inputChanged
#                     g._inputChanged = True
#                 else: raise errors.ConnectionError("ERROR: Element %d of source is of type: %s. It is neither a supported neuron type nor a spike source." %(src, str(src.cellclass)))
#         # Check for proper target cell type:
#         for tgt in target:
#             if not isinstance(tgt, simulator.ID): raise errors.ConnectionError("ERROR: Target element %s is not of type ID." %str(tgt))
#             if type(tgt.cell) not in supportedNeuronTypes: raise errors.ConnectionError("ERROR: Element %d of target is of type: %s. It is not a supported neuron type." %(src, str(tgt.cellclass)))
#             tgt.cell.checkConductanceRange('weight',weight)

    
        try:
            if sharedParameters:
                newParameterSet = existing_parameter_set or _createSynapseParameterSet(weight, delay, receptor_type, priority, stp_parameters)
            for src in source:
                if p < 1.:
                    if rng: # use the supplied RNG
                        rarr = rng.uniform(0.,1.,len(target))
                    else:   # use the default RNG
                        rarr = g._globalRNG.uniform(0.,1.,len(target))
                for j,tgt in enumerate(target):
                    # evaluate if a connection has to be created
                    if p >= 1. or rarr[j] < p:
                        toLog(DEBUG1, 'Connecting ' + str(src) + ' with ' + str(tgt) + ' and weight ' + str(weight))
                        if not sharedParameters: newParameterSet = _createSynapseParameterSet(weight, delay, receptor_type, priority, stp_parameters)
                        g._preprocessor.BioModelInsertSynapse(src.graphModelNode, tgt.graphModelNode, newParameterSet)

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

reset = common.build_reset(simulator)
    
def build_run(simulator):
    def run(simtime, callbacks=None):
    	"""!
    	Executes the emulation.
    
    	Run the simulation for simtime ms.
    	"""
    
    
    	if not g._calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")
    
    	g._simtime = simtime
    	g._preprocessor.BioModelInsertGlobalParameter("simtime",str(simtime))
    
    
    	# call mapping if not yet called
    	if not g._calledRunMapping:
    	    _run_mapping()
    
    	# update stimulation data configuration
    	# provide the spike times as c++ vectors for every input channel
    	# has to be called AFTER mapping, as it checks whether a PoissonSource
    	# is realized via L2 or via a background event generator
    	if g._inputChanged:
    	    # provide the spike times as c++ vectors for every input channel
    	    for inputID in g._externalInputs:
                assertStimulationSpikeTrain(inputID, regenerate=True)
    	    g._inputChanged = False
    
    	# configure hardware with data from hardware graph
    	g._configurator.configureAll()
    
    	# update change flags
    	g._neuronsChanged = False
    	g._synapsesChanged = False
    	g._connectivityChanged = False
    
    	toLog(INFO, "Configuration data transferred to hardware.")
    
    	# run the prepared experiment
    	g._configurator.setDuration(simtime)
    
    	toLog(INFO, "Starting to send spike trains to hardware.")
    	# set input spike trains
    	for inputID in g._externalInputs:
    	    if g._preprocessor.BioModelStimulusIsExternal(inputID.graphModelNode):
    		g._configurator.sendSpikeTrain(inputID.graphModelNode)
    
    	toLog(INFO, 'Starting experiment execution.')
    	toLog(INFO, 'Experiment iteration: %8d' % g._iteration)
    	#if not g._preprocessor.hardwareAvailable():
    	    #toLog(INFO, "Running pyNN description on a virtual hardware system!")
    	g._configurator.runSimulation()
    
    	g._iteration += 1
    	toLog(INFO, 'Experiment iteration finished.')
    	
    	simulator.state.run(simtime)
    	return simulator.state.t
      
    return run

run = build_run(simulator)
run_for = run

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
    
    g.init()
    g._dt = simulator.state.dt
    # make sure all models are on the same time base
    _set_speedup_factor(g._speedupFactor)   
    
    g._setupstart = time.time()
    
    common.setup(timestep, min_delay, max_delay, **extra_params)
    simulator.state.clear()
    
    # start of specific setup
    
    if extra_params.has_key('hardware'):
        g._hardware_list = extra_params['hardware']
    else:
        g._hardware_list = _default_extra_params['hardware']

    if 'loglevel' in extra_params.keys():
        g._loglevel = extra_params['loglevel']
    else:
        g._loglevel = 1

    if 'logfile' in extra_params.keys():
        g._logfile = extra_params['logfile']
    else: 
        g._logfile = 'logfile.txt'

    global logger
    logger = mapping.createLogger(g._loglevel, g._logfile)

    g._preprocessor = mapping.preprocessor()
    g._mapper = mapping.mapper()
    g._postprocessor = mapping.postprocessor()

    # check for random number generator seed
    if 'rng_seeds' in extra_params.keys():
        g._rng_seeds = extra_params['rng_seeds']
        g._globalRNG.seed(extra_params['rng_seeds'][0])

    # print the available hardware version
    if g._preprocessor.hardwareAvailable():
        toLog(INFO, 'Neuromorphic hardware is of type BrainSales HMF!')
    else:
        toLog(INFO, 'The assumed neuromorphic hardware is of type BrainScales HMF, but a real device is not available!')

    if g._preprocessor.virtualHardwareAvailable():
        toLog(INFO, 'A virtual hardware, i.e. an executable system simulation, is available!')

    # check if system simulation shall be used
    if 'useSystemSim' in extra_params.keys():
        if not isinstance(extra_params['useSystemSim'], bool):
            raise TypeError, 'ERROR: pyNN.setup: argument useSystemSim must be of type bool!'
        g._useSystemSim = extra_params['useSystemSim']
        if not g._preprocessor.virtualHardwareAvailable() and g._useSystemSim : 
            raise Exception("ERROR: Argument 'useSystemSim' of command setup() is set to True, but no virtual hardware is available!")
        if g._useSystemSim :
            toLog(INFO, 'A virtual, i.e. purely simulated hardware system is used instead of a real device!')

    # check if speedup factor of the system is specified by user
    if 'speedupFactor' in extra_params.keys():
        # if yes, we have to scale the parameter ranges of neurons and synapses and update the the global parameter g._speedupFactor
        _set_speedup_factor(extra_params['speedupFactor'])

    _set_trafo_params(extra_params)

    # set all changed-flags to true
    g._neuronsChanged = True
    g._synapsesChanged = True
    g._connectivityChanged = True
    g._inputChanged = True

    # the time step: for membrane traces used as sampling interval, for system simulation as integration time step
    g._dt = timestep
    simulator._dt = timestep
    simulator.state._dt = timestep

    # create containers for input sources
    g._externalInputs = []

    # create temp folder
    _create_temp_folder(extra_params)

    '''
    SETUP THE MAPPING PROCESS 1) HW MODEL
    '''

    _init_preprocessor(extra_params)

    # initialize the mapper
    g._mapper.SetHWModel(g._preprocessor.GetHWModel())
    g._mapper.SetBioModel(g._preprocessor.GetBioModel())
    g._mapper.Initialize()

    # initialize the postprocessor
    g._postprocessor.SetHWModel(g._mapper.GetHWModel())
    g._postprocessor.SetBioModel(g._mapper.GetBioModel())
    g._postprocessor.Initialize()

    _insert_global_hw_params(extra_params)

    # create and initialize the hardware configuration controller
    # if we are using the ESS, the configurator can be initialized only once, as the SystemC kernel can not be reset
    if g._useSystemSim:
        if g._initializedSystemC:
            raise Exception("ERROR: The System Simulation can be started only once per python program. Hence multiple calls of function 'setup()' are not possible.")
        else: g._initializedSystemC = True
    g._configurator = mapping.stage2configurator()

    for hardware in g._hardware_list:
        assert isinstance(hardware, dict)
        if hardware['setup'] == "vertical_setup":
            wafer_id = hardware["wafer_id"]
            g._configurator.setUseVerticalSetup(wafer_id, True);
            # check for IP and number of HICANNs in the jtag chain for vertical setup
            if hardware.has_key('setup_params'):
                vs_params = hardware['setup_params']
                if vs_params.has_key('ip'):
                    g._configurator.setIPv4VerticalSetup(wafer_id, vs_params['ip']);
                if vs_params.has_key('num_hicanns'):
                    g._configurator.setNumHicannsVerticalSetup(wafer_id, vs_params['num_hicanns'])
        else: # wafer
            wafer_id = hardware["wafer_id"]
            g._configurator.setUseVerticalSetup(wafer_id, False);

    g._configurator.init(g._mapper.GetHWModel(), g._mapper.GetBioModel(), g._useSystemSim, g._systemSimTimeStepInPS, g._tempFolder)
    g._configurator.setAcceleration(g._speedupFactor)

    _init_mapping_statistics(extra_params)

    g._calledSetup = True
    
    # end of specific setup
    
    simulator.state.dt = timestep  # move to common.setup?
    simulator.state.min_delay = min_delay
    simulator.state.max_delay = max_delay
    
    return 0

# re format docstring of setup function

setup.__doc__ = setup.__doc__.format(kwargs=_default_args.pprint(indent=8))

def list_standard_models():
    """Return a list of all the StandardCellType classes available for this simulator."""
    standard_cell_types = [obj for obj in globals().values() if isinstance(obj, type) and issubclass(obj, standardmodels.StandardCellType)]
    for cell_class in standard_cell_types:
        try:
            create(cell_class)
        except Exception, e:
            if isinstance(e,ParameterValueOutOfRangeError) or e.__str__() == "ERROR: Call function 'setup(...)' first!":
                pass
            else:
                print "Warning: %s is defined, but produces the following error: %s" % (cell_class.__name__, e)
                standard_cell_types.remove(cell_class)
    return [obj.__name__ for obj in standard_cell_types]

def end(compatible_output=True):
    """Do any necessary cleaning up before exiting."""
    
    # reset the number of neurons created so far
    g._numberOfNeurons = 0
    
    for (population, variables, filename) in simulator.state.write_on_end:
        io = get_io(filename)
        population.write_data(io, variables)
    simulator.state.write_on_end = []
    # should have common implementation of end()
    
    # clear list of place instances
    mapper.placer_list = []
    
    # Destroy the mapping and configuration instances
    if g._postprocessor is not None:
        toLog(INFO, "Erasing GraphModels.")
        g._postprocessor.EraseModels()
    g._preprocessor = None
    g._mapper = None
    g._postprocessor = None
    g._statistics = None
    g._configurator = None
    g._calledSetup = False
    g._calledRunMapping = False
