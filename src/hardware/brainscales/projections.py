from itertools import repeat, izip
from pyNN import common, errors
from pyNN.core import ezip
from pyNN.parameters import ParameterSpace
from pyNN.space import Space
import pyNN
from . import simulator
from .standardmodels.synapses import TsodyksMarkramMechanism, StaticSynapse
import globals as g
import mapping
toLog = mapping.toLog
ERROR   = mapping.ERROR
WARNING = mapping.WARNING
INFO    = mapping.INFO
DEBUG0  = mapping.DEBUG0
DEBUG1  = mapping.DEBUG1
DEBUG2  = mapping.DEBUG2
DEBUG3  = mapping.DEBUG3

class Connection(object):
    """
    Store an individual plastic connection and information about it. Provide an
    interface that allows access to the connection's weight, delay and other
    attributes.
    """

    def __init__(self, pre, post, **attributes):
        self.presynaptic_index = pre
        self.postsynaptic_index = post
        for name, value in attributes.items():
            setattr(self, name, value)

    def as_tuple(self, *attribute_names):
        # should return indices, not IDs for source and target
        return tuple([getattr(self, name) for name in attribute_names])


class Projection(common.Projection):
    __doc__ = common.Projection.__doc__
    _simulator = simulator
    _static_synapse_class = StaticSynapse

    def __init__(self, presynaptic_population, postsynaptic_population,
                 connector, synapse_type=None, source=None, receptor_type=None,
                 space=Space(), label=None):
        common.Projection.__init__(self, presynaptic_population, postsynaptic_population,
                                   connector, synapse_type, source, receptor_type,
                                   space, label)

        ## Create connections
        self.connections = []

	p = self._connector.p_connect
        if not g._calledSetup: raise Exception("ERROR: Call function 'setup(...)' first!")
        if g._calledRunMapping: raise Exception("ERROR: Cannot connect cells after _run_mapping() has been called")
        if p > 1.: toLog(WARNING, "A connection probability larger than 1 has been passed as connect argument!")
    
        # check if mapping priority (a value between 0 and 1) has been passed
        #if "mapping_priority" in extra_params.keys():
            #priority = extra_params["mapping_priority"]
            #if priority > 1.0 or priority < 0.0: raise Exception("ERROR: Only values between 0.0 and 1.0 are allowed for argument mapping_priority of function connect!")
        #else: priority = 1.0
    
        # check if a parameter_set has been passed
        #if "parameter_set" in extra_params.keys():
            #existing_parameter_set = extra_params["parameter_set"]
        #else:
            #existing_parameter_set = None
            ## if there is not yet a parameter set, we have to check the delays:
            #if delay and (delay is not common.build_state_queries(simulator)[2]):
                #delay = common.build_state_queries(simulator)[2]();
                #NoDelayWarning()
	existing_parameter_set = None
    
        if isinstance(self.synapse_type,StaticSynapse):
            stp_parameters = None
        elif isinstance(self.synapse_type,TsodyksMarkramMechanism):
            stp_parameters = TsodyksMarkramMechanism.parameters
        else:
            raise Exception("ERROR: The only short-term synaptic plasticity type supported by the BrainscaleS hardware is TsodyksMarkram!")
    
        g._synapsesChanged = True
        g._connectivityChanged = True
    
	sharedParameters=True
	priority = None
	delay=self.synapse_type.parameter_space['delay']
	weight=self.synapse_type.parameter_space['weight']
        try:
            if sharedParameters:
                newParameterSet = existing_parameter_set or pyNN.hardware.brainscales._createSynapseParameterSet(weight, delay, self.receptor_type, priority, stp_parameters)
            for src in self.pre:
                if p < 1.:
                    if self._connector.rng: # use the supplied RNG
                        rarr = self._connector.rng.uniform(0.,1.,len(postsynaptic_population))
                    else:   # use the default RNG
                        rarr = g._globalRNG.uniform(0.,1.,len(postsynaptic_population))
                for j,tgt in enumerate(self.post):
                    # evaluate if a connection has to be created
                    if p >= 1. or rarr[j] < p:
                        toLog(DEBUG1, 'Connecting ' + str(src) + ' with ' + str(tgt) + ' and weight ' + str(weight))
                        if not sharedParameters: newParameterSet = pyNN.hardware.brainscales.__createSynapseParameterSet(weight, delay, self.receptor_type, priority, stp_parameters)
                        g._preprocessor.BioModelInsertSynapse(src.graphModelNode, tgt.graphModelNode, newParameterSet)
    
        except Exception,e:
            raise errors.ConnectionError(e)


        connector.connect(self)

    def __len__(self):
        return len(self.connections)

    def set(self, **attributes):
        parameter_space = ParameterSpace

    def _convergent_connect(self, presynaptic_indices, postsynaptic_index,
                            **connection_parameters):
        for name, value in connection_parameters.items():
            if isinstance(value, float):
                connection_parameters[name] = repeat(value)
        for pre_idx, other in ezip(presynaptic_indices, *connection_parameters.values()):
            other_attributes = dict(zip(connection_parameters.keys(), other))
            self.connections.append(
                Connection(pre_idx, postsynaptic_index, **other_attributes)
            )