#!/usr/bin/python
# encoding: utf-8
#
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: Mapping Analyzer module for the BrainScaleS hardware
#
# ***************************************************************************
#
## @namespace hardware::brainscales::manualmapper
##
## @short Mapping Analyzer module .
##
## @detailed Holds a Class MappingAnalyzer that facilitates the analysis of a mapped network.


import numpy as np


class MappingAnalyzer:
    """!

    Class to facilitate the analysis of distorted networks mapped onto the BrainScaleS hardware.

    Requires files containing the lost and realized conneciton matrices of a network.
    The files are generatored during the mapping process, if the following parameters
    are in setup(..)
    > pynn.setup(
              realizedConnectionMatrixFile = realized_conn_file,
              lostConnectionMatrixFile = lost_conn_file,
              )

    Note:
    In the hardware.facets backend, real neurons get increasing IDs(integers) starting at 0 in the order they are created.
    SpikeSources get negative and decreasing IDs starting at -1 in the order they are created.

    """
    def __init__(self, lost_conn_file, realized_conn_file):
        """!

        @param lost_conn_file     - name of the file containing the connections lost during mapping
        @param realized_conn_file - name of the file containing the connections realized by the mapping

        """
        self.neurons, self.targets_lost = self.read_conn_matrix_file(lost_conn_file)
        sources_realized, self.targets_realized = self.read_conn_matrix_file(realized_conn_file)
        assert(sources_realized  == self.neurons)
        self.print_stats()
        self.sources_lost, self.target_neurons  = self._flip_matrix(self.neurons,self.targets_lost)
        self.sources_realized, targets_realized = self._flip_matrix(self.neurons,self.targets_realized)
        assert(self.target_neurons == targets_realized)

    def print_stats(self):
        """!

        Prints overall mapping statistics.

        """
        lost_s = np.sum([len(tgt_list) for tgt_list in self.targets_lost])
        realized_s = np.sum([len(tgt_list) for tgt_list in self.targets_realized])
        total_s=  lost_s + realized_s
        print "Mapping Statistiscs:" 
        print lost_s, " of ", total_s, " Synapses lost (", lost_s*100./total_s, "%)"

    def get_source_neurons(self, src_filter=None):
        """!

        Returns a list with source neuron ids, for which the supplied filter returns True.        
        If no filter is supplied, all source neurons are considered.
        @param src_filter - a function that returns True for all ids of source neurons, that shall be considered

        """
        if src_filter is None:
            src_filter = lambda x:True
        else:
            assert( hasattr(src_filter, "__call__") )
        return filter(src_filter, self.neurons)

    def get_target_neurons(self, tgt_filter=None):
        """!

        Returns a list with target neuron ids, for which the supplied filter returns True.        
        If no filter is supplied, all target neurons are considered.
        @param tgt_filter - a function that returns True for all ids of target neurons, that shall be considered

        """
        if tgt_filter is None:
            tgt_filter = lambda x:True
        else:
            assert( hasattr(tgt_filter, "__call__") )
        return filter(tgt_filter, self.target_neurons)

    def get_lost_and_realized_count(self, src_filter=None, tgt_filter = None):
        """!

        returns the number of lost and realized synapses between subsets of source neurons
        and target neurons.
        Filters can be applied for both the source neurons and the target neurons:
        If no filter is supplied, all source rsp. target neurons are considered.
        @param src_filter - a function that returns True for all ids of source neurons, that shall be considered
        @param tgt_filter - a function that returns True for all ids of target neurons, that shall be considered

        """
        lost_count = 0
        realized_count = 0
        if src_filter is None:
            src_filter = lambda x:True
        else:
            assert( hasattr(src_filter, "__call__") )
        for n,src in enumerate(self.neurons):
            if src_filter(src):
                lost_count += len(filter(tgt_filter,self.targets_lost[n]) if tgt_filter else self.targets_lost[n])
                realized_count += len(filter(tgt_filter,self.targets_realized[n]) if tgt_filter else self.targets_realized[n])
        return lost_count, realized_count

    def get_lost_and_realized_count2(self, src_filter=None, tgt_filter = None):
        """!

        returns the number of lost and realized synapses between a subset of source neurons
        and a relation between source and target neurons.
        Filters can be applied for both the source neurons and the target neurons:
        If no filter is supplied, all source rsp. target neurons are considered.
        @param src_filter - a function that returns True for all ids of source neurons, that shall be considered
        @param tgt_filter - a function generator, that generates a compare function for each src id. 
                            This function should return true for each target neuron id, for which the relation betwen src and tgt id is true.
        Example:
        > def same_modulo_3_like_source(src):
        >    mod3 = src%3
        >    f = lambda x : x%3 == mod3
        >    return f
        > is_even = lambda x: x%2==0
        > # connection from even neurons to neurons that have the same modulo3.
        > MA.get_lost_and_realized_count2(src_filter=is_even, tgt_filter=same_modulo_3_like_source)

        """
        lost_count = 0
        realized_count = 0
        if src_filter is None:
            src_filter = lambda x:True
        else:
            assert( hasattr(src_filter, "__call__") )
        for n,src in enumerate(self.neurons):
            if src_filter(src):
                lost_count += len(filter(tgt_filter(src),self.targets_lost[n]) if tgt_filter else self.targets_lost[n])
                realized_count += len(filter(tgt_filter(src),self.targets_realized[n]) if tgt_filter else self.targets_realized[n])
        return lost_count, realized_count

    def get_lost_and_realized_outgoing_counts(self, src_filter=None, tgt_filter = None):
        """!

        Returns for each source neuron the number of lost rsp. realized outgoing connections to given target neurons
        Returns a tuple (lost_count, realized_count), where boths counts are lists, that contain the number of lost
        rsp realized connections for each source neuron.

        Filters can be applied for both the source neurons and the target neurons:
        If no filter is supplied, all source rsp. target neurons are considered.
        @param src_filter - a function that returns True for all ids of source neurons, that shall be considered
        @param tgt_filter - a function that returns True for all ids of target neurons, that shall be considered

        """
        lost_count = []
        realized_count = []
        if src_filter is None:
            src_filter = lambda x:True
        else:
            assert( hasattr(src_filter, "__call__") )
        for n,src in enumerate(self.neurons):
            if src_filter(src):
                lost_count.append(len(filter(tgt_filter,self.targets_lost[n]) if tgt_filter else self.targets_lost[n]))
                realized_count.append(len(filter(tgt_filter,self.targets_realized[n]) if tgt_filter else self.targets_realized[n]))
        return lost_count, realized_count

    def get_lost_and_realized_incoming_counts(self, src_filter=None, tgt_filter = None):
        """!

        Returns for each target neuron the number of lost rsp. realized incoming connections from given source neurons
        Returns a tuple (lost_count, realized_count), where boths counts are lists, that contain the number of lost
        rsp realized incoming connections for each target neuron.

        Filters can be applied for both the source neurons and the target neurons:
        If no filter is supplied, all source rsp. target neurons are considered.
        @param src_filter - a function that returns True for all ids of source neurons, that shall be considered
        @param tgt_filter - a function that returns True for all ids of target neurons, that shall be considered

        """
        if tgt_filter is None:
            tgt_filter = lambda x:True
        else:
            assert( hasattr(tgt_filter, "__call__") )
        lost_count = []
        realized_count = []
        for n,src in enumerate(self.target_neurons):
            if tgt_filter(src):
                lost_count.append(len(filter(src_filter,self.sources_lost[n]) if src_filter else self.sources_lost[n]))
                realized_count.append(len(filter(src_filter,self.sources_realized[n]) if src_filter else self.sources_realized[n]))
        return lost_count, realized_count


    def print_synloss(self, src_filter=None, tgt_filter = None):
        """!

        Print the synapse loss between subsets of source neurons
        and target neurons.
        Filters can be applied for both the source neurons and the target neurons:
        If no filter is supplied, all source rsp. target neurons are considered.
        @param src_filter - a function that returns True for all ids of source neurons, that shall be considered
        @param tgt_filter - a function that returns True for all ids of target neurons, that shall be considered

        """
        lost_s, realized_s = self.get_lost_and_realized_count(src_filter,tgt_filter)
        total_s=  lost_s + realized_s
        print lost_s, " of ", total_s, " Synapses lost (", (lost_s*100./total_s if total_s > 0 else 0.) , "%)"

    @staticmethod
    def read_conn_matrix_file(filename):
        """!

        reads a connection matrix from a file.
        @param filename - name of the connection matrix file

        returns a tuple of (source_ids,target_ids), where source_ids is a list of source ids
        and target_ids is a list of lists, i.e. for each source id as list of target ids.

        The syntax of the file is the following:
        Connectivity is stored as an adjacency-list
        Each line in the file starts with the ID of the source neuron, which is separated via a colon
        from a list of white space separated target neurons.
        > SRC_NEURON:TGT1 TGT2 TGT3

        """
        fn = open(filename,'r')
        source_ids = []
        target_ids= []
        for line in fn.readlines():
            source, targets = line.split(':',1)
            targets = [int(t) for t in  targets.split()]
            source_ids.append(int(source))
            target_ids.append(targets)
        fn.close()
        return (source_ids,target_ids)

    @staticmethod
    def _flip_matrix(srcs, tgts):
        """!

        flips a connection matrix stored as an adjacency list
        @param srcs - list of source IDs
        @param tgts - a list of lists, for each source ID a list of target IDs

        Sustaining the same connectivity, it returns tuple (sources,targets)
        where targets is list of target IDs and sources a list of lists holding
        for each target ID a list of source IDs
        Assumes that all target IDs are positive.

        """
        targets = filter(lambda x: x>=0,srcs)
        sources = [ [] for i in range(len(targets))]
        for (src,tgt_list) in zip(srcs,tgts):
            for tgt in tgt_list:
                sources[tgt].append(src)
        return sources,targets

