from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def _read(name: str) -> dict[str, Any]:
    resource = files("culprit.resources").joinpath(name)
    return json.loads(resource.read_text(encoding="utf-8"))


def fixture_documents() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]
]:
    """Return fresh copies of the packaged reference stack and evidence."""
    stack = _read("stack.json")
    registry = _read("registry.json")
    manifests = {
        checkpoint: _read(f"manifest-{checkpoint}.json")
        for checkpoint in ("ckpt-1", "ckpt-2", "ckpt-3", "ckpt-4", "ckpt-5")
    }
    return stack, registry, manifests
