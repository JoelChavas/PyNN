#!/usr/bin/env python

import subprocess, glob, os

simulators = []
for sim in "pcsim", "neuron", "nest", "brian":
    try:
        exec("import pyNN.%s" % sim)
        simulators.append(sim)
    except ImportError:
        pass

exclude = {
    'PCSIM': ("brunel.py", "VAbenchmarks.py", "HH_cond_exp.py", "EIF_cond_alpha_isfa_ista.py"),
    'NEURON': ("brunel.py", "VAbenchmarks.py"),
    'NEST': ("brunel.py", "VAbenchmarks.py"),
    'Brian': ("brunel.py", "VAbenchmarks.py", "HH_cond_exp.py", "tsodyksmarkram.py",
              "tsodyksmarkram2.py", "simple_STDP.py", "simple_STDP2.py", "EIF_cond_alpha_isfa_ista.py"),
}

extra_args = {
    "VAbenchmarks2.py": "CUBA",
}

for simulator in 'PCSIM', 'NEST', 'NEURON', 'Brian':
    if simulator.lower() in simulators:
        print "\n\n\n================== Running examples with %s =================\n" % simulator
        for script in glob.glob("../*.py"):
            script_name = os.path.basename(script)
            if script_name not in exclude[simulator]:    
                cmd = "python %s %s" % (script, simulator.lower())
                if script_name in extra_args:
                    cmd += " " + extra_args[script_name]
                print cmd,
                logfile = open("Results/%s_%s.log" % (os.path.basename(script), simulator), 'w')
                p = subprocess.Popen(cmd, shell=True, stdout=logfile, stderr=subprocess.PIPE, close_fds=True)
                retval = p.wait()
                print retval == 0 and " - ok" or " - fail"
    else:
        print "\n\n\n================== %s not available =================\n" % simulator
    
print "\n\n\n================== Plotting results =================\n" 
for script in glob.glob("../*.py"):
    cmd = "python plot_results.py %s" % os.path.basename(script)[:-3]
    print cmd
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    p.wait()
