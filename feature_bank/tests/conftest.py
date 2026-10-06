"""pytest setup for the feature-bank tests: repo root on the path, and two opt-in switches.

    pytest tests/ -q                 # local, free
    pytest tests/ -q --gpu           # also the GPU families (downloads model weights)
    pytest tests/ -q --modal         # also local-vs-Modal parity (PAID: the lead runs this, nobody else)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_addoption(parser):
    parser.addoption("--gpu", action="store_true", help="also test families with RUNS_ON = 'gpu'")
    parser.addoption("--modal", action="store_true", help="also run the paid local-vs-Modal parity test")


def pytest_configure(config):
    config.addinivalue_line("markers", "modal: needs a paid Modal run")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--modal"):
        skip = pytest.mark.skip(reason="paid Modal run: pass --modal (lead only)")
        for item in items:
            if "modal" in item.keywords:
                item.add_marker(skip)
