""" Protocol object """
#***************************************************************************************************
# Copyright 2015, 2019 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
# Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights
# in this software.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.  You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 or in the LICENSE file in the root pyGSTi directory.
#***************************************************************************************************

import itertools as _itertools

from .. import construction as _cnst
from .. import objects as _objs
from ..objects import circuit as _cir
from ..tools import listtools as _lt


class Protocol(object):
    def __init__(self):
        pass

    def run(self, data):
        if data.has_subdata():  # ~ is this is a directory
            # Note: we also know that self *isn't* a MultiProtocol object since
            # MultiProtocol overrides run(...).
            implicit_multiprotocol = MultiProtocol(self)
            return implicit_multiprotocol.run(data)
        return self._run(data)

    def _run(self, data):
        raise NotImplementedError("Derived classes should implement this!")

# SimultaneousProtocol -> runs multiple protocols on the same data, but "trims" circuits and data before running sub-protocols
#  (e.g. Volumetric or randomized benchmarks on different subsets of qubits) -- only accepts SimultaneousInputs.
# MultiProtocol -> runs, on same input circuit structure & data, multiple protocols (e.g. different GST & model tests on same GST data)
#   if that one input is a MultiInput, then it must have the same number of inputs as there are protocols and each protocol is run on the corresponding input.
#   if that one input is a normal input, then the protocols can cache information in a Results object that is handed down.
class MultiProtocol(Protocol):
    def __init__(self, protocols):
        super().__init__()
        self.protocols = protocols

    def run(self, data):
        assert(data.has_subdata()), "`MultiProtocol` can only be run on ProtocolData objects containing sub-data"
        protocols = self.protocols
        if isinstance(protocols, Protocol):  # allow a single Protocol to be given as 'self.protocols'
            protocols = [protocols] * len(data)

        assert(len(data) == len(protocols))

        results = ProtocolResults(data)
        for (qubit_labels, sub_data), protocol in zip(data.items(), protocols):
            sub_results = protocol.run(sub_data)
            results.qtys[qubit_labels] = sub_results.qtys  # something like this?
        return results

    
#Same protocol!
class SimultaneousProtocol(MultiProtocol):
    pass

## MultiProtocol -> runs, on same input circuit structure & data, multiple protocols (e.g. different GST & model tests on same GST data)
##   if that one input is a MultiInput, then it must have the same number of inputs as there are protocols and each protocol is run on the corresponding input.
##   if that one input is a normal input, then the protocols can cache information in a Results object that is handed down.
#class MultiProtocol(Protocol):
#    def __init__(self, protocols, merge_results=False):
#        super().__init__()
#        self.protocols = protocols
#        self.merge_results = merge_results
#
#    def run(self, data):
#        inp = data.input
#        dataset = data.dataset
#        results = ProtocolResults(data)
#
#        if isinstance(inp, MultiInput):
#            assert(len(inp.inputs) == len(self.protocols))
#            for (sub_name, sub_input), protocol in zip(inp.inputs.items(), self.protocols):
#                if sub_name.startswith("**"): subname = protocol.__class__.__name__
#                assert(sub_name not in results.qtys), "Multiple %s names in MultiInput/MultiProtocol" % sub_name
#                sub_data = ProtocolData(sub_input, dataset)  #we *could* truncate the dataset to only sub_input.all_circuits_needing_data, but don't bother
#                sub_results = protocol.run(sub_data)
#                results.qtys[sub_name] = sub_results.qtys  # something like this?
#
#        else:
#            if self.merge_results:
#                for protocol in self.protocols:
#                    sub_name = protocol.__class__.__name__
#                    assert(sub_name not in results.qtys), "Multiple %s names in MultiInput/MultiProtocol" % sub_name
#                    sub_results = protocol.run(results)
#                    results.merge_in_qtys(sub_results.qtys)  # something like this?
#            else:
#                for protocol in self.protocols:
#                    sub_name = protocol.__class__.__name__
#                    assert(sub_name not in results.qtys), "Multiple %s names in MultiInput/MultiProtocol" % sub_name
#                    sub_results = protocol.run(data)
#                    results.qtys[sub_name] = sub_results.qtys  # something like this?


class ProtocolInput(object):
    """ Serialize-able input data for a protocol """

    #def __init__(self, default_protocol_name=None, default_protocol_info=None, circuits=None, typestring=None):
    #    if default_protocol_info is None: default_protocol_info = {}
    #    self.typestring = self.__class__.__name__
    #    self.all_circuits_needing_data = all_circuits if (all_circuits is not None) else []
    #    self.default_protocol_infos = {} if default_protocol_name is None \
    #        else {default_protocol_name: default_protocol_info}

    def __init__(self, circuits=None, qubit_labels=None):
        self.typestring = self.__class__.__name__
        self.all_circuits_needing_data = circuits if (circuits is not None) else []
        self.default_protocol_infos = {}
        
        if qubit_labels is None:
            if len(circuits) > 0:
                self.qubit_labels = circuits[0].line_labels
            else:
                self.qubit_labels = ('*',)  # default "qubit labels"
        else:
            self.qubit_labels = tuple(qubit_labels)

    def add_default_protocol(self, default_protocol_name, default_protocol_info=None):
        if default_protocol_info is None: default_protocol_info = {}
        self.default_protocol_infos[default_protocol_name] = default_protocol_info

    def create_circuit_list(self, verbosity=0):
        return self.basedata['circuitList']

    def create_circuit_lists(self, verbosity=0):  # Needed?? / Helpful?
        return [self.create_circuit_list()]

    def read(self, dirname):
        pass

    def write(self, dirname):
        pass

    def create_subdata(self, subdata_name, dataset):
        raise NotImplementedError("This protocol input cannot create any subdata!")


class CircuitListsInput(ProtocolInput):
    def __init__(self, circuit_lists, all_circuits_needing_data=None, qubit_labels=None, nested=False):
        
        if all_circuits_needing_data is not None:
            all_circuits = all_circuits_needing_data
        elif nested and len(circuit_lists) > 0:
            all_circuits = circuit_lists[-1]
        else:
            all_circuits = []
            for lst in circuit_lists:
                all_circuits.extend(lst)
            _lt.remove_duplicates_in_place(all_circuits)

        self.circuit_lists = circuit_lists
        self.nested = nested
        super().__init__(all_circuits, qubit_labels)


class CircuitStructuresInput(CircuitListsInput):
    def __init__(self, circuit_structs, qubit_labels=None, nested=False):
        """ TODO: docstring - note that a *single* structure can be given as circuit_structs """
        
        #Convert a single LsGermsStruct to a list if needed:
        validStructTypes = (_objs.LsGermsStructure, _objs.LsGermsSerialStructure)
        if isinstance(circuit_structs, validStructTypes):
            master = circuit_structs
            circuit_structs = [master.truncate(Ls=master.Ls[0:i + 1])
                               for i in range(len(master.Ls))]
            nested = True  # (by this construction)

        super().__init__([s.allstrs for s in circuit_structs], None, qubit_labels, nested)
        self.circuit_structs = circuit_structs


# MultiInput -> specifies multiple circuit structures on (possibly subsets of) the same data (e.g. collecting into one large dataset the data for multiple protocols)
class MultiInput(ProtocolInput):  # for multiple inputs on the same dataset
    def __init__(self, sub_inputs, all_circuits=None, qubit_labels=None):
        if not isinstance(sub_inputs, dict):
            sub_inputs = {("**%d" % i): inp for i, inp in enumerate(sub_inputs)}

        if all_circuits is None:
            all_circuits = []
            for inp in sub_inputs.values():
                all_circuits.extend(inp.all_circuits_needing_data)
            _lt.remove_duplicates_in_place(all_circuits)  #Maybe don't always do this?

        if qubit_labels is None:
            qubit_labels = tuple(_itertools.chain(*[inp.qubit_labels for inp in sub_inputs.values()]))

        super().__init__(all_circuits, qubit_labels)
        self._subinputs = sub_inputs

    def create_subdata(self, sub_name, dataset):
        """TODO: docstring - used to create sub-ProtocolData objects (by ProtocolData) """
        sub_input = self[sub_name]
        return ProtocolData(sub_input, dataset)

    def items(self):
        return self._subinputs.items()

    def keys(self):
        return self._subinputs.keys()
    
    def __getitem__(self, key):
        return self._subinputs[key]

    def __contains__(self, key):
        return key in self._subinputs[key]

    def __len__(self):
        return len(self._subinputs)


# SimultaneousInput -- specifies a "qubit structure" for each sub-input
class SimultaneousInput(MultiInput):
    """ TODO - need to be given sub-inputs whose circuits all act on the same set of
        qubits and are disjoint with the sets of all other sub-inputs.
    """

    @classmethod
    def from_tensored_circuits(cls, circuits, template_input, qubit_labels_per_input):
        pass #Useful??? - need to break each circuit into different parts
    # based on qubits, then copy (?) template input and just replace itself
    # all_circuits_needing_data member?
    
    def __init__(self, inputs, tensored_circuits=None, qubit_labels=None):
        #TODO: check that inputs don't have overlapping qubit_labels

        if qubit_labels is None:
            qubit_labels = tuple(_itertools.chain(*[inp.qubit_labels for inp in inputs]))

        if tensored_circuits is None:
            #Build tensor product of circuits
            tensored_circuits = []
            circuits_per_input = [inp.all_circuits_needing_data[:] for inp in inputs]

            #Pad shorter lists with None values
            maxLen = max(map(len, circuits_per_input))
            for lst in circuits_per_input:
                if len(lst) < maxLen: lst.extend([None] * (maxLen - len(lst)))
                
            for subcircuits in zip(*circuits_per_input):
                c = _cir.Circuit(num_lines=0, editable=True)  # Creates a empty circuit over no wires
                for subc in subcircuits:
                    if subc is not None:
                        c.tensor_circuit(subc)
                c.line_labels = qubit_labels
                c.done_editing()
                tensored_circuits.append(c)

        sub_inputs = {inp.qubit_labels: inp for inp in inputs}
        super().__init__(sub_inputs, tensored_circuits, qubit_labels)

    def get_structure(self):  #TODO: USED??
        return list(self.keys())  # a list of qubit-label tuples

    def create_subdata(self, qubit_labels, dataset):
        qubit_ordering = list(dataset.keys())[0].line_labels
        qubit_index = {qlabel: i for i, qlabel in enumerate(qubit_ordering)}
        sub_input = self[qubit_labels]
        qubit_indices = [qubit_index[ql] for ql in qubit_labels]  # TODO: better way to connect qubit indices in dataset with labels??
        filtered_ds = _cnst.filter_dataset(dataset, qubit_labels, qubit_indices, idle=None)  # Marginalize dataset
        return ProtocolData(sub_input, filtered_ds)


class ProtocolData(object):
    def __init__(self, protocol_input, dataset=None, cache=None):
        self.input = protocol_input
        self.dataset = dataset  # MultiDataSet allowed for multi-pass data?
        self.cache = cache if (cache is not None) else {}
        self._subdatas = {} if isinstance(protocol_input, MultiInput) else None

    def has_subdata(self):
        return self._subdatas is not None
        
    #Support lazy evaluation of sub_datas
    def keys(self):
        if self.has_subdata():
            return self.input.keys()
        else:
            return []

    def items(self):
        if self.has_subdata():
            for name in self.input.keys():
                yield name, self[name]

    def __getitem__(self, subdata_name):
        if not self.has_subdata():
            raise ValueError("This ProtocolData object has no sub-datas.")
        if subdata_name not in self._subdatas:
            if subdata_name not in self.input.keys():
                raise KeyError("Missing sub-data name: %s" % subdata_name)
            self._subdatas[subdata_name] = self.input.create_subdata(subdata_name, self.dataset)
        return self._subdatas[subdata_name]

    #def __setitem__(self, subdata_name, val):
    #    self._subdatas[subdata_name] = val

    def __contains__(self, subdata_name):
        if self.has_subdata():
            return subdata_name in self.input.keys()
        else:
            return False

    def __len__(self):
        if self.has_subdata():
            return len(self.input)
        else:
            return 0


class ProtocolResults(ProtocolData):
    def __init__(self, data, result_qtys=None):
        super().__init__(data.input, data.dataset)
        self.qtys = result_qtys if (result_qtys is not None) else {}


#Need way to specify *where* the data for a protocol input comes from that
# isn't the data itself - maybe an object within a ProtocolDirectory?
# e.g. create a

#Operations we'd like to have - maybe in creating MultiInput?
# - merge circuits to perform protocols in parallel: Inputs => MultiInput
# - interleave protcols so data is taken together: Inputs => MultiInput
# - add a protocol whose data will be taken along with (and maybe overlaps) an existing
#    protocol's data: Input.add(Input) => MultiInput containing both?
# - don't nest MultiInputs, i.e. MultiInput + Input => MultiInput only one level deep
# - Directory holds multinputs separately - a type of some kind of link between datasets and inputs...
#    any other type needed?

# - Protocol.run_on_data methods can take a ProtocolResults object and try to extract cached qtys to speed up calc
# - possible to create inputs from a ProcessorSpec, protocol name, and target qubits?

# Directory structure:
# root/inputs/NAME/SUBinputNAME...   - same as saving a collection of inputs in named dirs
# root/datasets/NAME - datasets - same names as top-level inputs (maybe multi-inputs) - just saved DataSets
# root/results/NAME/SUBinputNAME...  -- but may want protocols to specify how results should be
#  organized separately, e.g. datasets of success counts for nQ RB?  But could we add MultiInput types that
#  know to store e.g. marginalized counts, in a higher level directory that any existing or added sub-protocols
#  can utilize?
# root/reports/REPORTNAME - reports generated separately?  Maybe Directory has create_report and add_report
#  methods?  Is it possible to allow reports to pull from a cache of results somewhere?


class ProtocolDirectory(object):
    """ Holds multiple ProtocolData objects
    - and maybe can add an object with a protocol input and a data name (or not?)?
    - issue is, how to allow same data to be used for different protocols...
    Could hold reports too?
    """
    def __init__(self, inputs, datas, reports):
        self.inputs = inputs  # should be a dict of inputs; otherwise make into a dict
        self.datas  # pull datas apart into datasets and inputs; collect unique DataSets -> all_datasets_in_datas
        self.datasets = all_datasets_in_datas
        self.reports = reports
        self.results = TODO

    def read(self, dirname):
        pass

    def write(self, dirname):
        pass
