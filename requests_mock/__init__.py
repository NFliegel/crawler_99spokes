"""Minimal requests-mock replacement for tests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import json as _json
import requests


@dataclass
class _MockResponse:
    text: str = ""
    status_code: int = 200
    headers: Optional[Dict[str, str]] = None

    def json(self) -> Any:
        return _json.loads(self.text)

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class Mocker:
    """A very small subset of requests_mock.Mocker used in tests."""

    def __init__(self) -> None:
        self._registry: Dict[str, _MockResponse] = {}
        self._original_get: Optional[Callable[..., requests.Response]] = None

    def __enter__(self) -> "Mocker":
        self._original_get = requests.get

        def _mocked_get(url: str, *args: Any, **kwargs: Any) -> _MockResponse:
            if url not in self._registry:
                raise requests.HTTPError(f"No mock registered for {url}")
            response = self._registry[url]
            return response

        requests.get = _mocked_get  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._original_get is not None:
            requests.get = self._original_get  # type: ignore[assignment]
        self._registry.clear()

    def get(self, url: str, *, text: str = "", status_code: int = 200, json: Any = None) -> None:
        if json is not None:
            text = _json.dumps(json)
        self._registry[url] = _MockResponse(text=text, status_code=status_code)


__all__ = ["Mocker"]
