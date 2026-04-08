"""Flask application for collectd-web.

Replaces the Python CGI shim (runserver.py + CGIHTTPRequestHandler) with a
proper WSGI app. All URLs are backward-compatible with the original Perl CGI
scripts so that index.html requires no changes.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from collectd_web.config import load_config
from collectd_web.graph_defs import GRAPH_DEFS
from collectd_web.graph_engine import find_files_for_host, find_hosts, generate_graph

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config_path: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder=None,  # we handle static files manually
    )

    cfg = load_config(config_path)
    app.config['COLLECTD_CONFIG'] = cfg

    # Root of the repository (one level above this package)
    repo_root = Path(__file__).parent.parent

    # ------------------------------------------------------------------
    # /cgi-bin/collection.modified.cgi  (all actions)
    # ------------------------------------------------------------------
    @app.route('/cgi-bin/collection.modified.cgi')
    def collection_cgi() -> Response:
        config = app.config['COLLECTD_CONFIG']
        data_dirs: list[str] = config.get('data_dirs', [])
        action = request.args.get('action', '')

        # --- hostlist_json ---
        if action == 'hostlist_json':
            hosts = find_hosts(data_dirs)
            return jsonify(sorted(hosts))

        # --- pluginlist_json ---
        if action == 'pluginlist_json':
            host = request.args.get('host', '')
            if not host:
                return jsonify({'error': 'host parameter required'}), 400
            files = find_files_for_host(host, data_dirs)
            return jsonify(sorted(files.keys()))

        # --- graphs_json ---
        if action == 'graphs_json':
            host = request.args.get('host', '')
            plugin = request.args.get('plugin', '')
            if not host or not plugin:
                return jsonify({'error': 'host and plugin required'}), 400
            files = find_files_for_host(host, data_dirs)
            plugin_data = files.get(plugin, {})
            return jsonify(plugin_data)

        # --- show_graph / show_custom_graph ---
        if action in ('show_graph', 'show_custom_graph'):
            host = request.args.get('host')
            plugin = request.args.get('plugin')
            type_name = request.args.get('type')
            if not host or not plugin or not type_name:
                return Response('Missing host, plugin or type', status=400)

            plugin_instance = request.args.get('plugin_instance') or None
            type_instance = request.args.get('type_instance') or None
            timespan = request.args.get('timespan', 'day')
            start = request.args.get('start') or None
            end = request.args.get('end') or None
            enable_caching = 'enable-caching' in request.args
            output_format = request.args.get('output', 'PNG').upper()

            png = generate_graph(
                host=host,
                plugin=plugin,
                plugin_instance=plugin_instance,
                type_name=type_name,
                type_instance=type_instance,
                data_dirs=data_dirs,
                timespan=timespan,
                start=start,
                end=end,
                output_format=output_format,
                enable_caching=enable_caching,
            )
            if png is None:
                return Response('Graph not found', status=404)

            headers = {}
            if enable_caching:
                headers['Cache-Control'] = 'maxage=3600'
                headers['Pragma'] = 'public'
            return Response(
                png,
                mimetype='image/png',
                headers=headers,
            )

        return Response('Unknown action', status=400)

    # ------------------------------------------------------------------
    # /cgi-bin/graphdefs.cgi  — graph definitions as JSON
    # ------------------------------------------------------------------
    @app.route('/cgi-bin/graphdefs.cgi')
    def graphdefs_cgi() -> Response:
        return jsonify({'graph_defs': GRAPH_DEFS})

    # ------------------------------------------------------------------
    # /cgi-bin/time.cgi  — timezone offset JSON
    # ------------------------------------------------------------------
    @app.route('/cgi-bin/time.cgi')
    def time_cgi() -> Response:
        offset = -time.timezone / 3600.0
        if time.daylight and time.localtime().tm_isdst:
            offset = -time.altzone / 3600.0
        return jsonify({'tz': round(offset, 1)})

    # ------------------------------------------------------------------
    # Static files — index.html, media/, mobile/
    # ------------------------------------------------------------------
    @app.route('/')
    def index() -> Response:
        return send_file(repo_root / 'index.html')

    @app.route('/media/<path:filename>')
    def media(filename: str) -> Response:
        return send_from_directory(repo_root / 'media', filename)

    @app.route('/mobile/<path:filename>')
    def mobile(filename: str) -> Response:
        return send_from_directory(repo_root / 'mobile', filename)

    @app.route('/docs/<path:filename>')
    def docs(filename: str) -> Response:
        return send_from_directory(repo_root / 'docs', filename)

    return app
