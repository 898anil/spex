"""Shared test fixtures."""

from pathlib import Path

import pytest

from spex.graph.builder import build_graph
from spex.graph.model import Graph


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def minimal_root() -> Path:
    return FIXTURES / "minimal"


@pytest.fixture
def minimal_graph(minimal_root: Path) -> Graph:
    return build_graph(minimal_root)
