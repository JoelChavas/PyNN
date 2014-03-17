from pyNN import common

name = "HardwareBrainscales"

class ID(int, common.IDMixin):
    def __init__(self, n):
        """Create an ID object with numerical value `n`."""
        int.__init__(n)
        common.IDMixin.__init__(self)

class State(common.control.BaseState):
    """!
    Represent the simulator state.
    For implementation of get_time_step() and similar functions.
    """
    def __init__(self):
        common.control.BaseState.__init__(self)
        self.mpi_rank = 0
        self.num_processes = 1
        self.clear()
        self.t = 0.0
        self.dt = 0.0
        self.min_delay = 0.0
        self.max_delay = 0.0
    def run(self, simtime):
        self.t += simtime
        self.running = True
    def run_until(self, tstop):
        self.t = tstop
        self.running = True
    def clear(self):
        self.recorders = set([])
        self.id_counter = 42
        self.segment_counter = -1
        self.reset()
    def reset(self):
        """Reset the state of the current network to time t = 0."""
        self.running = False
        self.t = 0.0
        self.segment_counter += 1

#===================================================
# a Singleton, so only a single instance ever exists
#===================================================
state = State()
del State
