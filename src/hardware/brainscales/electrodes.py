# encoding: utf-8
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: PyNN Current stimulus classes
#
# ***************************************************************************
#
## @namespace hardware::brainscales::electrodes
#
## @short Interface classes for current stimulus.
##
## @detailed ...

import pyNN.hardware.brainscales
from pyNN.common import Population, PopulationView, Assembly

# size of the controller memory that is used for playback
# (number of available values per period)
FG_MEM_SIZE = 129

#  Cycle of the slow Hicann clock in seconds. This assumes the HICANN is using a PLL of 100 MHz.
SLOW_CLOCK = 4.e-8

# returns allowed period lengths for the playback clock, in biological
# time. Can be calculated using the clock speed(16 ns) and the pulselength
# parameter (HICANN documentation, figure: floating gate control
# instructions)
# pulselength =  range(16)
# = FG_MEM_SIZE*s_to_ms_conversion*slow_clock*speedup*(pulselength+1)
def FG_ALLOWED_PERIODS(speedup=10000.):
    return [FG_MEM_SIZE*1.e3*SLOW_CLOCK*speedup*(pulselength + 1) for pulselength in range(16) ]


class PeriodicCurrentSource(object):
    """!

    A periodic current source.

    A periodic current source that repeatedly plays back a set of
    current values. The period length can take on a set of values
    given in PeriodicCurrentSource.ALLOWED_PERIODS.

    """

    MEM_SIZE = FG_MEM_SIZE
    ALLOWED_PERIODS = FG_ALLOWED_PERIODS()

    def __init__(self, value_list, period=None):
        """!

        Initialize the PeriodicCurrentSource.

        @param value_list  - list of current amplitudes in nA.
        @param period      - duration of a single period, in ms.

        """
        if period is None:
            period = self.ALLOWED_PERIODS[-1]
        if len(value_list) != self.MEM_SIZE:
            raise ValueError("value_list must have the length of PeriodicStepSource.MEM_SIZE")
        if period not in self.ALLOWED_PERIODS:
            raise ValueError("period length of {0} not allowed. Possible values are {1}".format(period, self.ALLOWED_PERIODS))
        self._period = period
        self._values = value_list
        self._node = pyNN.hardware.brainscales._createCurrentSource()
        parameters = {'value_list':self._values, 'period':period, 'classname':self.__class__.__name__}
        self._param_node = pyNN.hardware.brainscales._createCurrentSourceParameterSet(parameters)
        pyNN.hardware.brainscales._preprocessor.BioModelAssignElementToParameterSet(self._node,self._param_node)

    def inject_into(self, cell_list):
        """!
        Inject the current into a list of cells.

        @param cell_list   - list of cells into which the current is
                             injected. Can be a Population,
                             PopulationView, Assembly or iterable
                             container of IDs.
        """
        for id in cell_list:
            if id.local and not id.celltype.injectable:
                raise TypeError("Can't inject current into a spike source.")
        if isinstance(cell_list, (Population, PopulationView, Assembly)):
            cell_list = [cell for cell in cell_list]
        for tgt in cell_list:
            pyNN.hardware.brainscales._preprocessor.BioModelInsertCurrentInjection(self._node, tgt.graphModelNode)



class DCSource(PeriodicCurrentSource):
    """!

    A source of constant current.

    """

    def __init__(self, amplitude=1.0, start=0.0, stop=None):
        """!

        Initialize the DCSource.

        @param amplitude    - amplitude of the constant current source, in nA.
        @param start - start time in miliseconds, not implementable on the hardware
        @param stop - end time in miliseconds, not implementable on the hardware
        
        ATTENTION: Setting the start and stop values is not supported and will be ignored.
        """
        if start != 0.0:
            raise ValueError("A start time different from 0 is not implemented in the hardware.")
        if stop != None:
            raise ValueError("stop value is not implemented in the hardware.")

        super(DCSource, self).__init__(
            [amplitude for i in range(PeriodicCurrentSource.MEM_SIZE)])


class StepCurrentSource(object):
    """!

    A step current source, aka, "rectangle".

    Currently not implemented.
    """

    MEM_SIZE = FG_MEM_SIZE
    MAXIMAL_LENGTH = max(FG_ALLOWED_PERIODS())


    def __init__(self, times, amplitudes):
        """!

        @param times ...
        @param amplitudes ...

        """
        if min(times) < 0. or max(times) > self.MAXIMAL_LENGTH:
            raise ValueError("Current change times must lie between {0} and {1}".format(0, self.MAXIMAL_LENGTH))
        # TODO: Send warning when change times do not correspond to an integer
        #       multiple of the clock cycle

        assert False, "not implemented"

    def inject_into(self, cell_list):
        """!
        Inject the current into a list of cells.

        @param cell_list   - list of cells into which the current is
                             injected. Can be a Population,
                             PopulationView, Assembly or iterable
                             container of IDs.
        """
        # TODO
        assert False, "not implemented"
