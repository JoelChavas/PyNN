# encoding: utf-8
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: PyNN hardware specific parameter range checking
#
# ***************************************************************************
#
## @namespace hardware::brainscales::range_checker
#
## @short Parameter Range checking classes and utilities.
##
## @detailed ...

import pyNN.hardware.brainscales

## if True: it is not checked if the biological parameters given fit within the hw parameter ranges 
_ignoreHWParameterRanges = False

class ParameterValueOutOfRangeError(Exception):
    """!
    
    Passed Parameter Value is out of the range supported by the FACETS Hardware.
    
    """
    def __init__(self, parameter_name, parameter_value, valid_parameter_range):
        """!
    
        @param parameter_name
        @param parameter_value 
        @param valid_parameter_range - allowed parameter range

        """
        Exception.__init__(self)
        self.parameter_name = parameter_name
        self.parameter_value = parameter_value
        self.valid_parameter_range = valid_parameter_range

    def __str__(self):
        """!

        Returns a string representation used by logging.
    
        """

        return "%s is out of the range supported by the hardware( valid range for parameter %s is: %s)" % ( self.parameter_value,
                                                         self.parameter_name,
                                                         self.valid_parameter_range)

class IgnoreParameterRangeWarning():
    """!
    Gives a Warning that hw parameter ranges will be ignored.
    """
    warning_called = False
    def __init__(self):
        if not IgnoreParameterRangeWarning.warning_called:
            pyNN.hardware.brainscales.toLog(pyNN.hardware.brainscales.WARNING,"HW parameter ranges will be ignored!")
            IgnoreParameterRangeWarning.warning_called = True

def check_parameter_range(name, value, range):
    """!
    
    Checks wether a parameter value lies within in a certain range.
    
    If it is not within this range a ParameterValueOutOfRangeError is raised.
    
    """

    if _ignoreHWParameterRanges == True :
        IgnoreParameterRangeWarning()
    else :
        if range[0] <= value <= range[1]:
            pass
        else:
            raise ParameterValueOutOfRangeError(name,value,range)

class HardwareRangeChecker(object):
    """!
    
    Comparing parameters to be within HW ranges.
    
    Base class, that provides methods for comparing the supplied 
    parameters with the ranges available in the hardware.

    Note: Requires the derived class to have member 'parameter_ranges'.
    """

    def checkParameterRanges(self, parameters):
        """!
        
        Checks if the parameters are within the range supported by the hardware.
        
        @param parameters ...
        
        The ranges have to be defined in the derived class with name "parameter_ranges"
        """

        # check parameter ranges
        for key in parameters:
            check_parameter_range(key,parameters[key],self.parameter_ranges[key])

    @classmethod
    def scaleParameterRangesTime(cls, new_speedup):
        """!
        
        Scales the parameter ranges, such that they correspond to the chosen speedup factor.

        @param new_speedup - the new speedup factor, for which the new parameter ranges shall be calculated.
        
        Note: should be called only from pyNN.setup() when the speedupFactor is supported.
         
        """
        new_over_old_acc = new_speedup*1./cls._speedupFactor
        cls._speedupFactor = new_speedup

        # the following implementation is a bit hack-ish
        # as the transformation factor is defined here for all variables
        # and is not model dependent.
        # variables that don't change, such as voltages, are not transformed
        transform_factor = {
            'tau_refrac': new_over_old_acc,
            'tau_m'     : new_over_old_acc,
            'i_offset'  : 1./new_over_old_acc,
            'a'         : 1./new_over_old_acc,
            'b'         : 1./new_over_old_acc,
            'tau_w'     : new_over_old_acc,
            'tau_syn_E' : new_over_old_acc,
            'tau_syn_I' : new_over_old_acc,
            'weight'    :1./new_over_old_acc,
            'rate'      :1./new_over_old_acc,
            'tau_rec'   : new_over_old_acc,
            'tau_facil' : new_over_old_acc,
        }
        for (key,limits) in cls.parameter_ranges.items():
            if transform_factor.has_key(key):
                factor = transform_factor[key]
                cls.parameter_ranges[key] = (limits[0]*factor, limits[1]*factor)

    @classmethod
    def scaleParameterRangesCap(cls, new_cap, old_cap):
        """!
        
        scales the parameter ranges, such that they correspond to the chosen hardware capacitance.
        
        @param new_cap - the new hardware capacitance, for which the new parameter ranges shall be calculated.
        @param old_cap - the old hardware capacitance, for which the current parameter ranges are valid.
        
        Note: should be called only from pyNN.setup() when the useSmallCap is true.
        
        """
        new_over_old_cap = new_cap*1./old_cap
        cls.cm_hw = new_cap
        # the following implementation is a bit hack-ish
        # as the transformation factor is defined here for all variables
        # and is not model dependent.
        # variables that don't change, such as voltages, are not transformed
        transform_factor = {
            'tau_m'     : new_over_old_cap,
            'i_offset'  : 1./new_over_old_cap,
            'a'         : 1./new_over_old_cap,
            'b'         : 1./new_over_old_cap,
            'weight'    :1./new_over_old_cap,
        }
        for (key,limits) in cls.parameter_ranges.items():
            if transform_factor.has_key(key):
                factor = transform_factor[key]
                cls.parameter_ranges[key] = (limits[0]*factor, limits[1]*factor)


class HardwareNeuronRangeChecker(HardwareRangeChecker):
    """!
    
    Specialization of HardwareRangeChecker for Hardware Neurons.
    
    Provides a method for checking the conductance range, 
    which is needed e.g. to check whether synaptic weights 
    are realizable in Hardware.

    requires the derived class to have a member 'c_hw'

    """

    def checkConductanceRange(self, key, value, cm = None):
        """!
        
        Checks wether a given conductance (either adaptation variable 'a' or 
        a synaptic weight 'w') is within the supported range defined in 
        dictionary parameter_ranges.
        
        The supported range depends on the ratio of the membrane 
        capacitance 'cm' and the hardware capacitance c_hw.

        @param key  - the key for the parameter to be checked
        @param value  - the value for the parameter to be checked
        
        This method exists only in the module "hardware.facets/brainscales" and 
        not in other backends.
        
        """
        new_limits = self.getConductanceRange(key, cm)
        check_parameter_range(key,value,new_limits)

    def getConductanceRange(self, key, cm = None):
        """!
        
        Returns the supported conductance range (either adaptation 
        variable 'a' or a synaptic weight 'w').
        
        The supported range depends on the ratio of the membrane 
        capacitance 'cm' and the hardware capacitance c_hw.

        This method exists only in the module "hardware.facets/brainscales" and 
        not in other backends.
        
        """
        if not cm:
            cm = self.reverse_translate(self.parameters)['cm']
        cap_ratio = cm/self.c_hw
        limits = self.parameter_ranges[key]
        return  (limits[0]*cap_ratio,limits[1]*cap_ratio)
