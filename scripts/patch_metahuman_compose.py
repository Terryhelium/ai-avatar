from __future__ import annotations

import base64
import os
import re
from pathlib import Path


def main() -> None:
    compose_path = Path(
        os.getenv("METAHUMAN_COMPOSE_PATH", "/opt/metahuman-stream/docker-compose.yml")
    )
    patch_script_path = Path(
        os.getenv("METAHUMAN_INIT_SCRIPT_PATH", "/opt/metahuman-stream/init_metahuman.py")
    )

    compose_text = compose_path.read_text(encoding="utf-8")
    patch_script = patch_script_path.read_text(encoding="utf-8")
    encoded = base64.b64encode(patch_script.encode("utf-8")).decode("ascii")

    pattern = re.compile(r"echo '([^']+)' \| base64 -d \| python &&")
    updated, replacements = pattern.subn(f"echo '{encoded}' | base64 -d | python &&", compose_text, count=1)
    if replacements != 1:
        raise SystemExit("embedded init script marker not found")

    compose_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
