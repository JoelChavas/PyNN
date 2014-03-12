# encoding: utf-8
# ***************************************************************************
#
# Copyright: TUD/UHEI 2007 - 2011
# License: GPL
# Description: utility classes for passing key-word Arguments in functions
#
# ***************************************************************************
#
## @namespace hardware::brainscales::arg_utils
#
## @short utility classes for key-word Arguments
## @detailed ...

def reindent(s, num_spaces):
    """indents a (multi-line) string by a given number of spaces"""
    return "\n".join([" "*num_spaces+ line for line in s.split("\n")])

class Arg(object):
    def __init__(self, name, description, default=None, dtype=None, choices=None, drange=None):
        assert isinstance(name, str)
        assert isinstance(description, str)
        self.name = name
        self.description = description
        self.default =default
        self.dtype = dtype
        self.choices = choices
        self.drange=drange

    def pprint(self, indent=0):
        sep_string = " - "
        s = self.name.ljust(indent) + sep_string + self.description
        if self.default is not None:
            s += "\ndefault: " + str(self.default)
        if self.choices:
            s += "\nchoices: " + str(self.choices)
        if self.drange:
            s += "\nrange: " + str(self.drange)
        # if everything is a multiline string, shift the string accordingly
        if s.find("\n") != -1:
            s = s.split("\n")
            s = "\n".join(s[0:1] + [" "*(indent+len(sep_string)) + line for line in s[1:]])
        return  s

    def check(self,value):
        if self.dtype is not None:
            if not isinstance(value, self.dtype):
                raise Exception ("The type of  argument " + self.name + " is wrong, must be of type" + str(self.dtype) + ", but is " + str(type(value)))
        if self.choices is not None:
            if value not in self.choices:
                raise Exception("The value specified for argument " + self.name + " is invalid, must be of " + str([str(c ) for c in self.choices])  + ", but is " + str(value))
        elif self.drange is not None:
            if not (self.drange[0] <= value <= self.drange[1]):
                raise Exception("The value specified for  argument " + self.name + " is out of range, must be in range " + str(self.drange) + ", but is " + str(value))
        return True

class ArgList(object):
    def __init__(self, *args):
        self._args = []
        self.names = set()
        for arg in args:
            assert isinstance(arg, Arg)
            if not (arg.name in self.names):
                self._args.append(arg)
                self.names.add(arg.name)
            else:
                raise Exception("An Argument with name " + arg.name + " is already in the list")
    def __getitem__(self, key):
        assert isinstance(key, str)
        if key in self.names:
            for arg in self._args:
                if arg.name == key:
                    return arg
        else:
            raise Exception("ArgList has no Argument with name " + key)

    def pprint(self, indent=0):
        subind = max(map(len, self.names))
        s = ""
        for arg in self._args:
            s += arg.pprint(subind+ 2)
            s += "\n"
        return s

    def get_defaults_as_dict(self):
        rv = {}
        for arg in self._args:
            if arg.default is not None:
                rv[arg.name] = arg.default
        return rv



if __name__ == "__main__":
    def test_Args():
        ms = Arg("maxSynapseLoss", "maximum synapse\nloss allowed", default=0.1, dtype=float, drange=(0.,1.))
        imm = Arg("interactiveMappingMode", "enable the interactive Mapping mode", default=False, dtype=bool)
        args = [ms,imm]
        ind = max(map(lambda x : len(x.name), args))
        print ind
        for arg in args:
            print arg.pprint(ind+2)
        print ms.pprint()
        print imm.pprint()

        print args
        al = ArgList(ms,imm)
        print al._args
        print al.pprint()
        print al.pprint(5)
        s = al.pprint(5)
        # shift
        indent = 10
        print reindent(s,1)
        print reindent(s,2)
        print reindent(s,5)
        print reindent(s,10)
        print reindent(s,1)

        ms.check(0.2)
        ms.check(0.)
        ms.check(1.)
        ms.check(1)
        ms.check(1.2) # should raise

    test_Args()

