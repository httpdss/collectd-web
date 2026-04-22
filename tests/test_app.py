"""Flask route integration tests for collectd-web."""
from __future__ import annotations


def test_time_cgi(client):
    resp = client.get('/cgi-bin/time.cgi')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'tz' in data
    assert isinstance(data['tz'], float)


def test_graphdefs_cgi(client):
    resp = client.get('/cgi-bin/graphdefs.cgi')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'graph_defs' in data
    assert 'cpu' in data['graph_defs']


def test_hostlist_json_empty(client):
    # Empty data dir -> empty host list
    resp = client.get('/cgi-bin/collection.modified.cgi?action=hostlist_json')
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_pluginlist_json_missing_host(client):
    resp = client.get('/cgi-bin/collection.modified.cgi?action=pluginlist_json')
    assert resp.status_code == 400


def test_graphs_json_missing_params(client):
    resp = client.get('/cgi-bin/collection.modified.cgi?action=graphs_json&host=h')
    assert resp.status_code == 400


def test_show_graph_missing_params(client):
    resp = client.get('/cgi-bin/collection.modified.cgi?action=show_graph&host=h')
    assert resp.status_code == 400


def test_unknown_action(client):
    resp = client.get('/cgi-bin/collection.modified.cgi?action=bogus')
    assert resp.status_code == 400
