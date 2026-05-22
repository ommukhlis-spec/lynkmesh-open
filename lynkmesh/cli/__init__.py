"""LynkMesh public CLI package (research preview / early validation).

This package provides the local-first, deterministic command-line surface for
LynkMesh. It is intentionally small. The only command implemented in this stage
is ``doctor`` (environment diagnostics). Graph-building commands are not part of
this package yet.

The entry point lives at ``lynkmesh.cli.main.main``. We deliberately do not
re-export it at the package level so that ``lynkmesh.cli.main`` always refers to
the submodule (avoiding an attribute/submodule name collision).
"""

__all__ = []
