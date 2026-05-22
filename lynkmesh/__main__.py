"""Enable ``python -m lynkmesh``.

Delegates to the public CLI entry point in ``lynkmesh.cli.main``.
"""

from lynkmesh.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
