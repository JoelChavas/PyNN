import os

def get_installation(target="brainscales"):
    if os.environ.has_key('SYMAP2IC_PATH'):
        symap2ic_path = os.environ['SYMAP2IC_PATH']
        if os.environ.has_key('PYNN_HW_PATH'): target_path = os.path.join(os.environ['PYNN_HW_PATH'],target)
        else: target_path = os.path.join(symap2ic_path,"components/pynnhw/src/hardware", target)
        hardware_path=os.path.join(symap2ic_path,"components/pynnhw/src/hardware")
    else:
        raise Exception("Variable SYMAP2IC_PATH not set!")
    return symap2ic_path, hardware_path, target_path
