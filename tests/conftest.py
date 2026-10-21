"""Group markers, with no implicit access to Windows or model subscriptions."""

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items):
    groups = {"unit", "integration", "windows", "providers"}
    for item in items:
        group = Path(str(item.path)).parent.name
        if group in groups:
            item.add_marker(getattr(pytest.mark, group))
