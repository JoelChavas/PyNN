from os import environ, path
from sys import path as syspath

#if __name__ == 'pyNN.hardware.brainscales':
if environ.has_key('SYMAP2IC_PATH'):
    symap2ic_path = environ['SYMAP2IC_PATH']
    hardware_path=path.join(symap2ic_path,"components/pynnhw/src")
    syspath.insert(0,hardware_path)
    from hardware.brainscales import *
else:
    raise Exception("Variable SYMAP2IC_PATH not set!")