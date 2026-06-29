from __future__ import annotations

import pytest

from private_rag.core.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
