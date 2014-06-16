import os
import aux

if __name__ == 'pyNN.hardware.brainscales':
    symap2ic_path, target_path = aux.get_installation('brainscales')
    execfile(os.path.join(target_path,'__init__.py'))
