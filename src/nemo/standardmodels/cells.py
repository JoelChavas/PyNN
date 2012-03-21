"""
Standard cells for the nemo module


:copyright: Copyright 2006-2011 by the PyNN team, see AUTHORS.
:license: CeCILL, see LICENSE for details.

$Id: cells.py 897 2011-01-13 12:47:23Z pierre $
"""

from pyNN.standardmodels import cells, build_translations, ModelNotAvailable, StandardCellType
from pyNN import errors
import numpy


class Izikevich(cells.Izikevich):
    
    __doc__ = cells.Izikevich.__doc__ 

    translations = build_translations(
        ('a',    'a'),
        ('b',    'b'),
        ('v_reset', 'c'),
        ('d',    'd'),
        ('tau_refrac', 'tau_refrac')
    )

    indices = {'a' : 0, 'b' : 1, 'c' : 2, 'd' : 3}
    initial_indices = {'u' : 0, 'v' : 1}



class SpikeSourcePoisson(cells.SpikeSourcePoisson):
    
    __doc__ = cells.SpikeSourcePoisson.__doc__ 

    translations = build_translations(
        ('rate', 'rate'),
        ('start', 'start'),
        ('duration', 'duration')
    )

    class spike_player(object):
        
        def __init__(self, rate, start, duration, precision=1.):
            self.rate        = rate
            self.start       = start
            self.duration    = duration
            self.rng         = numpy.random.RandomState()
            self.precision   = precision
            self.rate_Hz     = self.rate * self.precision / 1000.
            self.stop_time   = self.start + self.duration
            self.buffer      = 1000           
            self.do_spikes   = self.rng.rand(self.buffer) < self.rate_Hz
            self.idx         = 0
    
        def do_spike(self, t):
            if (t > self.stop_time) or (t < self.start):
                return False
            else:
                if self.idx == (self.buffer - 1):
                    self.do_spikes = self.rng.rand(self.buffer) <= self.rate_Hz
                    self.idx       = 0
                self.idx += 1
                return self.do_spikes[self.idx]
        
        def reset(self, rate=None, start=None, duration=None, precision=1):
            if rate is not None:
                self.rate    = rate
            if start is not None:            
                self.start   = start
            if duration is not None:
                self.duration= duration
            self.rate_Hz     = self.rate * self.precision/1000.
            self.stop_time   = self.start + self.duration

    def __init__(self, parameters):
        cells.SpikeSourcePoisson.__init__(self, parameters) 


class SpikeSourceArray(cells.SpikeSourceArray):

    __doc__ = cells.SpikeSourceArray.__doc__    

    translations = build_translations(
        ('spike_times', 'spike_times'),
    )

    class spike_player(object):
        
        def __init__(self, spike_times=[], precision=1):
            self.spike_times = precision * numpy.round(spike_times/precision)        
            self.spike_times = numpy.unique(numpy.sort(self.spike_times))
            self.cursor      = 0
            self.N           = len(self.spike_times)

        @property
        def next_spike(self):
            if self.cursor < self.N:
                return self.spike_times[self.cursor]
            else:
                return numpy.inf
        
        def update(self):
            self.cursor += 1

        def reset(self, spike_times, precision):
            self.spike_times = precision * numpy.round(spike_times/precision)
            self.spike_times = numpy.unique(numpy.sort(self.spike_times))
            self.N           = len(self.spike_times)
            self.cursor      = 0

    def __init__(self, parameters):
        cells.SpikeSourceArray.__init__(self, parameters)        


class IF_cond_exp_gsfa_grr(ModelNotAvailable):
    pass

class IF_curr_alpha(ModelNotAvailable):
    pass

class IF_curr_exp(cells.IF_curr_exp):
    
    __doc__ = cells.IF_curr_exp.__doc__    

    translations = build_translations(
        ('v_rest',     'v_rest'),
        ('v_reset',    'v_reset'),
        ('cm',         'cm'), 
        ('tau_m',      'tau_m'),
        ('tau_refrac', 't_refrac'),
        ('tau_syn_E',  'tau_syn_E'),
        ('tau_syn_I',  'tau_syn_I'),
        ('v_thresh',   'v_thresh'),
        ('i_offset',   'i_offset'), 
    )

    indices = {
            'v_rest' : 0,
            'cm' : 2,
            'tau_m' : 3,
            't_refrac' : 4,
            'tau_syn_E' : 5,
            'tau_syn_I' : 6,
            'i_offset' : 8,
            'v_reset' : 1,
            'v_thresh' : 7
        }

    initial_indices = {'v' : 0}


class IF_cond_alpha(ModelNotAvailable):
    pass

class IF_cond_exp(ModelNotAvailable):
    pass

class IF_facets_hardware1(ModelNotAvailable):
    pass

class EIF_cond_alpha_isfa_ista(ModelNotAvailable):
    pass

class EIF_cond_exp_isfa_ista(ModelNotAvailable):
    pass    

class HH_cond_exp(ModelNotAvailable):
    pass

class SpikeSourceInhGamma(ModelNotAvailable):
    pass

class IF_cond_exp_gsfa_grr(ModelNotAvailable):
    pass
