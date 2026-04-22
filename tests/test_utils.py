"""Tests for collectd_web.utils."""
from collectd_web.utils import VALID_TIMESPANS, RRD_DEFAULT_ARGS, timespan_to_seconds


def test_valid_timespans_keys():
    assert set(VALID_TIMESPANS.keys()) == {'hour', 'day', 'week', 'month', 'year', 'decade'}


def test_timespan_values():
    assert VALID_TIMESPANS['hour'] == 3600
    assert VALID_TIMESPANS['day'] == 86400
    assert VALID_TIMESPANS['week'] == 7 * 86400


def test_timespan_to_seconds_known():
    assert timespan_to_seconds('day') == 86400


def test_timespan_to_seconds_unknown():
    assert timespan_to_seconds('unknown') is None


def test_rrd_default_args_is_list():
    assert isinstance(RRD_DEFAULT_ARGS, list)
    assert '--rigid' in RRD_DEFAULT_ARGS
    assert '-w' in RRD_DEFAULT_ARGS
