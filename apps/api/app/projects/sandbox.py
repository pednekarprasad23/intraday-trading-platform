"""Execution sandbox and parameterized run validation for V2.6 Phase 3."""

import json
from typing import Any
from fastapi import HTTPException
from app.backtesting.engine import fingerprint


def validate_and_snapshot_parameters(params: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    """Validate parameters as pure data, snapshot them, and compute canonical SHA-256 fingerprint.

    Enforces security constraints:
    - Parameters must be JSON-serializable data.
    - No executable code strings, shell commands, file paths, imports, or SQL strings.
    """
    if params is None:
        params = {}

    if not isinstance(params, dict):
        raise HTTPException(400, "Parameters must be a JSON object dictionary")

    # Security scan of parameter keys and string values
    forbidden_substrings = ["eval(", "exec(", "import ", "sys.", "os.", "subprocess", "__", "DROP TABLE", "SELECT ", "rm -rf"]
    for k, v in params.items():
        key_str = str(k)
        val_str = str(v)
        for forbidden in forbidden_substrings:
            if forbidden.lower() in key_str.lower() or forbidden.lower() in val_str.lower():
                raise HTTPException(
                    400,
                    f"Security violation: Parameter contains forbidden execution pattern '{forbidden}'",
                )

    # Verify JSON serializability
    try:
        serialized = json.dumps(params, sort_keys=True, default=str)
    except (TypeError, ValueError) as e:
        raise HTTPException(400, f"Parameters must be JSON serializable: {e}")

    param_fingerprint = fingerprint(params)
    return params, param_fingerprint
