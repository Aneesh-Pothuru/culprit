"""Vendored file-level records; no live loopkit service is required."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    ATTRIBUTED = "ATTRIBUTED"
    UNATTRIBUTED = "UNATTRIBUTED"
    DATA_COMPOSITION = "DATA_COMPOSITION"
    DATA_QUALITY = "DATA_QUALITY"
    TRAINING_CONFIG = "TRAINING_CONFIG"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True)
class TraceEvent:
    timestamp: float
    actor: str
    output: Any
    reference: Any = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

