from __future__ import annotations

import tarfile
import os
from datetime import datetime
from pathlib import Path


EXCLUDE_DIR_NAMES = {"node_modules", "dist", "venv", "__pycache__", "data", ".git"}
EXCLUDE_PREFIXES = ("frontend/node_modules/", "frontend/dist/", "backend/venv/", "data/", ".git/")


def should_exclude(rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/")
    return any(rel == p.rstrip("/") or rel.startswith(p) for p in EXCLUDE_PREFIXES)


def main() -> None:
    root = Path(__file__).resolve().parent
    out = root.parent / f"nova_source_backup_{datetime.now():%Y%m%d_%H%M%S}.tar.gz"

    with tarfile.open(out, "w:gz") as tar:
        for dirpath, dirnames, filenames in os.walk(root):
            # prune heavy/generated directories early
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]

            for filename in filenames:
                path = Path(dirpath) / filename
                rel = path.relative_to(root).as_posix()
                if should_exclude(rel):
                    continue
                tar.add(path, arcname=rel, recursive=False)

    print(out.as_posix())


if __name__ == "__main__":
    main()
