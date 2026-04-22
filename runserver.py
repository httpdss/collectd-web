#!/usr/bin/env python3
"""collectd-web server entry point.

Replaces the old CGIHTTPRequestHandler shim with a proper Flask WSGI server.

Dev usage:
    python runserver.py [host] [port]

Production usage (recommended):
    gunicorn -w 4 'runserver:wsgi_app'
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

DEFAULT_HOST = os.getenv('HOST', '127.0.0.1')
DEFAULT_PORT = int(os.getenv('PORT', 8888))


def _create_app():
    from collectd_web.app import create_app
    config_path = os.getenv('COLLECTD_WEB_CONFIG')
    return create_app(config_path=config_path)


# WSGI entry point for Gunicorn / uWSGI
wsgi_app = _create_app()


def main():
    parser = argparse.ArgumentParser(
        description='Start the collectd-web Python backend server.'
    )
    parser.add_argument(
        'host',
        nargs='?',
        default=DEFAULT_HOST,
        help='Hostname or IP address to bind to (default: %(default)s)',
    )
    parser.add_argument(
        'port',
        nargs='?',
        type=int,
        default=DEFAULT_PORT,
        help='Port number to listen on (default: %(default)s)',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        default=os.getenv('FLASK_DEBUG', '0') == '1',
        help='Enable Flask debug mode',
    )
    args = parser.parse_args()

    print(f'collectd-web server running at http://{args.host}:{args.port}/')
    wsgi_app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
