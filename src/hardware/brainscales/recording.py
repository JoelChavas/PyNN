# encoding: utf-8
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: PyNN hardware specific recording classes
#
# ***************************************************************************
#
## @namespace hardware::brainscales::recording
#
## @short Recording classes and and utilities.
##
## @detailed ...

import numpy
from pyNN import recording, errors
from . import globals as g
from . import simulator
import pyNN.hardware.brainscales


# --- For implementation of record_X()/get_X()/print_X() -----------------------

class Recorder(recording.Recorder):
    """!

    Encapsulates data and functions related to recording model variables.

    """
    _simulator = simulator
    formats = {'spikes': 'id t',
               'v': 'id t v',
               'gsyn': 'id t ge gi',
               'generic': 'id t variable'}
    map_variable_record_params = {
        'spikes': {'record':'record_spikes', 'filename':'record_spikes_filename'},
        'v': {'record':'record_membrane', 'filename':'record_membrane_filename'},
        }

    def _record(self, variable, new_ids):
        """!

        Add the cells in `new_ids` to the set of recorded cells.

        @param new_ids
        """
        self.variable = variable
        if g._calledRunMapping: raise Exception("ERROR: Cannot add recording after _run_mapping() has been called")
        record_params = {}
        if variable == 'spikes':
            record_params = Recorder.map_variable_record_params['spikes']
        elif variable == 'v':
            record_params = Recorder.map_variable_record_params['v']
        else:
            raise NotSupportedError("pyNN.hardware.brainscales can only record spikes and some membrane voltages, not %s" % self.variable)

        # check if all sources share the same parameter set. If yes, cloning of parameter set is not necessary.
        considerCloningNecessary = False
        tempGraphModelNodeParams = None
        for id in new_ids:
            if not isinstance(id, pyNN.hardware.brainscales.ID): raise Exception("ERROR: Source element %s is not of type ID." %str(id))
            #if type(id.cell) not in supportedNeuronTypes:  raise Exception("ERROR: Can only record neurons, not external spike sources!")
            if not tempGraphModelNodeParams:
                tempGraphModelNodeParams = id.graphModelNodeParams
            elif id.graphModelNodeParams is not tempGraphModelNodeParams:
                considerCloningNecessary = True

        # if we we recorde voltage, we have to clone the parameterset, as there will be an individual filename for each neuron
        if variable == 'v':
            considerCloningNecessary = True
            vm_file_base_name = g._tempFolder

        # now actually set the new parameters to the already existing or to a cloned parameter set
        # if all cells in list share the same original parameter set, cloning this set once is enough
        cellCount = 0
        updatedParameterSet = None
        for id in new_ids:
            # if new values differ from old ones, first cell needs to be cloned in all cases
            # if cells have different parameter sets, cloning is considered for every individual cell
            if cellCount==0 or considerCloningNecessary:
                # for multiple new parameter values, cloning a parameter set once is enough
                hasBeenCloned = False
                # if parameter set needs to be cloned, it is enough to do this only once
                if variable == 'spikes':
                    id.graphModelNodeParams = g._preprocessor.BioModelSetParameter(id.graphModelNode, record_params['record'], "1", True)
                    updatedParameterSet = g._preprocessor.BioModelSetParameter(id.graphModelNode, record_params['filename'], str(self.file), False)
                elif variable == 'v':
                    vm_filename = vm_file_base_name + "/vm_" + str(int(id)).zfill(5) + ".tmp"
                    id.graphModelNodeParams = g._preprocessor.BioModelSetParameter(id.graphModelNode, record_params['record'], "1", True)
                    updatedParameterSet = g._preprocessor.BioModelSetParameter(id.graphModelNode, record_params['filename'], vm_filename, False)
            else:
                g._preprocessor.BioModelAssignElementToParameterSet(id.graphModelNode,updatedParameterSet)
            # update pyNN-internal mapping of IDs to their parameter sets
            id.graphModelNodeParams = updatedParameterSet
            cellCount +=1

    def _reset(self):
        """!
        Resets the state of the Recorder.
        Not implementable on the BrainScaleS hardware.
        """
        raise NotImplementedError("Recording reset is not currently supported for pyNN.hardware.brainscales")

    def _get_spikes(self, id):
	if (id < 0 and g._preprocessor.BioModelStimulusIsExternal(id.graphModelNode)):
	    spiketrain = g._postprocessor.BioModelReceiveRecordedSpikes(id.graphModelNode)
	    # for stage2 real neurons and stimuli mapped onto background generators we receive the spikes via the configurator
	else:
	    spiketrain = g._configurator.receiveSpikeTrain(id.graphModelNode) 
	return numpy.array(spiketrain)

    def _get_spiketimes(self, id):
        spikes = self._get_spikes(id)
        if len(spikes) > 0:
            data = spikes
        else:
            data = numpy.empty((0))
        return data

    def _get_all_signals(self, variable, ids, clear=False):
        """!

        Return the recorded data as a Numpy array.

        """
        
        if variable == 'spikes':
            if len(ids) > 0:
                data = numpy.vstack([self._get_spikes(id) for id in ids]).T
            else:
                data = numpy.array([])
        elif variable == 'v':
            if len(ids) > 0:
                data = numpy.vstack([numpy.array(g._configurator.receiveVoltageTrace(id.graphModelNode)) for id in ids]).T
            else:
                data = numpy.array([])
        else:
            raise Exception("Recording of %s not implemented." % self.variable)
        #if gather and simulator.state.num_processes > 1:
        #    data = recording.gather(data)
        return data
    
    @staticmethod
    def find_units(variable):
        if variable in recording.UNITS_MAP:
            return recording.UNITS_MAP[variable]
        else:
            raise Exception("units unknown")

    def _local_count(self, variable, filter_ids=None):  
        N = {}
        filtered_ids = self.filter_recorded(variable, filter_ids)
	if len(filtered_ids) > 0:
	    for id in filtered_ids:
	        N[id] = len(self._get_spikes(id))
        return N

