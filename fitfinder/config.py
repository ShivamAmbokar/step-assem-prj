"""Configuration (HANDBOOK section 5). The defaults are frozen; change them only in S19.

``Config`` is an immutable dataclass. Tests and the CLI (``--set KEY=VALUE``) derive modified
copies with ``Config.override(**kw)`` and ``Config.from_cli(["KEY=VALUE", ...])``.
"""
from __future__ import annotations

import dataclasses
import os
import typing
from dataclasses import dataclass

_TRUE = ("1", "true", "yes", "on")
_FALSE = ("0", "false", "no", "off")


@dataclass(frozen=True)
class Config:
    GEOM_TOL: float = 1e-3  # mm  same point / same surface
    ANGLE_TOL_DEG: float = 0.5
    EXACT_GAP_TOL: float = 0.02  # mm  play <= this -> EXACT
    INTERFERENCE_MAX: float = 0.05  # mm  diametral / across-flats interference accepted
    CLEARANCE_MAX: float = 1.0  # mm  play / size clearance accepted
    RELAX_MARGIN: float = 2.0  # mm  relaxed search window widening
    MIN_PAIR_OVERLAP: float = 0.2
    MIN_MEAN_OVERLAP: float = 0.5
    FULL_CONTACT: float = 0.99
    UV_GRID: int = 20  # refine to 40 if < 50 interior samples
    PLAY_SAMPLES_PER_PAIR: int = 16
    BOOLEAN_FUZZY: float = 1e-4
    COLLISION_VOL_ABS: float = 1e-3  # mm^3
    COLLISION_VOL_REL: float = 1e-6  # x source volume
    INTERFERENCE_VOL_FACTOR: float = 1.5
    UNDER_CONSTRAINED_T: int = 2  # query free translations >= this -> skip Mode B
    MIN_SEED_FRACTION: float = 0.5  # multi-part seeds use >= max(2, ceil(0.5 n)) faces
    MAX_SEEDS: int = 5000
    PLATEAU_GRID: int = 201
    RANGE_RES: float = 0.1
    ROT_SAMPLES_AXIS: int = 24  # 15 deg steps for a free rotation axis
    MAX_RESULTS: int = 500
    INCLUDE_SAME_DEFINITION: bool = False
    ALL_POSES: bool = False
    REACHABILITY: bool = False
    DEF_TIMEOUT_S: int = 30
    WORKERS: int = 0  # 0 = os.cpu_count()
    CACHE_VERSION: int = 1
    BOUNDARY_EPS: float = 1e-6  # inclusive class boundaries

    def to_dict(self) -> dict[str, float | int | bool]:
        """All settings in definition order."""
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}

    def override(self, **kw: object) -> Config:
        """Return a copy with the given settings replaced (names are case-insensitive)."""
        types = typing.get_type_hints(type(self))
        changes = {}
        for key, value in kw.items():
            name = key.upper()
            if name not in types:
                raise ValueError(f"unknown config key: {key!r}")
            changes[name] = _coerce(name, types[name], value)
        return dataclasses.replace(self, **changes)

    @classmethod
    def from_cli(cls, items: list[str] | tuple[str, ...], base: Config | None = None) -> Config:
        """Build a Config from ``['KEY=VALUE', ...]`` (``--set KEY=VALUE``), from ``base``."""
        cfg = base if base is not None else cls()
        parsed = {}
        for item in items:
            key, sep, value = item.partition("=")
            if not sep or not key.strip():
                raise ValueError(f"expected KEY=VALUE, got {item!r}")
            parsed[key.strip()] = value.strip()
        return cfg.override(**parsed)

    def effective_workers(self) -> int:
        """Number of worker processes: WORKERS, or all cores when WORKERS is 0."""
        return self.WORKERS if self.WORKERS > 0 else max(1, os.cpu_count() or 1)


def _coerce(name: str, typ: type, value: object) -> object:
    """Convert ``value`` to the declared type of setting ``name``; strict about bool/int/float."""
    if typ is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in _TRUE + _FALSE:
            return value.strip().lower() in _TRUE
        raise ValueError(f"{name}: expected a boolean (true/false), got {value!r}")
    if typ is int:
        if isinstance(value, bool) or isinstance(value, float):
            raise ValueError(f"{name}: expected an integer, got {value!r}")
        try:
            return int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            raise ValueError(f"{name}: expected an integer, got {value!r}") from None
    if typ is float:
        if isinstance(value, bool):
            raise ValueError(f"{name}: expected a number, got {value!r}")
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(f"{name}: expected a number, got {value!r}") from None
    raise TypeError(f"{name}: unsupported setting type {typ!r}")


DEFAULT = Config()
