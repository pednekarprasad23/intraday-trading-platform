"""Execution sandbox and parameterized run validation (V2.6 Phase 3 Acceptance Audit)."""

import json
from typing import Any
from fastapi import HTTPException
from app.backtesting.engine import fingerprint


def validate_and_snapshot_parameters(params: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    """Validate parameters as pure data (no executable code, no shell, no eval/exec),

    snapshot them, and compute canonical SHA-256 fingerprint.
    """
    if params is None:
        params = {}

    if not isinstance(params, dict):
        raise HTTPException(400, "Parameters must be a JSON object dictionary")

    # Structural type-safety and code execution protection
    allowed_types = (int, float, str, bool, list, dict, type(None))

    def _validate_value(val: Any, path: str = "root"):
        if not isinstance(val, allowed_types):
            raise HTTPException(
                400,
                f"Parameter type error at '{path}': type {type(val).__name__} is not allowed in sandbox parameters",
            )
        if isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise HTTPException(400, f"Parameter key error at '{path}': keys must be strings")
                _validate_value(v, f"{path}.{k}")
        elif isinstance(val, list):
            for idx, item in enumerate(val):
                _validate_value(item, f"{path}[{idx}]")
        elif isinstance(val, str):
            val_lower = val.lower()
            # Explicit code execution checks
            if any(code_op in val_lower for code_op in ["eval(", "exec(", "__import__", "subprocess", "os.system", "sys.modules"]):
                raise HTTPException(400, f"Security violation: Parameter at '{path}' contains forbidden execution code pattern")

    for k, v in params.items():
        if not isinstance(k, str):
            raise HTTPException(400, "Parameter top-level keys must be strings")
        _validate_value(v, k)

    try:
        serialized = json.dumps(params, sort_keys=True, default=str)
    except (TypeError, ValueError) as e:
        raise HTTPException(400, f"Parameters must be JSON serializable: {e}")

    param_fingerprint = fingerprint(params)
    return params, param_fingerprint
