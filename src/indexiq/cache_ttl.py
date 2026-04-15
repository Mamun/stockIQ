"""
Load cache TTL values from config/cache.yml.

Usage:
    from indexiq.cache_ttl import CACHE_TTL

    @st.cache_data(ttl=CACHE_TTL["fetch_spx_quote"])
    def fetch_spx_quote() -> dict: ...
"""
from pathlib import Path

import yaml

_cfg_path = Path(__file__).parent.parent.parent / "config" / "cache.yml"
with open(_cfg_path) as _f:
    _raw: dict = yaml.safe_load(_f)

# Flatten all sections into a single dict keyed by function name
CACHE_TTL: dict[str, int] = {
    fn: ttl
    for section in _raw.values()
    for fn, ttl in section.items()
}
