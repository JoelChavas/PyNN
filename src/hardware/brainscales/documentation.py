# encoding: utf-8
"""
help strings of the hardware.brainscales backend of the PyNN API.

:copyright: Copyright 2006-2013 by the PyNN team, see AUTHORS.
:license: CeCILL, see LICENSE for details.
"""
import os
from .arg_utils import Arg, ArgList, reindent
from copy import deepcopy
from numpy import inf


#========================
# parameters for hardware
#========================

_hardware_setup_params= ArgList(
    Arg("ip", "IP Address (v4) of FPGA of vertical setup as string in dotted decimal form. Only used if setup is a 'vertical_setup'", default="192.168.1.1", dtype=str),
    Arg("num_hicanns", "number of HICANNs in the JTAG chain of vertical setup", default=1, drange=(1,8))
    )

_hardware_args = ArgList(
    Arg("setup", "specifies the type of the hardware", choices=['vertical_setup', 'wafer'], default='wafer', dtype=str),
    Arg("wafer_id", "the logical id of the wafer in the Calibration Database", default=0, dtype=int),
    Arg("hicannIndices", "a list of HICANN Indices (HALBE Enumeration) that shall be used for mapping. If not specified, all HICANNs of the wafer will be used.", dtype=list, default=range(384)),
    Arg("setup_params", """dictionary specifying the parameters of the hardware setup\nparams:\n""" + reindent(_hardware_setup_params.pprint(), 4), dtype=dict),
    )

_mapping_quality_weights = ArgList(
    Arg("G_HW", "weight with which HW efficiency influences the mapping quality", default=0.3, dtype=float),
    Arg("G_PR", "weight with which P & R losses influence the mapping quality", default=0.7, dtype=float),
    Arg("G_T", "weight with which Parameter Transformation distortions influence the mapping quality", default=0.0, dtype=float),
    )

Arg("mappingQualityWeights", """a list of weights for optimization goals.\nWeights are specified in a dictionary with the following values:\n""" + reindent(_mapping_quality_weights.pprint(), 4), default=[{'G_HW':0.3, 'G_PR':0.7, 'G_T':0.0 }], dtype=list),

## default extra_params
_default_args = ArgList(
      Arg("hardware", """a list of hardware setups to be used.\nEach setup is specified by a dictionary with the following parameters:\n""" + reindent(_hardware_args.pprint(), 4), default=[_hardware_args.get_defaults_as_dict()], dtype=list),
      Arg("hicannsMax", "Maximum number of HICANNs that can be used for mapping, if not given, all available HICANNs are considered", drange=(1,inf), default=0, dtype=int),
      Arg("loglevel", "criticality threshold for log messages:\n 0 = ERROR,\n 1 = WARNING,\n 2 = INFO,\n 3 = DEBUG0,\n 4 = DEBUG1,\n 5 = DEBUG2,\n 6 = DEBUG3\n", dtype=int, default=1, drange=(0,6)),
      Arg("logfile", "filename for the logfile.", default="logfile.txt", dtype=str),
      Arg("rng_seeds", "a list of seed values.", default=[0], dtype=list),
      Arg("useSystemSim",
"""specifies if the executable system simulation, i.e. a virtual hardware, shall be
used instead of a real hardware system.""",
        dtype=bool,
        default=False),

      Arg("ess_params", """dictionary containing parameters, that are only considered when using the ESS (useSystemSim=True):
parameters:
    @param perfectSynapseTrafo - Use a perfect synapse transformation, instead of the only available ideal synapse trafo. boolean
    @param weightDistortion    - specifies the distortion of synaptic weights in the virtual hardware system.
                                            This parameters define the fraction of the original value, that is used as
                                            the standard deviation for randomizing the weight according to a normal(Gaussian)
                                            distribution around the original value).
    @param pulseStatisticsFile - name of file, to which the ESS pulse statistics are written""",
    dtype=dict,
    default={}),
        Arg("maxSynapseLoss", "maximum synapse loss allowed during mapping.", default = 0.0, dtype=float, drange=(0.,1.)),
        Arg("maxNeuronLoss", "maximum neuron loss allowed during mapping.", default = 0.0, dtype=float, drange=(0.,1.)),
        Arg("hardwareNeuronSize", "specifies the size of hardware neurons, i.e. the number of neuron circuits that are used to form a larger neuron. The higher this number, the higher is the number of incoming synapses per neuron, and the lower is the total number of neurons", choices=[1,2,4,8,16,32,64], default=1, dtype=int),
        Arg("databaseHost", "provide an IP for the 'calibration' Database", default="127.0.0.1"),
        Arg("databasePort", "provide a port for the 'calibration' Database",  default=27017),
        Arg("ignoreDatabase", "ignore Database for HWModel creation and manual placement", default=False, dtype=bool),
        Arg("interactiveMappingMode","enable the interactive Mapping mode", default=False, dtype=bool),
        Arg("interactiveMappingModeGUI","enable the interactive Mapping mode's GUI", default=False, dtype=bool),
        Arg("experimentName","a name for the experiment to identify it in the mapping log", default='no name', dtype=str),
        Arg("mappingStrategy", "the mapping strategy applied (choose from: {valid,normal,best,user}", default='normal', dtype=str),
        Arg("mappingQualityWeights", """a list of weights for optimization goals.\nWeights are specified in a dictionary with the following values:\n""" + reindent(_mapping_quality_weights.pprint(), 4), default=[{'G_HW':0.2, 'G_PR':0.8, 'G_T':0.0 }], dtype=list),
        Arg("mappingStatisticsFile", "name of a mapping statistics file. If a file name is given then statistics are extracted after mapping from the Bio Model and written to a file.",default=None, dtype=str),
        Arg("fullConnectionMatrixFile", "name of a file, to which the full connection matrix shall be written.\nIf no filename is passed, the connection matrix is not written."),
        Arg("realizedConnectionMatrixFile", """name of a file, to which the realized connection matrix shall be written. 
This connection matrix includes all connections, that where realized during mapping.
If no filename is passed, the connection matrix is not written."""),
        Arg("lostConnectionMatrixFile", """name of a file, to which the lost connection matrix shall be written. This
connection matrix includes all connections, that where lost during mapping.
If no filename is passed, the connection matrix is not written."""),
        Arg("speedupFactor", "specifies the speedup factor of the (virtual) hardware system."),
        Arg("ignoreHWParameterRanges", "ignore the hw parameter ranges when creating the model", default=False, dtype=bool),
        Arg("useSmallCap", "use the small hardware capacitance (500fF instead of 2pF)", default=False, dtype=bool),
        Arg("algoinitFilename", "specifies the filename for the algorithm sequence initialization file (path language).",
            default= os.environ['SYMAP2IC_PATH'] + '/components/mappingtool/script/stage2/algoinit.pl', dtype=str),
        Arg("jsonPathname", "specifies the path for the JSON backup files.", default=os.environ['SYMAP2IC_PATH'] + '/components/mappingtool/script/stage2/JSON/default', dtype=str),
        Arg("tempFolder", """specifies the folder name where all temporary files are stored during ESS simulation.
If not specified a temp folder is created which will be removed by function end().""", dtype=str),
        Arg("programFloatingGates", "option on whether floating gates of hardware are programmed. 'once' is useful when 'run()' is called multiple times afterwards, hence FGs are only programmed once.",
            choices = ['never', 'once', 'always'], default='always'),
        Arg("weightBoost", """allows to boost (i.e. increase) the synaptic weights when using the real hardware. Scales all V_gmax
values (global FloatingGate) by the given factor.""", drange=(0.,5.), dtype=float, default=1.),
        )

_default_extra_params =_default_args.get_defaults_as_dict()

#====================================================
# default extra_params for ESS are slightly different
#====================================================

_default_extra_params_ess = deepcopy(_default_extra_params)
_default_extra_params_ess.update({
    "algoinitFilename" : os.environ['SYMAP2IC_PATH'] + '/components/mappingtool/script/stage2/algoinit_sim.pl',
    "jsonPathname" : os.environ['SYMAP2IC_PATH'] + '/components/mappingtool/script/stage2/JSON/ess',
    }
    )

_default_extra_params_multiwafer = deepcopy(_default_extra_params)
_default_extra_params_multiwafer.update({
    "algoinitFilename" : os.environ['SYMAP2IC_PATH'] + '/components/mappingtool/script/stage2/algoinit_multiwafer.pl',
    "jsonPathname" : os.environ['SYMAP2IC_PATH'] + '/components/mappingtool/script/stage2/JSON/default',
    }
    )