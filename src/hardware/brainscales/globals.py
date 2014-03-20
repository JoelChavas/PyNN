from pyNN.random import NumpyRNG

def init():
    global _logfile
    global _loglevel
    global _hardware_list
    global _globalRNG
    global _calledSetup
    global _useSystemSim
    global _initializedSystemC
    global _runSystemC
    global _preprocessor
    global _mapper
    global _postprocessor
    global _statistics
    global _configurator
    global _numberOfNeurons
    global _numberOfNeuronParameterSets
    global _numberOfCurrentSourceParameterSets
    global _numberOfCurrentSources
    global _numberOfSynapseParameterSets
    global _neuronsChanged
    global _synapsesChanged
    global _connectivityChanged
    global _inputChanged
    global _calledRunMapping
    global _iteration
    global _externalInputs
    global _speedupFactor
    global _useSmallCap
    global _rng_seeds
    global _dt
    global _simtime
    global _interactiveMappingMode
    global _interactiveMappingModeGUI
    global _experimentName
    global _mappingStrategy
    global _mapping_quality_weights
    global _systemSimTimeStepInPS
    global _mappingStatisticsFile
    global _statistics
    global _fullConnectionMatrixFile
    global _realizedConnectionMatrixFile
    global _lostConnectionMatrixFile
    global _tempFolder
    global _deltempFolder
    global _setupstart

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
    _dt = 0.
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
