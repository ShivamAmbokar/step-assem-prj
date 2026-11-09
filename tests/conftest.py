"""pytest configuration: marker skipping (HANDBOOK 0.1.3) and the session fixture placeholder.

* ``occ`` tests are skipped when ``import OCP`` fails (e.g. Claude's sandbox).
* ``real`` tests are skipped unless ``FITFINDER_DATA`` points to an existing directory. Files the
  test needs can be named in the marker: ``@pytest.mark.real("key_part.step")``; the test is
  skipped when one of them is missing from ``FITFINDER_DATA``.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from helpers import REPO_ROOT, fixtures_content_hash

_MARKERS = {
    "occ": "needs OCP / cadquery (skipped when OCP cannot be imported)",
    "real": "needs the real assemblies under FITFINDER_DATA (skipped when unset or files missing)",
    "slow": "long-running test (excluded from the regression suite)",
}


def _occ_importable() -> bool:
    try:
        import OCP  # noqa: F401
    except Exception:
        return False
    return True


def _real_data_problem(marker: pytest.Mark) -> str | None:
    """Return why a ``real`` test cannot run here, or None when its data is available."""
    data = os.environ.get("FITFINDER_DATA", "").strip()
    if not data:
        return "FITFINDER_DATA is not set"
    data_dir = Path(data)
    if not data_dir.is_dir():
        return f"FITFINDER_DATA is not a directory: {data}"
    names: list[str] = []
    for arg in marker.args:
        names.extend(arg if isinstance(arg, (list, tuple)) else [arg])
    for name in names:
        if not (data_dir / str(name)).exists():
            return f"{name} not found in FITFINDER_DATA ({data})"
    return None


def pytest_configure(config: pytest.Config) -> None:
    for name, text in _MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {text}")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    occ_ok = _occ_importable()
    for item in items:
        if "occ" in item.keywords and not occ_ok:
            item.add_marker(pytest.mark.skip(reason="OCP is not importable"))
        real = item.get_closest_marker("real")
        if real is not None:
            problem = _real_data_problem(real)
            if problem:
                item.add_marker(pytest.mark.skip(reason=problem))


@pytest.fixture(scope="session")
def fixtures_out() -> SimpleNamespace:
    """Placeholder for the built synthetic fixtures (``fixtures/out``).

    S01.4 will build the fixtures here once per content hash of ``fixtures/``; until then this
    only reports where they will live and the current hash.
    """
    fixtures = REPO_ROOT / "fixtures"
    return SimpleNamespace(
        path=fixtures / "out",
        content_hash=fixtures_content_hash(fixtures),
        build_script=fixtures / "build.py",
    )
