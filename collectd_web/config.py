"""Config reader for /etc/collectd/collection.conf.

File format (same as the original Perl implementation):

    DataDir: "/path/to/rrd/data"
    DataDir: "/another/path"
    LibDir: "/usr/share/collectd"
    UriPrefix: "/collectd-web"

Rules:
- Lines starting with # or blank lines are ignored.
- Keys are case-insensitive.
- String values are wrapped in double-quotes (backslash escapes supported).
- Numeric values are bare integers.
- DataDir may appear multiple times (accumulates into a list).
"""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH_LINUX = Path("/etc/collectd/collection.conf")
_DEFAULT_CONFIG_PATH_FREEBSD = Path("/usr/local/etc/collectd-web.conf")

_RE_STRING = re.compile(r'^([A-Za-z]+):\s*"((?:[^"\\]|\\.)*)"\s*$')
_RE_NUMBER = re.compile(r'^([A-Za-z]+):\s*([0-9]+)\s*$')


def default_config_path() -> Path:
    """Return the platform-appropriate default config file path."""
    if platform.system().lower() == "freebsd":
        return _DEFAULT_CONFIG_PATH_FREEBSD
    return _DEFAULT_CONFIG_PATH_LINUX


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Parse a collection.conf file and return a config dict.

    Returns:
        {
            "data_dirs": [str, ...],   # one or more RRD data directories
            "lib_dir": str | None,     # optional library directory
            "uri_prefix": str | None,  # optional URI prefix
        }
    """
    if path is None:
        path = Path(os.environ.get("COLLECTD_WEB_CONFIG", str(default_config_path())))
    path = Path(path)

    config: dict[str, Any] = {
        "data_dirs": [],
        "lib_dir": None,
        "uri_prefix": None,
    }

    if not path.exists():
        return config

    with path.open(encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            m = _RE_STRING.match(line)
            if m:
                key = m.group(1).lower()
                value: Any = m.group(2).replace("\\\\", "\\").replace('\\"', '"')
                value = value.rstrip("/")
            else:
                m = _RE_NUMBER.match(line)
                if m:
                    key = m.group(1).lower()
                    value = int(m.group(2))
                else:
                    continue

            if key == "datadir":
                config["data_dirs"].append(value)
            elif key == "libdir":
                config["lib_dir"] = value
            elif key == "uriprefix":
                config["uri_prefix"] = value

    return config
