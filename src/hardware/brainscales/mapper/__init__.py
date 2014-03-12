# encoding: utf-8
#
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: Mapping manual placement for the BrainScaleS hardware
#
# ***************************************************************************
#
## @namespace hardware::brainscales:mapper
##
## @short Manual placement module.
##
## @detailed Manually place neurons an the BrainScaleS hardware system


import pyNN.hardware.brainscales
import mapping

from mapping_analyzer import MappingAnalyzer

## list of place instances
## place instances are appended to this list, when created
## before mapping is started, it is checked whether all instances have been commited
## is cleared everytime when simulator.end() is called
placer_list = []

class place(object):
    """!
    Constrains on manual placement
    """
    instances = []
    _filepath = 'NeuronPlacement.mpf'
    header = "# BrainScaleS Manual Placement File\n# Line-wise format:\n# [PyNN-cell-ID wafer hicann neuron]\n"

    def __init__(self):
        """!
        ...
        """
        self._occupied_slots = []
        self._mapped_neurons = []
        self._mapping_list = []
        self.committed = False
        placer_list.append(self)

    def __del__(self):
        # delete self from instances list
        try:
            placer_list.remove(self)
        except:
            pass

    def to(self, element, wafer=0, hicann=None, neuron=None):
        '''!
        manually setting the destination for an element (circumvents automatic placing)
        @param element - The PyNN element to be placed: pyNN cell, e.g. a neuron or a spike source
        @param wafer   - the wafer ID, to which the neuron is placed
        @param hicann  - the hicann ID (new coordinate system, global enumeration scheme), to which the neuron is placed on the wafer
        @param neuron  - the abstract neuron number within the HICANN. This corresponds to the denmem for the case that HardwareNeuronSize=1.
        '''
        assert(type(element) is pyNN.hardware.brainscales.ID), "Wrong type of element. 'element' must be of type(pyNN.hardware.brainscales.ID)"
        assert(int(wafer) >= 0)
        assert(int(hicann) >= 0)
        assert(int(neuron) >= 0)
        pyNN.hardware.brainscales.toLog(mapping.DEBUG0, 'Manual placing of '+str(element)+' to Wafer '+str(wafer)+', Hicann '+str(hicann)+', Neuron '+str(neuron))
        #    (element, wafer, hicann, neuron)
        if  element in self._mapped_neurons:
            raise Exception("ERROR: Neuron %s already placed on another slot." % element )
        if  (wafer, hicann, neuron) in self._occupied_slots :
            raise Exception("ERROR: Cannot place Neuron %s to Wafer %s, Hicann %s, Neuron %s. Slot already occupied" % \
            (element, wafer, hicann, neuron))
        if (int(element) < 0) and not isinstance(element.cell, pyNN.hardware.brainscales.SpikeSourcePoisson):
            raise Exception("ERROR: cannot place spike sources other than SpikeSourcePoisson. Your cellclass is %s"  % type(element.cell) )
        self._mapped_neurons.append(element)
        self._occupied_slots.append( (wafer, hicann, neuron) )
        self._mapping_list.append( (int(element), wafer, hicann, neuron) )

    def commit(self, filename=None):
        """!
        @param filename file to write the manual placement to

        Stream the manual placement to a file
        """
        if filename is not None:
            self._filepath = filename

        import os
        from numpy import savetxt
        pyNN.hardware.brainscales.toLog(mapping.INFO, 'Writing manual placement sequence to '+os.path.abspath(self._filepath))
        with open(self._filepath, 'w') as f:
            f.write(place.header)
            savetxt(f,self._mapping_list,fmt="%d")
        self.committed = True
