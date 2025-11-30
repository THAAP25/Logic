#!/usr/bin/env python3
"""
Graph Partitioning Problem SAT Solver

This script encodes, solves, and decodes the graph partitioning problem
via reduction to SAT. Given a graph G(V,E) with 2n nodes and integer k,
determines if nodes can be partitioned into two sets of size n with at
most k edges crossing between them.
"""

import sys
import subprocess
import tempfile
import os
import shutil
from typing import List, Tuple, Set, Dict
from argparse import ArgumentParser


def load_instance(input_file):
    """
    Read the input instance from file.

    Supports three formats:
    1. Simple: n k, then edges u v
    2. DIMACS graph: p edge <nodes> <edges>, then e u v
    3. DIMACS CNF: p cnf <vars> <clauses>, with metadata comments

    Returns: (edges, n, k) where edges is list of (u,v) tuples
    """
    with open(input_file, 'r') as f:
        lines = f.readlines()

    # Detect format
    format_type = None
    for line in lines:
        line = line.strip()
        if line.startswith('p cnf'):
            format_type = 'cnf'
            break
        elif line.startswith('p edge'):
            format_type = 'edge'
            break
        elif line and not line.startswith('c') and not line.startswith('#'):
            format_type = 'simple'
            break

    if format_type is None:
        format_type = 'simple'

    if format_type == 'cnf':
        return read_cnf(lines)
    elif format_type == 'edge':
        return read_dimacs_graph(lines)
    else:
        return read_simple(lines)


def read_simple(lines):
    """Read simple format: n k, then edges u v."""
    first_line = lines[0].strip().split()
    n = int(first_line[0])
    k = int(first_line[1])

    edges = []
    for line in lines[1:]:
        line = line.strip()
        if line and not line.startswith('#'):
            parts = line.split()
            if len(parts) >= 2:
                u, v = int(parts[0]), int(parts[1])
                edges.append((u, v))

    return edges, n, k


def read_dimacs_graph(lines):
    """Read DIMACS graph format: p edge <nodes> <edges>, e u v."""
    edges = []
    num_nodes = None
    n = None
    k = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('c'):
            parts = line.split()
            if len(parts) >= 3:
                if parts[1] == 'n':
                    n = int(parts[2])
                elif parts[1] == 'k':
                    k = int(parts[2])
            continue

        parts = line.split()
        if not parts:
            continue

        if parts[0] == 'p' and parts[1] == 'edge':
            num_nodes = int(parts[2])
        elif parts[0] == 'e':
            u, v = int(parts[1]), int(parts[2])
            edges.append((u - 1, v - 1))  # Convert 1-indexed to 0-indexed

    if n is None and num_nodes is not None:
        n = num_nodes // 2
    if k is None:
        k = len(edges)

    if n is None:
        raise ValueError("Could not determine n from DIMACS file")

    return edges, n, k


def read_cnf(lines):
    """Read DIMACS CNF format (not supported - CNF files cannot be read back)."""
    raise ValueError(
        "Reading CNF files is not supported.\n"
        "This script only writes CNF output.\n"
        "Use DIMACS graph format or simple format for input."
    )


def encode(edges, n, k):
    """
    Encode the graph partitioning problem as CNF formula.

    Variables:
      - x_i (node variables): node i is in set U
      - e_j (edge variables): edge j crosses between U and W

    Returns: (cnf, nr_vars) where cnf is list of clauses
    """
    # Normalize edges: remove duplicates, self-loops, sort
    normalized_edges = set()
    for u, v in edges:
        if u != v:
            normalized_edges.add((min(u, v), max(u, v)))
    edges = sorted(list(normalized_edges))

    num_nodes = 2 * n
    clauses = []
    var_map = {}
    num_vars = 0

    # Variable creation helpers
    def node_var(i):
        if ('node', i) not in var_map:
            nonlocal num_vars
            num_vars += 1
            var_map[('node', i)] = num_vars
        return var_map[('node', i)]

    def edge_var(edge_idx):
        if ('edge', edge_idx) not in var_map:
            nonlocal num_vars
            num_vars += 1
            var_map[('edge', edge_idx)] = num_vars
        return var_map[('edge', edge_idx)]

    # Encode edge crossing constraints: e_j <=> (x_u XOR x_v)
    for idx, (u, v) in enumerate(edges):
        e = edge_var(idx)
        xu = node_var(u)
        xv = node_var(v)

        # Both in same set => edge doesn't cross
        clauses.append([xu, xv, -e])
        clauses.append([-xu, -xv, -e])
        # Different sets => edge crosses
        clauses.append([xu, -xv, e])
        clauses.append([-xu, xv, e])

    # Encode partition size: exactly n nodes in U
    node_vars = [node_var(i) for i in range(num_nodes)]
    clauses.extend(cardinality_constraint(node_vars, n, num_vars, var_map))
    num_vars = max(var_map.values()) if var_map else 0

    negated_vars = [-v for v in node_vars]
    clauses.extend(cardinality_constraint(negated_vars, n, num_vars, var_map))
    num_vars = max(var_map.values()) if var_map else 0

    # Encode crossing edges bound: at most k edges cross
    edge_vars = [edge_var(i) for i in range(len(edges))]
    if edge_vars:
        clauses.extend(cardinality_constraint(edge_vars, k, num_vars, var_map))
        num_vars = max(var_map.values()) if var_map else 0

    return (clauses, num_vars, var_map, edges)


def cardinality_constraint(literals, k, num_vars_base, var_map):
    """
    Encode "at most k of literals are true" using sequential counter encoding.

    Uses counter variables s[i][j] representing "at least j+1 of first i+1 literals are true"
    Returns list of clauses.
    """
    clauses = []
    m = len(literals)

    if k >= m:
        return clauses

    if k == 0:
        for lit in literals:
            clauses.append([-lit])
        return clauses

    counter = {}
    counter_var_idx = [num_vars_base]

    def get_counter(i, j):
        if ('counter', i, j) not in counter:
            counter_var_idx[0] += 1
            counter[('counter', i, j)] = counter_var_idx[0]
            var_map[('counter', i, j)] = counter_var_idx[0]
        return counter[('counter', i, j)]

    # Base case
    clauses.append([-literals[0], get_counter(0, 0)])
    for j in range(1, k):
        clauses.append([-get_counter(0, j)])

    # Recursive case
    for i in range(1, m):
        clauses.append([-literals[i], get_counter(i, 0)])
        clauses.append([-get_counter(i - 1, 0), get_counter(i, 0)])

        for j in range(1, k):
            clauses.append([-get_counter(i - 1, j), get_counter(i, j)])
            clauses.append([-literals[i], -get_counter(i - 1, j - 1), get_counter(i, j)])

        clauses.append([-literals[i], -get_counter(i - 1, k - 1)])

    return clauses


def call_solver(cnf, nr_vars, output_name, solver_name, verbosity):
    """
    Write CNF to file in DIMACS format and call the SAT solver.
    Returns the subprocess result.
    """
    with open(output_name, "w") as f:
        f.write("p cnf " + str(nr_vars) + " " + str(len(cnf)) + '\n')
        for clause in cnf:
            # Each clause is a list of integers, add 0 terminator
            f.write(' '.join(str(lit) for lit in clause) + ' 0\n')

    return subprocess.run(
        [solver_name, '-model', '-verb=' + str(verbosity), output_name],
        stdout=subprocess.PIPE
    )


def decode_solution(result, n, var_map, edges):
    """
    Parse the solver output and decode the graph partition.

    Returns: (satisfiable, set_U, set_W, crossing_edges)
    """
    # Check SAT/UNSAT
    if result.returncode == 20:  # UNSAT
        return False, None, None, None

    # Parse model
    model = []
    for line in result.stdout.decode('utf-8').split('\n'):
        if line.startswith("v"):
            vars = line.split(" ")
            vars.remove("v")
            model.extend(int(v) for v in vars)

    if 0 in model:
        model.remove(0)

    # Decode partition
    set_U = set()
    set_W = set()

    for i in range(2 * n):
        var_key = ('node', i)
        if var_key in var_map:
            var = var_map[var_key]
            if model[var - 1] > 0:
                set_U.add(i)
            else:
                set_W.add(i)

    # Compute crossing edges
    crossing_edges = []
    for u, v in edges:
        u_in_U = u in set_U
        v_in_U = v in set_U
        if u_in_U != v_in_U:
            crossing_edges.append((u, v))

    return True, set_U, set_W, crossing_edges


def print_result(result, n, k, var_map, edges, verbose):
    """Print the result in human-readable format."""

    if verbose:
        for line in result.stdout.decode('utf-8').split('\n'):
            print(line)
        print()

    satisfiable, set_U, set_W, crossing = decode_solution(result, n, var_map, edges)

    if not satisfiable:
        print("UNSATISFIABLE")
        return

    print("SATISFIABLE")
    print(f"U: {sorted(set_U)}")
    print(f"W: {sorted(set_W)}")
    print(f"Crossing edges: {len(crossing)}")

    if verbose:
        print("############[ Detailed solution for graph partition ]############")
        print()
        print(f"Set U ({len(set_U)} nodes): {sorted(set_U)}")
        print(f"Set W ({len(set_W)} nodes): {sorted(set_W)}")
        print(f"Crossing edges ({len(crossing)}/{k} allowed):")
        if crossing:
            for u, v in sorted(crossing):
                print(f"  {u} -- {v}")
        else:
            print("  (none)")
        print()
        print("Verification:")
        print(f"  |U| = {len(set_U)}, expected {n}: {'+' if len(set_U) == n else '-'}")
        print(f"  |W| = {len(set_W)}, expected {n}: {'+' if len(set_W) == n else '-'}")
        print(f"  Crossings = {len(crossing)}, max {k}: {'+' if len(crossing) <= k else '-'}")


def find_solver():
    """Auto-detect Glucose executable."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(script_dir, "glucose-main", "simp", "glucose"),
        os.path.join(script_dir, "glucose-main", "glucose"),
        os.path.join(script_dir, "glucose"),
    ]

    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    # Check PATH
    found = shutil.which("glucose")
    if found:
        return found

    return None


if __name__ == "__main__":
    parser = ArgumentParser(description="Graph Partitioning SAT Solver using Glucose 4.2")

    parser.add_argument("-i", "--input", type=str,
                        help="The instance file")
    parser.add_argument("-o", "--output", default="formula.cnf", type=str,
                        help="Output file for the DIMACS CNF formula")
    parser.add_argument("-s", "--solver", default=None, type=str,
                        help="The SAT solver to be used")
    parser.add_argument("-v", "--verb", default=0, type=int, choices=range(0, 2),
                        help="Verbosity of the SAT solver")
    parser.add_argument("--print-cnf", action='store_true',
                        help="Print the CNF formula in DIMACS format")
    parser.add_argument("--stats", action='store_true',
                        help="Print statistics about the encoding and solver execution")
    parser.add_argument("--n", type=int, help="Half the number of nodes (for command line input)")
    parser.add_argument("--k", type=int, help="Maximum crossing edges (for command line input)")
    parser.add_argument("--edges", type=str, help="Edges as 'u1,v1 u2,v2 ...'")

    args = parser.parse_args()

    # Interactive mode when no arguments provided
    if not args.input and not args.n:
        print("Graph Partitioning Problem - SAT Solver")
        print("=" * 50)
        print()
        print("Enter n (half the number of nodes):")
        try:
            n = int(input().strip())
        except (ValueError, EOFError):
            print("Error: Invalid input")
            sys.exit(1)

        print("Enter k (maximum crossing edges):")
        try:
            k = int(input().strip())
        except (ValueError, EOFError):
            print("Error: Invalid input")
            sys.exit(1)

        print()
        print(f"Graph has {2 * n} nodes (indexed 0 to {2 * n - 1})")
        print("Enter edges, one per line as 'u v'")
        print("Finish with empty line:")
        edges = []
        while True:
            try:
                line = input().strip()
                if not line:
                    break
                parts = line.split()
                if len(parts) >= 2:
                    edges.append((int(parts[0]), int(parts[1])))
            except (ValueError, EOFError):
                break

        print()

    # Get input from arguments
    elif args.input:
        edges, n, k = load_instance(args.input)
    elif args.n is not None and args.k is not None:
        n = args.n
        k = args.k
        if args.edges is not None:
            edges = []
            if args.edges:  # Only parse if not empty string
                for edge_str in args.edges.split():
                    u, v = map(int, edge_str.split(','))
                    edges.append((u, v))
        else:
            # Interactive input
            edges = []
            while True:
                try:
                    line = input().strip()
                    if not line:
                        break
                    parts = line.split()
                    if len(parts) >= 2:
                        edges.append((int(parts[0]), int(parts[1])))
                except EOFError:
                    break
    else:
        print("Error: Provide --input FILE or (--n N --k K [--edges EDGES])")
        sys.exit(1)

    # Find solver
    if args.solver is None:
        args.solver = find_solver()
        if args.solver is None:
            print("Error: Could not find Glucose solver")
            sys.exit(1)

    # Encode the problem
    cnf, nr_vars, var_map, normalized_edges = encode(edges, n, k)

    # Print CNF formula if requested
    if args.print_cnf:
        print("##################[ CNF Formula in DIMACS Format ]################")
        print()
        print(f"p cnf {nr_vars} {len(cnf)}")
        for clause in cnf:
            print(' '.join(str(lit) for lit in clause) + ' 0')
        print()

    # Print encoding statistics if requested
    if args.stats:
        print("#####################[ Encoding Statistics ]######################")
        print()
        print(f"Graph:")
        print(f"  Nodes: {2 * n}")
        print(f"  Edges: {len(normalized_edges)}")
        print(f"  Max crossing edges (k): {k}")
        print()
        print(f"CNF Formula:")
        print(f"  Variables: {nr_vars}")
        print(f"  Clauses: {len(cnf)}")
        print()

        # Count variable types
        node_vars = sum(1 for key in var_map.keys() if key[0] == 'node')
        edge_vars = sum(1 for key in var_map.keys() if key[0] == 'edge')
        counter_vars = sum(1 for key in var_map.keys() if key[0] == 'counter')

        print(f"Variable breakdown:")
        print(f"  Node variables (x_i): {node_vars}")
        print(f"  Edge variables (e_j): {edge_vars}")
        print(f"  Counter variables (cardinality): {counter_vars}")
        print()

    # Call solver
    result = call_solver(cnf, nr_vars, args.output, args.solver, args.verb)

    # Print solver statistics if requested
    if args.stats:
        print("######################[ Solver Statistics ]#######################")
        print()

        # Parse solver output for statistics
        output = result.stdout.decode('utf-8')
        for line in output.split('\n'):
            if 'conflicts' in line.lower() or 'decisions' in line.lower() or 'propagations' in line.lower() or 'CPU time' in line:
                if line.startswith('c'):
                    print(line)
        print()

    # Print result
    print_result(result, n, k, var_map, normalized_edges, args.verb > 0)