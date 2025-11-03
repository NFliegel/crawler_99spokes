"""Minimal stub implementation of the :mod:`requests_mock` API used in tests.

This project only needs a very small subset of the functionality provided by
the real third party library.  Network access is not available in the execution
environment so we provide a local drop-in replacement that mimics the context
manager used in the tests.  The implementation keeps track of mocked GET
requests and temporarily patches :func:`requests.get` to return predictable
responses during the lifetime of the context manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import requests


@dataclass
class _MockResponse:
    text: str
    status_code: int = 200

    def raise_for_status(self) -> None:
        if not (200 <= self.status_code < 400):
            raise requests.HTTPError(f"Status code: {self.status_code}")

    def json(self) -> Dict[str, str]:
        raise NotImplementedError("JSON responses are not supported by the stub")


class Mocker:
    """A tiny context manager compatible with ``requests_mock.Mocker`` used in tests."""

    def __init__(self) -> None:
        self._registry: Dict[str, _MockResponse] = {}
        self._original_get: Optional[Callable[..., requests.Response]] = None

    def __enter__(self) -> "Mocker":
        self._original_get = requests.get

        def _mocked_get(url: str, *args, **kwargs):
            if url not in self._registry:
                raise RuntimeError(f"No mock registered for URL: {url}")
            return self._registry[url]

        requests.get = _mocked_get  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._original_get is not None:
            requests.get = self._original_get  # type: ignore[assignment]
            self._original_get = None
        self._registry.clear()

    def get(self, url: str, *, text: str, status_code: int = 200) -> None:
        """Register a mocked GET request with the response text returned by the stub."""

        self._registry[url] = _MockResponse(text=text, status_code=status_code)


__all__ = ["Mocker"]

