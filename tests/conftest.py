"""Pytest configuration ensuring local packages are importable."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if 'requests_mock' not in sys.modules:
    package_path = ROOT / 'requests_mock' / '__init__.py'
    spec = importlib.util.spec_from_file_location(
        'requests_mock', package_path, submodule_search_locations=[str(ROOT / 'requests_mock')]
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules['requests_mock'] = module
        spec.loader.exec_module(module)
