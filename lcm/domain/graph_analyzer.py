import networkx as nx


class GraphAnalyzer:
    """Enriches graphs with domain-specific metrics (leakage, termination, etc.)."""

    def enrich_graph_with_metrics(
        self, G: nx.MultiDiGraph, knockout_threshold: float = 0.5
    ) -> nx.MultiDiGraph:
        leakage_gt_0_count = 0
        terminal_count = 0
        G_enriched = G.copy()
        for node in G_enriched.nodes():
            incoming_weight = sum(
                G_enriched.edges[pred, node, key]["weight"]
                for pred in G_enriched.predecessors(node)
                for key in G_enriched[pred][node]
            )
            outgoing_weight = sum(
                G_enriched.edges[node, succ, key]["weight"]
                for succ in G_enriched.successors(node)
                for key in G_enriched[node][succ]
            )
            weight = G_enriched.nodes[node].get("weight", 0)
            leakage = incoming_weight - outgoing_weight
            terminated_cases = weight - outgoing_weight
            termination_ratio = terminated_cases / weight if weight > 0 else 0

            G_enriched.nodes[node]["metrics"] = {
                "incoming_flow": incoming_weight,
                "outgoing_flow": outgoing_weight,
                "leakage": leakage,
                "termination_ratio": termination_ratio,
                "is_balanced": incoming_weight == outgoing_weight,
                "is_terminal": termination_ratio >= knockout_threshold,
            }
            if leakage > 0:
                leakage_gt_0_count += 1
            if termination_ratio >= knockout_threshold:
                terminal_count += 1
        G_enriched.graph["leakage_gt_0_count"] = leakage_gt_0_count
        G_enriched.graph["terminal_count"] = terminal_count
        return G_enriched
