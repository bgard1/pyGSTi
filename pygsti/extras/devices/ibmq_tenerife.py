""" Functions for interfacing pyGSTi with IBM Q Tenerife (ibmqx4) """
#***************************************************************************************************
# Copyright 2015, 2019 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
# Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights
# in this software.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.  You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 or in the LICENSE file in the root pyGSTi directory.
#***************************************************************************************************

# import numpy as _np
# from ...objects import processorspec as _pspec

qubits = ['Q' + str(x) for x in range(5)]

twoQgate = 'Gcnot'

edgelist = [('Q1', 'Q0'),
            ('Q2', 'Q1'),
            ('Q2', 'Q0'),
            ('Q3', 'Q2'),
            ('Q3', 'Q4'),
            ('Q4', 'Q2')]


spec_format = 'ibmq_v2019'

# def qubits():

#     return ['Q' + str(x) for x in range(5)]


# def make_processor_spec(one_q_gate_names, construct_clifford_compilations = {'paulieq' : ('1Qcliffords',),
#                         'absolute': ('paulis', '1Qcliffords')}, verbosity=0):
#     """
#     todo

#     """
#     gate_names = ['Gcnot'] + one_q_gate_names
#     qubit_labels = qubits()
#     total_qubits = len(qubit_labels)
#     cnot_edge_list = get_twoQgate_edgelist()
#     availability = {'Gcnot':cnot_edge_list}
#     pspec = _pspec.ProcessorSpec(total_qubits, gate_names, availability=availability,
#                                   construct_clifford_compilations=construct_clifford_compilations,
#                                   verbosity=verbosity, qubit_labels=qubit_labels)
#     return pspec


# def get_twoQgate_edgelist(subset=None):
#     """
#     The edgelist for the CNOT gates in IBMQX5. If subset is None this is
#     all the CNOTs in the device; otherwise it only includes the qubits in
#     the subset (qubits are labelled 'Qi' for i = 0,1,2...).
#     """
#     cnot_edge_list = [('Q1', 'Q0'),
#                       ('Q2', 'Q1'),
#                       ('Q2', 'Q0'),
#                       ('Q3', 'Q2'),
#                       ('Q3', 'Q4'),
#                       ('Q4', 'Q2')]
#     if subset is None:
#         return cnot_edge_list

#     else:
#         subset_cnot_edge_list = []
#         for cnot_edge in cnot_edge_list:
#             if cnot_edge[0] in subset and cnot_edge[1] in subset:
#                 subset_cnot_edge_list.append(cnot_edge)

#         return subset_cnot_edge_list


# def get_all_connected_sets(n):
#     """

#     """

#     pspec = make_processor_spec(['Gc' + str(i) for i in range(24)], construct_clifford_compilations={})
#     import itertools as _iter
#     connectedqubits = []
#     for combo in _iter.combinations(pspec.qubit_labels, n):
#         if pspec.qubitgraph.subgraph(list(combo)).are_glob_connected(combo):
#             connectedqubits.append(combo)

#     return connectedqubits