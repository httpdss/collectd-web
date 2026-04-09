"""Tests for collectd_web.config."""
from __future__ import annotations

from pathlib import Path

from collectd_web.config import load_config


def test_load_nonexistent_file(tmp_path: Path):
    cfg = load_config(tmp_path / 'missing.conf')
    assert cfg['data_dirs'] == []
    assert cfg['lib_dir'] is None
    assert cfg['uri_prefix'] is None


def test_load_datadir(tmp_path: Path):
    conf = tmp_path / 'collection.conf'
    conf.write_text('DataDir: "/var/lib/collectd"\n')
    cfg = load_config(conf)
    assert cfg['data_dirs'] == ['/var/lib/collectd']


def test_load_multiple_datadirs(tmp_path: Path):
    conf = tmp_path / 'collection.conf'
    conf.write_text('DataDir: "/data1"\nDataDir: "/data2"\n')
    cfg = load_config(conf)
    assert cfg['data_dirs'] == ['/data1', '/data2']


def test_trailing_slash_stripped(tmp_path: Path):
    conf = tmp_path / 'collection.conf'
    conf.write_text('DataDir: "/var/lib/collectd/"\n')
    cfg = load_config(conf)
    assert cfg['data_dirs'] == ['/var/lib/collectd']


def test_libdir(tmp_path: Path):
    conf = tmp_path / 'collection.conf'
    conf.write_text('LibDir: "/usr/share/collectd"\n')
    cfg = load_config(conf)
    assert cfg['lib_dir'] == '/usr/share/collectd'


def test_uriprefix(tmp_path: Path):
    conf = tmp_path / 'collection.conf'
    conf.write_text('UriPrefix: "/prefix"\n')
    cfg = load_config(conf)
    assert cfg['uri_prefix'] == '/prefix'


def test_comments_ignored(tmp_path: Path):
    conf = tmp_path / 'collection.conf'
    conf.write_text('# comment\n\nDataDir: "/data"\n')
    cfg = load_config(conf)
    assert cfg['data_dirs'] == ['/data']
