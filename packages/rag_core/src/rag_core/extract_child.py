"""Isolated parser entry point. No uploaded content is executed."""

import json
import sys
from pathlib import Path

from rag_core.errors import PlatformError
from rag_core.extraction import extract


def main() -> None:
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (1_073_741_824, 1_073_741_824))
    source, output, filename, checksum, characters, pages = sys.argv[1:]
    try:
        result = {
            "extraction": extract(
                Path(source), filename, checksum, int(characters), int(pages)
            ).model_dump()
        }
    except PlatformError as error:
        result = {"error": {"code": error.code, "message": error.message}}
    except Exception:
        result = {"error": {"code": "extraction_failed", "message": "Document extraction failed."}}
    target = Path(output)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


if __name__ == "__main__":
    main()
