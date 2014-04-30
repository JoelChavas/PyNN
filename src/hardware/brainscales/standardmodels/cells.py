# encoding: utf-8
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: PyNN Standard cell classes
#
# ***************************************************************************
#
## @namespace hardware::brainscales::cells
#
## @short Standard cell classes.
##
## @detailed Defines an implementation of the PyNN API for the BrainScaleS neuromorphic hardware systems.

from pyNN import common
from pyNN.standardmodels import cells, build_translations
from ..simulator import state
from ..range_checker import *

## nS
BIG_HW_CAP = 0.0026
## nS
SMALL_HW_CAP = 0.0004
## ...
supportedNeuronTypes = []

class EIF_cond_exp_isfa_ista(cells.EIF_cond_exp_isfa_ista, HardwareNeuronRangeChecker):
    __doc__ = cells.EIF_cond_exp_isfa_ista.__doc__

    translations = build_translations(
        ('cm'        , 'cm'),
        ('tau_refrac', 'tau_refrac'),
        ('v_spike'   , 'v_spike'),
        ('v_reset'   , 'v_reset'),
        ('v_rest'    , 'v_rest'),
        ('tau_m'     , 'g_l', "cm/tau_m*1000.0", "cm/g_l*1000."),
        ('i_offset'  , 'i_offset'),
        ('a'         , 'a'),
        ('b'         , 'b'),
        ('delta_T'   , 'delta_T'),
        ('tau_w'     , 'tau_w'),
        ('v_thresh'  , 'v_thresh'),
        ('e_rev_E'   , 'e_rev_E'),
        ('tau_syn_E' , 'tau_syn_E'),
        ('e_rev_I'   , 'e_rev_I'),
        ('tau_syn_I' , 'tau_syn_I'),
    )
    _speedupFactor = 10000. # speedup factor for which the current parameter ranges are valid
    parameter_ranges = {
        'cm'        : (  0.2,   0.2), # nF
        'tau_refrac': (    0,   10.), # ms
        'v_spike'   : (-100.,    0.), # mV
        'v_reset'   : (-100.,    0.), # mV
        'v_rest'    : ( -50.,  -50.), # mV (fixed)
        'tau_m'     : (   9.,  110.001), # mV
        'i_offset'  : (   0.,    0.),
        'a'         : (   0.,  0.13), # nS (for the case that cm = c_hw = 2.6 pF), changed from (0.01,0.1) to allow bigger range.
                                      # chosen such that upper limit 10 nS for cm=0.2 nF
                                      # 10 = x*0.2/0.0026 => x = 10*0.0026/0.2 = 0.13
        'b'         : (   0., 0.086), # nA
        'delta_T'   : (  0.0,    3.), # mV  changed from (0.4,3.), # mV to allow 0.
        'tau_w'     : (  20.,  780.), # ms
        'v_thresh'  : (-100.,    0.), # mV
        'e_rev_E'   : (   0.,    0.), # mV (fixed)
        'tau_syn_E' : (  0.5,    5.), # ms
        'e_rev_I'   : (-100., -100.), # mV (fixed)
        'tau_syn_I' : (  0.5,    5.), # ms
        'weight'     :(   0.,   0.3), # uS
    }

    recordable = ['spikes', 'v']

    # hardware capacitance of HICANN
    #c_hw = 0.0026 # nS (big
    c_hw = BIG_HW_CAP

    def __init__(self,parameters):
        cells.EIF_cond_exp_isfa_ista.__init__(self,parameters)
        checked_params = self.reverse_translate(self.parameters)
        self.checkParameterRanges(checked_params)

    def checkParameterRanges(self, parameters):
        """!
        Method derived from HardwareRangeChecker.

        Checks if the parameters are within the range supported by the hardware.
        As the conductance 'a' requires a special treatment, we override this method
        """
        # check parameter ranges
        for (key,value) in parameters.iteritems():
            # conductances need a special treatment
            if key == 'a':
                self.checkConductanceRange(key,value, cm = parameters['cm'] or None)
            else:
                check_parameter_range(key,value,self.parameter_ranges[key])

supportedNeuronTypes.append(EIF_cond_exp_isfa_ista)


class IF_cond_exp(cells.IF_cond_exp, HardwareNeuronRangeChecker):
    __doc__ = cells.IF_cond_exp.__doc__

    translations = build_translations(
        ('v_rest',     'v_rest')    ,
        ('v_reset',    'v_reset'),
        ('cm',         'cm'),
        ('tau_m',      'g_l', "cm/tau_m*1000.0", "cm/g_l*1000.0"),
        ('tau_refrac', 'tau_refrac'),
        ('tau_syn_E',  'tau_syn_E'),
        ('tau_syn_I',  'tau_syn_I'),
        ('v_thresh',   'v_thresh'),
        ('i_offset',   'i_offset'),
        ('e_rev_E',    'e_rev_E'),
        ('e_rev_I',    'e_rev_I'),
    )
    _speedupFactor = 10000. # speedup factor for which the current parameter ranges are valid
    parameter_ranges = {
        'cm'        : (  0.2,   0.2), # nF
        'tau_refrac': (    0,   10.), # ms
        'v_reset'   : (-100.,    0.), # mV
        'v_rest'    : ( -50.,  -50.), # mV (fixed)
        'tau_m'     : (   9.,  110.001), # mV
        'i_offset'  : (   0.,    0.),
        'v_thresh'  : (-100.,    0.), # mV
        'e_rev_E'   : (   0.,    0.), # mV (fixed)
        'tau_syn_E' : (  0.5,    5.), # ms
        'e_rev_I'   : (-100., -100.), # mV (fixed)
        'tau_syn_I' : (  0.5,    5.), # ms
        'weight'     :(   0.,   0.3), # uS
    }

    recordable = ['spikes', 'v']
    # hardware capacitance of HICANN
    c_hw = BIG_HW_CAP

    def __init__(self,**parameters):
        super(IF_cond_exp, self).__init__(**parameters)
        self.parameter_space.shape = (1,)
        self.parameter_space.evaluate(simplify=True)
        self.checkParameterRanges(self.parameter_space.as_dict())

supportedNeuronTypes.append(IF_cond_exp)


class SpikeSourcePoisson(cells.SpikeSourcePoisson, HardwareRangeChecker):
    __doc__ = cells.SpikeSourcePoisson.__doc__

    translations = build_translations(
        ('rate',      'rate'),
        ('start',     'start'),
        ('duration',  'duration')
    )
    _speedupFactor = 10000. # speedup factor for which the current parameter ranges are valid
    parameter_ranges = {
            'rate':(0.,2084.), # Maximum throuput DNC->HICANN connection at speedup 10^4
            'start':(0.,float('inf')),
            'duration': (0.,float('inf'))
            }
    recordable = ['spikes']

    def __init__(self,**parameters):
        random = True
        if parameters is not None:
            params = parameters.copy()
            if parameters.has_key('random'):
                if not isinstance( parameters['random'], bool):
                    raise TypeError, 'ERROR: pyNN.hardware.brainscales.SpikeSourcePoisson: parameter random must be of type bool!'
                random = parameters['random']
                params.pop('random')
        else:
            params = {}
        self.index = None
        self.hardwareSpikeTimes = None
        cells.SpikeSourcePoisson.__init__(self,**params)
        checked_params = self.reverse_translate(self.parameter_space)
        checked_params.shape=(1,)
        checked_params.evaluate(simplify=True)
        self.checkParameterRanges(checked_params.as_dict())
        self.parameter_space.schema['random'] = type(int(0))
        self.parameter_space.update(random=int(random))
        self.parameter_space.shape=(1,)
        self.parameter_space.evaluate(simplify=True)


class SpikeSourceArray(cells.SpikeSourceArray, HardwareRangeChecker):
    __doc__ = cells.SpikeSourceArray.__doc__
    __name__ = "SpikeSourceArray"

    translations = build_translations(
        ('spike_times', 'spike_times')
    )
    recordable = ['spikes']
    _speedupFactor = 10000. # speedup factor for which the current parameter ranges are valid
    parameter_ranges = {}

    def __init__(self,**parameters):
        self.index = None
        self.hardwareSpikeTimes = None
        super(SpikeSourceArray, self).__init__(**parameters)
        self.checkParameterRanges(self.parameter_space._parameters)
        
    def checkParameterRanges(self, parameters):
        """!

        Method derived from HardwareRangeChecker.

        Additionally checks if the parameters are within the range supported by the hardware.
        This happens before the conversion into native parameters.

        """
        # currently no range restriction for SpikeSourceArrays (could check for the mean rate of the spiketrains)
        pass
