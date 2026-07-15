"""Auto Dependency Graph Builder for Agent Tracer Plus."""

import json
from typing import Dict, Set, Optional, Any

from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.core.models import SpanType


class DependencyGraph:
    """Represents a topological dependency graph of agents and tools using networkx."""

    def __init__(self):
        try:
            import networkx as nx
            self.nx_graph = nx.DiGraph()
        except ImportError:
            self.nx_graph = None
            
        self.nodes: Set[str] = set()
        self.edges: Dict[str, Set[str]] = {}  # Source -> set of Targets
        self.node_attributes: Dict[str, Dict[str, Any]] = {}

    def add_node(self, node: str, node_type: str = "tool", **kwargs):
        self.nodes.add(node)
        self.node_attributes[node] = {"type": node_type, **kwargs}
        if self.nx_graph is not None:
            self.nx_graph.add_node(node, type=node_type, **kwargs)

    def add_edge(self, source: str, target: str, weight: int = 1, relationship: str = "calls"):
        self.nodes.add(source)
        self.nodes.add(target)
        
        if source not in self.node_attributes:
            self.add_node(source)
        if target not in self.node_attributes:
            self.add_node(target)
            
        if source not in self.edges:
            self.edges[source] = set()
        self.edges[source].add(target)
        
        if self.nx_graph is not None:
            if self.nx_graph.has_edge(source, target):
                self.nx_graph[source][target]["weight"] += weight
            else:
                self.nx_graph.add_edge(source, target, weight=weight, relationship=relationship)

    def detect_cycles(self) -> list:
        """Return all cycles in the dependency graph (indicates infinite loops).
        
        Returns:
            List of cycles, where each cycle is a list of node names.
            Empty list means no cycles detected.
        """
        if self.nx_graph is None:
            return []
        import networkx as nx
        try:
            return list(nx.simple_cycles(self.nx_graph))
        except Exception:
            return []

    def has_cycles(self) -> bool:
        """Quick boolean check if any cycles exist."""
        return len(self.detect_cycles()) > 0

    def find_bottlenecks(self, top_n: int = 5) -> list:
        """Find the most critical nodes based on betweenness centrality.
        
        Returns list of dicts with node name, centrality score, and avg_duration_ms.
        """
        if self.nx_graph is None:
            return []
        import networkx as nx
        centrality = nx.betweenness_centrality(self.nx_graph)
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        results = []
        for node, score in sorted_nodes[:top_n]:
            attrs = self.node_attributes.get(node, {})
            results.append({
                "node": node,
                "centrality_score": round(score, 4),
                "node_type": attrs.get("type", "unknown"),
                "avg_duration_ms": attrs.get("avg_duration_ms", None),
                "call_count": attrs.get("call_count", None),
            })
        return results

    def to_graphml(self) -> str:
        """Export the graph as GraphML for UI rendering engines like Cytoscape."""
        if self.nx_graph is None:
            raise ImportError("networkx is required for GraphML export")
        import networkx as nx
        return "\n".join(nx.generate_graphml(self.nx_graph))

    def export_dot(self) -> str:
        """Export the graph as Graphviz DOT format."""
        if self.nx_graph is None:
            raise ImportError("networkx is required for DOT export")
        import networkx as nx
        lines = []
        for line in nx.generate_networkx_drawing(self.nx_graph):
            pass # We'll just build it manually to avoid pydot dependency
        
        lines = ["digraph DependencyGraph {"]
        for node in self.nodes:
            clean_name = node.replace('"', '')
            lines.append(f'  "{clean_name}";')
        for source, targets in self.edges.items():
            for target in targets:
                clean_src = source.replace('"', '')
                clean_tgt = target.replace('"', '')
                lines.append(f'  "{clean_src}" -> "{clean_tgt}";')
        lines.append("}")
        return "\n".join(lines)

    def export_mermaid(self) -> str:
        """Export the graph as a Mermaid.js flowchart string."""
        lines = ["graph TD;"]

        # Define nodes with styling based on name hinting
        for node in self.nodes:
            clean_name = node.replace('"', '').replace('(', '').replace(')', '')
            node_type = self.node_attributes.get(node, {}).get("type", "tool")
            
            if node_type == "llm" or "LLM" in clean_name or "gpt" in clean_name.lower():
                shape = f'{clean_name}("{clean_name}"):::llm'
            elif node_type == "agent" or "Agent" in clean_name:
                shape = f'{clean_name}("{clean_name}"):::agent'
            else:
                shape = f'{clean_name}("{clean_name}"):::tool'
            lines.append(f"  {shape}")

        # Define edges
        for source, targets in self.edges.items():
            for target in targets:
                clean_src = source.replace('"', '')
                clean_tgt = target.replace('"', '')
                
                weight = 1
                if self.nx_graph is not None and self.nx_graph.has_edge(source, target):
                    weight = self.nx_graph[source][target].get("weight", 1)
                
                # If it's a heavy edge, make it thicker
                if weight > 10:
                    lines.append(f"  {clean_src} ==>|{weight} calls| {clean_tgt}")
                else:
                    lines.append(f"  {clean_src} --> {clean_tgt}")

        # Add basic classes
        lines.append("  classDef agent fill:#8b5cf6,stroke:#fff,stroke-width:2px,color:#fff;")
        lines.append("  classDef llm fill:#3b82f6,stroke:#fff,stroke-width:2px,color:#fff;")
        lines.append("  classDef tool fill:#f59e0b,stroke:#fff,stroke-width:2px,color:#fff;")

        return "\n".join(lines)


async def build_dependency_graph(limit: int = 100) -> DependencyGraph:
    """Scan recent traces and build a dependency graph of span relationships."""
    tracer = get_tracer()
    if not tracer:
        raise RuntimeError("Tracer not initialized")

    traces_data = await tracer.query(limit=limit)
    graph = DependencyGraph()

    for t_data in traces_data:
        trace_id = t_data.get("trace_id")
        if not trace_id:
            continue

        spans = await tracer.get_spans(trace_id)
        if not spans:
            continue

        # Map span_id -> Span for quick lookup
        span_map = {s.span_id: s for s in spans}

        for span in spans:
            node_type = "llm" if span.span_type == SpanType.LLM else "agent" if span.span_type == SpanType.AGENT else "tool"
            graph.add_node(span.name, node_type=node_type)

            # If it has a parent, draw edge from Parent -> Child (Execution lineage)
            if span.parent_span_id and span.parent_span_id in span_map:
                parent = span_map[span.parent_span_id]
                graph.add_edge(parent.name, span.name, relationship="calls")
                
            # If it's a root span (no parent) but has an agent_name, link trace agent -> span
            elif not span.parent_span_id and t_data.get("agent_name"):
                if t_data["agent_name"] != span.name:
                    graph.add_edge(t_data["agent_name"], span.name, relationship="calls")
                    
            # Data Lineage: If this is an LLM call, and there were previous RETRIEVAL spans in the same trace, 
            # draw a data lineage edge (Retrieval -> LLM)
            if span.span_type == SpanType.LLM:
                for other_span in spans:
                    if other_span.span_type in (SpanType.RETRIEVAL, SpanType.TOOL) and other_span.started_at < span.started_at:
                        # Only add data lineage if we know they are in the same parent context to avoid noise
                        if other_span.parent_span_id == span.parent_span_id:
                            graph.add_edge(other_span.name, span.name, relationship="feeds_data")

    return graph
