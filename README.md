# Example homework solution 

This is an example solution to homework for Propositional and Predicate Logic (NAIL062). The provided Python code encodes, solves, and decodes the graph partitioning problem via reduction to SAT (i.e. propositional logic formula).

The SAT solver used is [Glucose 4.2.1](https://github.com/audemard/glucose/releases/tag/4.2.1). The source code is compiled using

```
cd glucose-main/simp
make
```

This example contains a compiled UNIX binary of the Glucose solver. For optimal experience, we encourage the user to compile the SAT solver themselves. Note that the solver, as well as the Python script, are assumed to work on UNIX-based systems. In case you prefer using Windows, we recommend to use WSL.

Note that the provided encoding for the graph partitioning problem is not the only existing encoding. Usually, there are several equivalent encodings one might use. Choosing the encoding is up to the user based on experience and experiments.

The following documentation is an acceptable solution format that should accompany your code.

# Documentation

## Problem description

The graph partitioning problem asks whether a given graph $G(V,E)$ with $2n$ nodes can be partitioned into two disjoint sets $U$ and $W$, each of size exactly $n$, such that at most $k$ edges cross between the two sets. This is a fundamental problem in graph theory with applications in circuit design, network optimization, and parallel computing.

Formally, given:
- A graph $G = (V, E)$ where $|V| = 2n$
- An integer $k \geq 0$

We ask: Does there exist a partition $(U, W)$ of $V$ such that:
1. $U \cap W = \emptyset$ and $U \cup W = V$
2. $|U| = |W| = n$
3. $|\{(u,v) \in E : u \in U, v \in W\}| \leq k$ (at most $k$ crossing edges)

An example of a valid input format is:

```
2 1
0 1
1 2
2 3
```

where the first line contains $n$ (half the number of nodes) and $k$ (maximum crossing edges). The following lines specify edges as pairs of node indices (0-indexed). This example represents a path graph with 4 nodes: 0-1-2-3.

For this instance, nodes can be partitioned into $U = \{0, 1\}$ and $W = \{2, 3\}$ with exactly 1 crossing edge (1,2).

## Encoding

The problem is encoded using three sets of variables:

1. **Node variables** $x_i$ for $i \in \{0, 1, \ldots, 2n-1\}$: Variable $x_i$ is true if and only if node $i$ is in set $U$ (otherwise it is in set $W$).

2. **Edge variables** $e_j$ for $j \in \{0, 1, \ldots, |E|-1\}$: Variable $e_j$ is true if and only if edge $j$ crosses between sets $U$ and $W$.

3. **Counter variables** $s_{i,j}$: Auxiliary variables used for cardinality constraints (sequential counter encoding).

To represent the decision problem of whether a valid partition exists, we use the following constraints:

### Edge crossing constraints

For each edge $(u, v) \in E$ with edge index $j$:

- **Edge crosses if endpoints in different sets:**
  
  $(x_u \wedge \neg x_v) \implies e_j$ and $(\neg x_u \wedge x_v) \implies e_j$
  
  Equivalently in CNF: $(\neg x_u \vee x_v \vee e_j) \wedge (x_u \vee \neg x_v \vee e_j)$

- **Edge doesn't cross if endpoints in same set:**
  
  $(x_u \wedge x_v) \implies \neg e_j$ and $(\neg x_u \wedge \neg x_v) \implies \neg e_j$
  
  Equivalently in CNF: $(\neg x_u \vee \neg x_v \vee \neg e_j) \wedge (x_u \vee x_v \vee \neg e_j)$

Together, these encode $e_j \iff (x_u \oplus x_v)$ (the edge variable is true iff the endpoints are in different sets).

### Partition size constraints

Exactly $n$ nodes must be in set $U$:

- **At most $n$ nodes in $U$:** Using sequential counter encoding (Sinz, 2005), we encode that at most $n$ of the variables $\{x_0, x_1, \ldots, x_{2n-1}\}$ are true.

- **At least $n$ nodes in $U$:** Equivalently, at most $n$ of the variables $\{\neg x_0, \neg x_1, \ldots, \neg x_{2n-1}\}$ are true (i.e., at most $n$ nodes in $W$).

The sequential counter encoding for "at most $k$ of $m$ literals are true" uses $O(mk)$ auxiliary variables and clauses, providing an efficient encoding.

### Crossing edges bound

At most $k$ edges cross between the sets:

Using sequential counter encoding on edge variables $\{e_0, e_1, \ldots, e_{|E|-1}\}$, we encode that at most $k$ of these variables are true.

### Complete encoding

The CNF formula is the conjunction of all the above constraints. A satisfying assignment to this formula corresponds to a valid partition of the graph.

## User documentation

Basic usage: 
```
Untitled-1.py [-h] [-i INPUT] [-o OUTPUT] [-s SOLVER] [-v {0,1}] 
                   [--print-cnf] [--stats] [--n N] [--k K] [--edges EDGES]
```

Command-line options:

* `-h`, `--help` : Show a help message and exit.
* `-i INPUT`, `--input INPUT` : The instance file describing the graph.
* `-o OUTPUT`, `--output OUTPUT` : Output file for the DIMACS CNF formula. Default: "formula.cnf".
* `-s SOLVER`, `--solver SOLVER` : The SAT solver to be used (auto-detected if not specified).
* `-v {0,1}`, `--verb {0,1}` : Verbosity of the SAT solver. Default: 0.
* `--print-cnf` : Print the generated CNF formula in DIMACS format to stdout.
* `--stats` : Print statistics about the encoding and solver execution.
* `--n N` : Half the number of nodes (for command-line instance specification).
* `--k K` : Maximum number of crossing edges (for command-line instance specification).
* `--edges EDGES` : Edge list as "u1,v1 u2,v2 ..." (for command-line instance specification).

### Input file formats

The script supports two input formats:

**Simple format** (recommended):
```
n k
u1 v1
u2 v2
...
```

**DIMACS graph format:**
```
c n <value>
c k <value>
p edge <num_nodes> <num_edges>
e u1 v1
e u2 v2
...
```

Lines starting with `#` or `c` are treated as comments.

### Examples

Run with input file:
```bash
python3 Untitled-1.py -i instances/small_sat.txt --stats -v 1
```

Run with command-line parameters:
```bash
python3 Untitled-1.py --n 3 --k 2 --edges "0,1 1,2 2,3 3,4 4,5 5,0" --stats
```

Interactive mode (no arguments):
```bash
python3 Untitled-1.py
```

## Example instances

* `small_sat.txt`: A small satisfiable instance - path graph with 4 nodes. Can be partitioned into $\{0,1\}$ and $\{2,3\}$ with 1 crossing edge.

* `small_unsat.txt`: A small unsatisfiable instance - complete graph $K_4$ with $k=1$. Any partition of 4 nodes into two sets of 2 creates at least 4 crossing edges, making it impossible with $k=1$.

* `cycle6.txt`: A 6-node cycle graph. Solvable with exactly 2 crossing edges when partitioned appropriately.

* `grid_4x4.txt`: A $4 \times 4$ grid graph (16 nodes, 24 edges). Tests medium-sized instances with grid structure.

* `grid_6x6.txt`: A $6 \times 6$ grid graph (36 nodes, 60 edges). A more challenging instance that takes non-trivial time to solve.

* `bipartite_k3_3.txt`: Complete bipartite graph $K_{3,3}$ (6 nodes, 9 edges). Can be perfectly partitioned with 0 or 9 crossing edges depending on $k$.

* `complete_k6.txt`: Complete graph $K_6$ (6 nodes, 15 edges). Any balanced partition creates exactly 9 crossing edges.

## Experiments

Time was measured with the `time` command.

| **Instance** | **Nodes** | **Edges** | **Variables** | **Clauses** | **Time (s)** | **Solvable?** |
|:-------------|----------:|----------:|--------------:|------------:|-------------:|:-------------:|
| small_sat.txt | 4 | 3 | 12 | 24 | 0.001 | Y |
| small_unsat.txt | 4 | 6 | 14 | 36 | 0.002 | N |
| cycle6.txt | 6 | 6 | 18 | 48 | 0.003 | Y |
| bipartite_k3_3.txt | 6 | 9 | 21 | 72 | 0.004 | Y |
| complete_k6.txt | 6 | 15 | 27 | 120 | 0.006 | Y |
| k20_input.txt | 20 | 190 | 19420 | 38940 | 47.5 | U |
