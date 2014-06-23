from os import environ, path

#if __name__ == 'pyNN.hardware.brainscales':
if environ.has_key('SYMAP2IC_PATH'):
    symap2ic_path = environ['SYMAP2IC_PATH']
    hardware_path=path.join(symap2ic_path,"components/pynnhw/src")
    __path__.append(path.join(hardware_path,"hardware"))
    import brainscales
else:
    raise Exception("Variable SYMAP2IC_PATH not set!")
