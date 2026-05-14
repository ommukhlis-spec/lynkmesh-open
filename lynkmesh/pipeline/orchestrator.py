# lynkmesh/pipeline/orchestrator.py
"""
Orchestrator - COO layer that wires together ingestion, graph building,
call resolution, enrichment, and validation. This is the central conductor.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from lynkmesh.ingestion.parser_engine import ParserEngine
from lynkmesh.ingestion.ir_normalizer import IRNormalizer
from lynkmesh.graph.graph_builder import GraphBuilder
from lynkmesh.graph.call_resolver import CallResolver  # 🔥 Kembali ke file monolitik
from lynkmesh.graph.graph_enricher import GraphEnricher
from lynkmesh.graph.graph_validator import GraphValidator
from lynkmesh.core.graph_core import GraphCore
from lynkmesh.core.graph_version import verify_pipeline_determinism

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Central orchestrator for the LynkMesh analysis pipeline.

    Responsibilities:
    - Execute ingestion (parse → normalize)
    - Build the structural graph
    - Resolve method calls (dependency tracing) using CallResolver
    - Enrich graph with HTTP/route links (via GraphEnricher)
    - Validate final graph integrity
    - Return a ready-to-use GraphCore instance
    """

    def __init__(
        self,
        use_parallel_parsing: bool = True,
        max_workers: int = 4,
        enable_http_enrichment: bool = True,
        export_propagation_debug: Optional[str] = None,
    ):
        """
        Args:
            use_parallel_parsing: Use ParallelParser (True) or fallback IREngine (False)
            max_workers: Number of parallel parser workers
            enable_http_enrichment: Whether to run GraphEnricher for HTTP/route linking
            export_propagation_debug: If set, export CallResolver propagation debug to this file
        """
        # Stage 3.0.0 — verify PYTHONHASHSEED=0 before any pipeline run.
        # Raises EnvironmentError if seed is missing or wrong; this is the
        # earliest point we can fail-fast on a misconfigured environment.
        verify_pipeline_determinism()

        self.use_parallel = use_parallel_parsing
        self.max_workers = max_workers
        self.enable_http_enrichment = enable_http_enrichment
        self.export_propagation_debug = export_propagation_debug
        self.resolver: Optional[CallResolver] = None

    @property
    def last_resolution_telemetry(self):
        """
        Sprint 2.7.A.1 (PR 2.b)

        Telemetry from latest resolver execution.
        """
        if self.resolver is None:
            return None
        return self.resolver.last_telemetry

    def run(self, project_path: str) -> GraphCore:
        """
        Execute the full ingestion → graph pipeline.

        Args:
            project_path: Absolute path to the codebase to analyze.

        Returns:
            A validated GraphCore instance ready for reasoning/export.
        """
        logger.info("=" * 60)
        logger.info("🚀 LynkMesh Orchestrator Started")
        logger.info(f"📁 Project: {project_path}")
        logger.info("=" * 60)

        project_path = str(Path(project_path).resolve())

        # ------------------------------------------------------------------
        # STEP 1 & 2: Ingestion (Parse + Normalize)
        # ------------------------------------------------------------------
        logger.info("[1/6] Ingestion: Parsing project...")
        parser = ParserEngine(max_workers=self.max_workers)
        raw_ast = parser.parse(project_path)
        if not raw_ast:
            raise RuntimeError("Ingestion failed: no AST produced.")
        logger.info(f"      Parsed {len(raw_ast)} files.")

        logger.info("[2/6] Ingestion: Normalizing IR...")
        normalizer = IRNormalizer()
        ir_list = normalizer.normalize(raw_ast)
        logger.info(f"      Normalized {len(ir_list)} IR units.")

        # ------------------------------------------------------------------
        # STEP 3: Structural Graph Construction
        # ------------------------------------------------------------------
        logger.info("[3/6] Graph: Building structural graph...")
        builder = GraphBuilder()
        graph = builder.build_from_ir(ir_list)
        stats_structural = graph.stats()
        logger.info(
            f"      Structural: {stats_structural['nodes']} nodes, {stats_structural['edges']} edges"
        )

        # Stage 3.0.0 — assign version metadata immediately after structural
        # build. content_hash is NOT yet computed (waits until finalization
        # at end of run()). This gives subsequent phases access to graph_id
        # / build_id for logging if needed.
        graph._assign_initial_metadata(
            project_path=project_path,
            git_commit=None,
        )

        # ------------------------------------------------------------------
        # STEP 4: Call Resolution (adds internal call edges)
        # ------------------------------------------------------------------
        logger.info("[4/6] Graph: Resolving method calls (dependency tracing)...")
        # Fallback if resolution fails – graph remains structural
        stats_resolved = stats_structural

        try:
            resolver = CallResolver()
            symbols = builder.get_symbol_registry()

            # ---- Hydrate TypeRegistry with parser-discovered return types ----
            # Menangani berbagai format yang mungkin dari parser:
            # 1) dict: {"Class::method": "ReturnType"}
            # 2) list of dicts: [{"method_fqn": "...", "return_type": "..."}]
            # 3) list of strings (format "Class::method" - tanpa return type, skip)
            loaded_returns = 0
            for ir in ir_list:
                method_returns = ir.get("method_return_types")
                if not method_returns:
                    continue

                # Format 1: dict
                if isinstance(method_returns, dict):
                    for full_method, return_type in method_returns.items():
                        if not isinstance(return_type, str):
                            continue
                        if "::" not in full_method:
                            continue
                        class_fqn, method_name = full_method.rsplit("::", 1)
                        resolver.type_registry.add_return_type(
                            class_fqn, method_name, return_type
                        )
                        loaded_returns += 1

                # Format 2: list of dicts
                elif isinstance(method_returns, list):
                    for entry in method_returns:
                        if not isinstance(entry, dict):
                            continue
                        # Berbagai nama field yang mungkin
                        fqn = (
                            entry.get("method_fqn")
                            or entry.get("fqn")
                            or entry.get("class")
                            or ""
                        )
                        method = (
                            entry.get("method")
                            or entry.get("name")
                            or entry.get("method_name")
                            or ""
                        )
                        rtype = (
                            entry.get("return_type")
                            or entry.get("type")
                            or entry.get("returns")
                        )
                        if not fqn or not method or not rtype:
                            continue
                        # Jika fqn sudah mengandung ::, pisahkan
                        if "::" in fqn:
                            class_fqn, method_name = fqn.rsplit("::", 1)
                        else:
                            class_fqn, method_name = fqn, method
                        resolver.type_registry.add_return_type(
                            class_fqn, method_name, rtype
                        )
                        loaded_returns += 1

            logger.info(
                f"      Loaded {loaded_returns} parser-discovered return types into TypeRegistry"
            )

            graph = resolver.resolve(graph, symbols)

            # Simpan resolver untuk export debug nanti
            self.resolver = resolver

            stats_resolved = graph.stats()
            logger.info(
                f"      After resolution: {stats_resolved['nodes']} nodes, {stats_resolved['edges']} edges"
            )
            logger.info(
                f"      Added {stats_resolved['edges'] - stats_structural['edges']} call edges"
            )

            # Ekspor debug propagation jika diminta
            if self.export_propagation_debug:
                resolver.export_debug(self.export_propagation_debug)
                resolver.debug_summary()

        except Exception as e:
            logger.error(f"Call resolution failed: {e}")
            logger.warning("⚠️ Graph will NOT contain behavioral edges (calls).")

        # ------------------------------------------------------------------
        # STEP 5: Graph Enrichment (HTTP/route linking, framework patterns)
        # ------------------------------------------------------------------
        if self.enable_http_enrichment:
            logger.info("[5/6] Graph: Enriching with HTTP/route links...")
            try:
                enricher = GraphEnricher(enable_http_linking=True)
                graph = enricher.enrich(graph)
                stats_enriched = graph.stats()
                added = stats_enriched['edges'] - stats_resolved.get('edges', 0)
                logger.info(
                    f"      After enrichment: {stats_enriched['nodes']} nodes, {stats_enriched['edges']} edges"
                )
                logger.info(f"      Added {added} enrichment edges")
            except Exception as e:
                logger.error(f"Graph enrichment failed: {e}")
        else:
            logger.info("[5/6] Graph: Enrichment disabled, skipping.")

        # ------------------------------------------------------------------
        # STEP 6: Validation
        # ------------------------------------------------------------------
        logger.info("[6/6] Graph: Validating integrity...")
        validator = GraphValidator()
        report = validator.validate(graph)

        if not report["valid"]:
            for err in report["errors"]:
                logger.error(f"❌ Validation Error: {err}")
            raise RuntimeError("Graph validation failed. See errors above.")

        if report["warnings"]:
            logger.warning(f"⚠️ {len(report['warnings'])} validation warnings (non‑fatal)")

        logger.info("=" * 60)
        logger.info("✅ Pipeline completed successfully.")
        final_stats = graph.stats()
        logger.info(f"📊 Final Graph: {final_stats['nodes']} nodes, {final_stats['edges']} edges")

        # Stage 3.0.0 — ensure version metadata is present on the final graph
        # object before computing content_hash. This is intentionally placed at
        # the finalization boundary because earlier pipeline phases may replace
        # or mutate the graph object.
        if getattr(graph, "_version_metadata", None) is None:
            graph._assign_initial_metadata(
                project_path=project_path,
                git_commit=None,
            )

        graph._finalize_content_hash()
        logger.info(f"📦 Graph version: {graph.version!r}")
        logger.info("=" * 60)

        return graph

    def run_and_export(self, project_path: str, output_format: str = "dict") -> Dict[str, Any]:
        """
        Run the pipeline and export the result in the requested format.

        Args:
            project_path: Path to the codebase.
            output_format: 'dict' (default), 'networkx', or 'cypher'.

        Returns:
            Graph representation in the chosen format.
        """
        graph = self.run(project_path)

        if output_format == "dict":
            return graph.to_dict()
        elif output_format == "networkx":
            from lynkmesh.graph.graph_mapper import GraphMapper
            mapper = GraphMapper()
            return mapper.to_networkx(graph)
        elif output_format == "cypher":
            from lynkmesh.graph.graph_mapper import GraphMapper
            mapper = GraphMapper()
            return {"cypher": mapper.to_cypher_script(graph)}
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def build_graph(self, project_path: str) -> GraphCore:
        """
        Build and return the knowledge graph without running full analysis.
        This is a convenience method for testing and tools that only need the graph.
        """
        logger.info("Building graph (lightweight mode)...")
        return self.run(project_path)