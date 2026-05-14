# lynkmesh/graph/graph_enricher.py
"""
Graph Enricher - Adds specialized edges to the knowledge graph.

Currently wraps the legacy UnifiedCallGraphEngine for HTTP/route connections,
but is designed to host additional enrichment strategies in the future.
"""

import logging
from typing import Dict, Any, List

from lynkmesh.core.graph_core import GraphCore

logger = logging.getLogger(__name__)


class GraphEnricher:
    """
    Enhances an existing graph with additional semantic edges.

    Responsibilities:
    - Detect and link HTTP routes to controller methods
    - Handle framework-specific call patterns (Laravel, Symfony, etc.)
    - Bridge legacy enrichment logic without polluting GraphBuilder

    The enrichment is purely additive and does not modify existing nodes/edges.
    """

    def __init__(self, enable_http_linking: bool = True):
        self.enable_http_linking = enable_http_linking

    def enrich(self, graph: GraphCore) -> GraphCore:
        """
        Apply all active enrichment strategies and return the enhanced graph.
        """
        logger.info("[GraphEnricher] Starting graph enrichment...")
        initial_stats = graph.stats()
        graph_dict = graph.to_dict()
        added_edges = 0

        # ------------------------------------------------------------------
        # HTTP / Route Linking (Legacy UnifiedCallGraphEngine)
        # ------------------------------------------------------------------
        if self.enable_http_linking:
            try:
                from lynkmesh.legacy.graph.unified_call_graph_engine import (
                    UnifiedCallGraphEngine,
                )

                # Bridge: dict → legacy engine
                engine = UnifiedCallGraphEngine(graph_dict)
                new_edges = engine.run()  # returns list of edge dicts

                if new_edges:
                    # Ensure we have a mutable edge list
                    edges = graph_dict.get("edges", [])
                    # Filter out duplicates based on (from, to, type)
                    existing_keys = {(e["from"], e["to"], e["type"]) for e in edges}
                    for edge in new_edges:
                        key = (edge["from"], edge["to"], edge["type"])
                        if key not in existing_keys:
                            edges.append(edge)
                            existing_keys.add(key)
                            added_edges += 1

                    graph_dict["edges"] = edges
                    logger.info(f"      Added {added_edges} HTTP/route edges")
                else:
                    logger.info("      No HTTP edges added (legacy engine returned nothing)")

            except ImportError:
                logger.warning("Legacy UnifiedCallGraphEngine not available, skipping HTTP linking.")
            except Exception as e:
                logger.error(f"Legacy enrichment failed: {e}")

        # ------------------------------------------------------------------
        # Rehydrate GraphCore and return
        # ------------------------------------------------------------------
        enriched_graph = GraphCore.from_dict(graph_dict)
        final_stats = enriched_graph.stats()
        logger.info(
            f"[GraphEnricher] Enrichment complete. "
            f"Added {final_stats['edges'] - initial_stats['edges']} total edges."
        )
        return enriched_graph