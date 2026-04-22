"""Tests for collectd_web.graph_defs."""
from collectd_web.graph_defs import GRAPH_DEFS


def test_graph_defs_is_dict():
    assert isinstance(GRAPH_DEFS, dict)


def test_graph_defs_has_entries():
    # Original graphdefs.cgi defined 80 graph types;
    # partial push has at least the initial entries
    assert len(GRAPH_DEFS) >= 1


def test_known_keys_present():
    for key in ('cpu', 'disk', 'df'):
        assert key in GRAPH_DEFS, f'Missing key: {key}'


def test_values_are_lists_of_strings():
    for key, val in GRAPH_DEFS.items():
        assert isinstance(val, list), f'{key}: expected list, got {type(val)}'
        for item in val:
            assert isinstance(item, str), f'{key}: non-string item {item!r}'


def test_cpu_def_contains_file_placeholder():
    cpu = GRAPH_DEFS['cpu']
    assert any('{file}' in s for s in cpu), 'cpu def missing {file} placeholder'


def test_no_perl_variable_remnants():
    import re
    perl_var_re = re.compile(r'\$[A-Za-z]')
    for key, items in GRAPH_DEFS.items():
        for item in items:
            assert not perl_var_re.search(item), (
                f'{key}: Perl variable remnant in {item!r}'
            )
