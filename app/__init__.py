"""Synapse backend application package."""

import logging
import os
import subprocess
import sys
import sysconfig
from pathlib import Path


def _ensure_prisma_client_generated() -> None:
    """Generate the Prisma client when the generated Python package is missing."""
    project_root = Path(__file__).resolve().parent.parent
    site_packages = Path(sysconfig.get_paths()["purelib"])
    generated_client = site_packages / "prisma" / "models.py"

    if generated_client.exists():
        return

    logger = logging.getLogger(__name__)
    logger.info("Prisma client is missing; running `python -m prisma generate`.")

    bin_dir = Path(sys.executable).resolve().parent
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    }

    try:
        subprocess.run([sys.executable, "-m", "prisma", "generate"], cwd=project_root, check=True, env=env)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Prisma client is missing and the Prisma CLI is not available. "
            "Run `python -m prisma generate` in the backend directory."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Prisma client generation failed. Run `python -m prisma generate` in the backend directory to inspect the error."
        ) from exc


_ensure_prisma_client_generated()

if __name__ == "__main__":
    from pathlib import Path

    # Running this file sets sys.path[0] to app/; ensure project root is on path so `app.main` imports.
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
