# Module: `agent_tracer_plus.graph.builder`

Auto Dependency Graph Builder for Agent Tracer Plus.

## Class `DependencyGraph`
Represents a topological dependency graph of agents and tools using networkx.

### `def __init__(self)`
### `def add_node(self, node, node_type)`
### `def add_edge(self, source, target, weight, relationship)`
### `def has_cycles(self)`
Check if the dependency graph has cycles (e.g., infinite loops between tools).

### `def get_bottlenecks(self)`
Find the most critical nodes based on betweenness centrality.

### `def to_graphml(self)`
Export the graph as GraphML for UI rendering engines like Cytoscape.

### `def to_mermaid(self)`
Export the graph as a Mermaid.js flowchart string.

