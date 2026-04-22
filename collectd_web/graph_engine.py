"""Graph engine for collectd-web.

Ports the core RRD discovery and graph generation logic from
cgi-bin/collection.modified.cgi.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from collectd_web.graph_defs import GRAPH_DEFS
from collectd_web.utils import RRD_DEFAULT_ARGS, VALID_TIMESPANS

log = logging.getLogger(__name__)

# Try to import the native rrdtool Python bindings; fall back to subprocess.
try:
    import rrdtool as _rrdtool
    _RRDTOOL_NATIVE = True
except ImportError:  # pragma: no cover
    _RRDTOOL_NATIVE = False
    log.warning("rrdtool Python bindings not available — falling back to subprocess")


# ---------------------------------------------------------------------------
# RRD file / directory discovery
# ---------------------------------------------------------------------------

def find_hosts(data_dirs: list[str]) -> list[str]:
    """Return sorted list of host names found across all data directories."""
    hosts: set[str] = set()
    for data_dir in data_dirs:
        try:
            for entry in os.scandir(data_dir):
                if entry.is_dir() and not entry.name.startswith('.'):
                    hosts.add(entry.name)
        except OSError:
            pass
    return sorted(hosts)


def find_plugins(host: str, data_dirs: list[str]) -> dict[str, list[str | None]]:
    """Return dict of {plugin: [instance, ...]} for a host.

    Mirrors _find_plugins() in collection.modified.cgi.
    Plugin dirs are named 'plugin' or 'plugin-instance'.
    """
    plugins: dict[str, list[str | None]] = {}
    for data_dir in data_dirs:
        host_dir = Path(data_dir) / host
        try:
            entries = [e for e in os.scandir(host_dir) if e.is_dir() and not e.name.startswith('.')]
        except OSError:
            continue
        for entry in entries:
            parts = entry.name.split('-', 1)
            plugin = parts[0]
            instance: str | None = parts[1] if len(parts) == 2 else None
            if plugin not in plugins:
                plugins[plugin] = []
            plugins[plugin].append(instance)
    return plugins


def find_types(host: str, plugin: str, plugin_instance: str | None,
               data_dirs: list[str]) -> dict[str, list[str | None]]:
    """Return dict of {type: [instance, ...]} for a host/plugin/plugin_instance.

    Mirrors _find_types() in collection.modified.cgi.
    RRD files are named 'type.rrd' or 'type-instance.rrd'.
    """
    types: dict[str, list[str | None]] = {}
    for data_dir in data_dirs:
        dir_name = plugin + (f'-{plugin_instance}' if plugin_instance else '')
        type_dir = Path(data_dir) / host / dir_name
        try:
            entries = [e for e in os.scandir(type_dir)
                       if e.is_file() and e.name.lower().endswith('.rrd')]
        except OSError:
            continue
        for entry in entries:
            name = entry.name[:-4]  # strip .rrd
            parts = name.split('-', 1)
            type_name = parts[0]
            type_instance: str | None = parts[1] if len(parts) == 2 else None
            if type_name not in types:
                types[type_name] = []
            if type_instance is not None:
                types[type_name].append(type_instance)
    return types


def find_files_for_host(host: str, data_dirs: list[str]) -> dict:
    """Return nested dict {plugin: {p_inst: {type: {t_inst: True}}}}.

    Mirrors _find_files_for_host() in collection.modified.cgi.
    """
    result: dict = {}
    plugins = find_plugins(host, data_dirs)
    for plugin, instances in plugins.items():
        result[plugin] = {}
        effective_instances: list[str | None] = instances if instances else [None]
        for p_inst in effective_instances:
            key = p_inst if p_inst is not None else '-'
            result[plugin][key] = {}
            types = find_types(host, plugin, p_inst, data_dirs)
            for type_name, t_instances in types.items():
                result[plugin][key][type_name] = {}
                if t_instances:
                    for t_inst in t_instances:
                        result[plugin][key][type_name][t_inst] = True
                else:
                    result[plugin][key][type_name]['-'] = True
    return result


# ---------------------------------------------------------------------------
# Graph generation
# ---------------------------------------------------------------------------

def _rrd_path(data_dir: str, host: str, plugin: str,
              plugin_instance: str | None, type_name: str,
              type_instance: str | None) -> str:
    """Build the path to an RRD file."""
    dir_name = plugin + (f'-{plugin_instance}' if plugin_instance else '')
    file_name = type_name + (f'-{type_instance}' if type_instance else '') + '.rrd'
    return str(Path(data_dir) / host / dir_name / file_name)


def _cache_path(cache_dir: str, cache_key: str) -> Path:
    return Path(cache_dir) / f"{cache_key}.png"


def generate_graph(
    host: str,
    plugin: str,
    plugin_instance: str | None,
    type_name: str,
    type_instance: str | None,
    data_dirs: list[str],
    timespan: str = 'day',
    start: str | int | None = None,
    end: str | int | None = None,
    output_format: str = 'PNG',
    enable_caching: bool = False,
    cache_dir: str = '/tmp/collectd-web-cache',
) -> bytes | None:
    """Generate an RRD graph and return PNG bytes.

    Returns None if no matching RRD file is found.

    Mirrors action_show_graph() in collection.modified.cgi.
    """
    # Resolve graph definition — redis/memory special case preserved
    if plugin == 'redis' and type_name == 'memory':
        graph_def = list(GRAPH_DEFS.get('gauge', []))
    else:
        graph_def = list(GRAPH_DEFS.get(type_name, []))
    if not graph_def:
        return None

    # Resolve time range
    if start is not None and end is not None:
        start_arg = str(start)
        end_arg = str(end)
    else:
        offset = VALID_TIMESPANS.get(timespan, VALID_TIMESPANS['day'])
        start_arg = f'-{offset}s'
        end_arg = 'now'

    # Build short title for the graph
    short_title = (
        (f'{plugin_instance}/' if plugin_instance else '')
        + type_name
        + (f'-{type_instance}' if type_instance else '')
    )
    full_title = (
        f'{host}/{plugin}'
        + (f'-{plugin_instance}' if plugin_instance else '')
        + f'/{type_name}'
        + (f'-{type_instance}' if type_instance else '')
    )

    # Find the RRD file across data dirs
    rrd_file: str | None = None
    rrd_base_dir: str | None = None
    for data_dir in data_dirs:
        candidate = _rrd_path(data_dir, host, plugin, plugin_instance,
                               type_name, type_instance)
        if Path(candidate).is_file():
            rrd_file = candidate
            rrd_base_dir = data_dir
            break

    if rrd_file is None:
        return None

    # Substitute {file} placeholder in graph args
    # Use the title path (relative-style) as the Perl code did
    title_path = full_title.replace(':', '\\:') + '.rrd'
    resolved_args = [arg.replace('{file}', title_path) for arg in graph_def]

    # Check cache
    if enable_caching:
        cache_key = hashlib.md5(
            f"{full_title}:{timespan}:{start}:{end}".encode()
        ).hexdigest()
        cached = _cache_path(cache_dir, cache_key)
        if cached.exists() and (time.time() - cached.stat().st_mtime < 300):
            return cached.read_bytes()

    # Build full rrdtool graph argument list
    rrd_args: list[str] = [
        '-a', output_format,
        '-s', start_arg,
        '-t', short_title,
    ]
    if end_arg != 'now':
        rrd_args += ['-e', end_arg]
    rrd_args += RRD_DEFAULT_ARGS
    rrd_args += resolved_args

    # Generate graph
    png_bytes = _render_graph(rrd_file, rrd_base_dir, rrd_args)

    # Store in cache
    if enable_caching and png_bytes:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        _cache_path(cache_dir, cache_key).write_bytes(png_bytes)

    return png_bytes


def _render_graph(rrd_file: str, cwd: str, rrd_args: list[str]) -> bytes | None:
    """Call rrdtool to render a graph, returning PNG bytes."""
    if _RRDTOOL_NATIVE:
        return _render_native(rrd_file, cwd, rrd_args)
    return _render_subprocess(rrd_file, cwd, rrd_args)


def _render_native(rrd_file: str, cwd: str, rrd_args: list[str]) -> bytes | None:
    """Render using the rrdtool Python bindings."""
    orig_dir = os.getcwd()
    try:
        os.chdir(cwd)
        result = _rrdtool.graphv('-', *rrd_args)  # type: ignore[attr-defined]
        return result.get('image')
    except Exception as exc:  # pragma: no cover
        log.error("rrdtool.graphv failed: %s", exc)
        return None
    finally:
        os.chdir(orig_dir)


def _render_subprocess(rrd_file: str, cwd: str, rrd_args: list[str]) -> bytes | None:
    """Render using the rrdtool CLI via subprocess."""
    cmd = ['rrdtool', 'graph', '-'] + rrd_args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            cwd=cwd,
            timeout=30,
        )
        if result.returncode != 0:
            log.error("rrdtool subprocess error: %s", result.stderr.decode())
            return None
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
        log.error("rrdtool subprocess failed: %s", exc)
        return None
