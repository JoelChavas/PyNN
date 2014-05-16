import numpy as np
import matplotlib.pyplot as plt

hard = np.loadtxt('hardware.txt')
nest = np.loadtxt('nest.txt')
hard[:,0]=hard[:,0]*1000
nest[:,0]=nest[:,0]*1000

fig=plt.figure()
ax = fig.add_subplot(111)
plt.title("PyNN 0.8 backend - saturation of synaptic weights")

ax.plot(hard[:,0], hard[:,1], '-ro')
ax.plot(hard[:,0], hard[:,2], '-ro', label="ESS")
ax.plot(nest[:,0], nest[:,1], '-b*')
ax.plot(nest[:,0], nest[:,2], '-b*', label = "nest")
ax.set_xlabel("weight (nS)")
ax.set_ylabel("size EPSP (mV)")
ax.legend()
plt.show()
