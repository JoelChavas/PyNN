# encoding: utf-8
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: PyNN hardware specific synapse dynamics
#
# ***************************************************************************
#
## @namespace hardware::brainscales::synapses
#
## @short Synapse dynamics.
##
## @detailed ...

from pyNN import common
from pyNN.standardmodels import synapses, build_translations
import numpy
from pyNN.random import RandomDistribution, NativeRNG
from math import *
import types
from ..range_checker import HardwareRangeChecker
import pyNN.hardware.brainscales
from ..simulator import state

class STDPMechanism(synapses.STDPMechanism):
    __doc__ = synapses.STDPMechanism.__doc__
    
    def __init__(self, timing_dependence=None, weight_dependence=None,
                 voltage_dependence=None, dendritic_delay_fraction=0.0):
        """!
        ...
        """
        if not timing_dependence is SpikePairRule:
            pyNN.hardware.brainscales.toLog(pyNN.hardware.brainscales.ERROR, "Setting timing_dependence != SpikePairRule isn't support on FACETS hardware.")
            raise Exception("Setting timing_dependence != SpikePairRule isn't support on FACETS hardware.")
        if not voltage_dependence is None:
            pyNN.hardware.brainscales.toLog(pyNN.hardware.brainscales.ERROR, "Voltage dependent STDP isn't supported on FACETS hardware.")
            raise Exception("Voltage dependent STDP isn't supported on FACETS hardware.")
        if not dendritic_delay_fraction == 0.0:
            pyNN.hardware.brainscales.toLog(pyNN.hardware.brainscales.ERROR, "Setting a dendritic_delay_fraction != 0.0 isn't supported on FACETS hardware.")
            raise Exception("Setting a dendritic_delay_fraction != 0.0 isn't supported on FACETS hardware.")
        self.timing_dependence = timing_dependence
        self.weight_dependence = weight_dependence
        self.voltage_dependence = None
        self.dendritic_delay_fraction = 0.0

class StaticSynapse(synapses.StaticSynapse):
    __doc__ = synapses.StaticSynapse.__doc__
    translations = build_translations(
        ('weight', 'WEIGHT'),
        ('delay', 'DELAY'),
    )

    def _get_minimum_delay(self):
        return state.min_delay

class TsodyksMarkramMechanism(synapses.TsodyksMarkramSynapse, HardwareRangeChecker):
    __doc__ = synapses.TsodyksMarkramSynapse.__doc__


    translations = build_translations(
        ('U', 'U'),
        ('tau_rec', 'tau_rec'),
        ('tau_facil', 'tau_facil'),
        ('u0', 'u0'),
        ('x0', 'x0' ),
        ('y0', 'y0')
    )

    _speedupFactor = 10000. # speedup factor for which the current parameter ranges are valid
    parameter_ranges = {
        'U': (0.1,0.5), # TODO(BV): Limit to the the maximum U in hardware ?
        'tau_rec': (50.,200.), # ms
        'tau_facil': (50.,200.), # ms
        'u0': (0.,0.),
        'x0': (1.,1.),
        'y0': (0.,0.)
        }

    def __init__(self, U=0.5, tau_rec=100.0, tau_facil=0.0, u0=0.0, x0=1.0, y0=0.0):
        """!
        ...
        """
        parameters = dict(locals()) # need the dict to get a copy of locals. When running
        parameters.pop('self')      # through coverage.py, for some reason, the pop() doesn't have any effect
        
        #TsodyksMarkramMechanism.__init__(self, U, tau_rec, tau_facil, u0, x0, y0)   # DB: check this!
        assert ( u0==0.0 and  x0==1.0 and y0==0.0), "It is not possible to set u0, x0, y0 in the Hardware."
        #store global parameter_ranges temporarily
        original_parameter_ranges = self.parameter_ranges.copy()
        # exactly one of the 2 time-constant has to be non-zero
        if ( tau_facil > 0. and tau_rec > 0.):
            raise Exception("ERROR: The Short-Term Plasticity Mechanism of the Hardare currently only supports 1 time-constant. You have to set one of the two parameters 'tau_rec' and 'tau_fac' to 0.")
        elif ( tau_facil > 0. ):
            self.parameter_ranges[ 'tau_rec' ] = (0.,0.)
        else:
            self.parameter_ranges[ 'tau_facil' ] = (0.,0.)
        # (the case when both are zero will tracked at the parameter-range check
        self.parameters = self.translate(parameters)
        checked_params = self.reverse_translate(self.parameters)
        self.checkParameterRanges(checked_params)

        # reset original values for creation of the next dynamics
        self.parameter_ranges.update(original_parameter_ranges)


class AdditiveWeightDependence(synapses.AdditiveWeightDependence):
    __doc__ = synapses.AdditiveWeightDependence.__doc__

    default_parameters = {
        'w_min':   0.0,
        'w_max':   1.0,
        'A_plus':  1.0/16,
        'A_minus': 1.0/16
    }
    possible_models = set([])

    def __init__(self, w_min=0.0, w_max=1.0, A_plus=1.0/16, A_minus=1.0/16): # units?
        """!
        ...
        """
        pyNN.hardware.brainscales.toLog(pyNN.hardware.brainscales.ERROR, "AdditiveWeightDependence not yet implemented!")
        print "TODO AdditiveWeightDependence() (ECM)"
        raise Exception("AdditiveWeightDependence not yet implemented!")
        pass


class MultiplicativeWeightDependence(synapses.MultiplicativeWeightDependence):
    __doc__ = synapses.MultiplicativeWeightDependence.__doc__

    default_parameters = {
        'w_min':   0.0,
        'w_max':   1.0,
        'A_plus':  1.0/16,
        'A_minus': 1.0/16
    }
    possible_models = set([])

    def __init__(self, w_min=0.0, w_max=1.0, A_plus=1.0/16, A_minus=1.0/16): # units?
        """!
        ...
        """
        pyNN.hardware.brainscales.toLog(pyNN.hardware.brainscales.ERROR, "MultiplicativeWeightDependence not yet implemented!")
        print "TODO MultiplicativeWeightDependence() (ECM)"
        raise Exception("MultiplicativeWeightDependence not yet implemented!")
        pass


class SpikePairRule(synapses.SpikePairRule):
    __doc__ = synapses.SpikePairRule.__doc__

    default_parameters = {
        'tau_plus':  20.0,
        'tau_minus': 20.0,
    }

    def __init__(self, tau_plus=20.0, tau_minus=20.0):
        """!
        ...
        """
        pyNN.hardware.brainscales.toLog(pyNN.hardware.brainscales.ERROR, "SpikePairRule not yet implemented!")
        print "SpikePairRule not yet implemented! (TODO: ECM)"
        raise Exception("SpikePairRule not yet implemented!")
        pass

