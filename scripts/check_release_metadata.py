from __future__ import annotations

import json

from agent_memory.release_metadata import validate_release_metadata


if __name__ == "__main__":
    metadata = validate_release_metadata()
    print(
        json.dumps(
            {
                "python_package_name": metadata.python_package_name,
                "python_package_version": metadata.python_package_version,
                "npm_package_name": metadata.npm_package_name,
                "npm_package_version": metadata.npm_package_version,
                "module_version": metadata.module_version,
            },
            indent=2,
        )
    )
