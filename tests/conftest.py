"""Shared pytest fixtures for collectd-web tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from collectd_web.app import create_app


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    """Write a minimal collection.conf and return its path."""
    data_dir = tmp_path / 'rrd'
    data_dir.mkdir()
    conf = tmp_path / 'collection.conf'
    conf.write_text(f'DataDir: "{data_dir}"\n')
    return conf


@pytest.fixture()
def fake_rrd_tree(tmp_path: Path) -> Path:
    """Create a fake RRD directory tree for discovery tests.

    Structure::

        rrd/
          myhost/
            cpu-0/
              cpu-user.rrd
              cpu-system.rrd
            memory/
              memory-used.rrd
    """
    base = tmp_path / 'rrd'
    cpu_dir = base / 'myhost' / 'cpu-0'
    mem_dir = base / 'myhost' / 'memory'
    cpu_dir.mkdir(parents=True)
    mem_dir.mkdir(parents=True)
    (cpu_dir / 'cpu-user.rrd').touch()
    (cpu_dir / 'cpu-system.rrd').touch()
    (mem_dir / 'memory-used.rrd').touch()
    return base


@pytest.fixture()
def app(tmp_config: Path):
    """Flask test application backed by a temp config."""
    application = create_app(config_path=str(tmp_config))
    application.config['TESTING'] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
