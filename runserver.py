#!/usr/bin/env python3

import http.server
import argparse
from dotenv import load_dotenv
import os

load_dotenv()

DEFAULT_HOST = os.getenv("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("PORT", 8888))


class Handler(http.server.CGIHTTPRequestHandler):
    cgi_directories = ["/cgi-bin"]

def main():
    parser = argparse.ArgumentParser(
        description="Start a simple CGI-capable web server for serving Perl scripts."
    )
    parser.add_argument(
        "host",
        nargs="?",
        default=DEFAULT_HOST,
        help="Hostname or IP address to bind to (default: %(default)s)"
    )
    parser.add_argument(
        "port",
        nargs="?",
        type=int,
        default=DEFAULT_PORT,
        help="Port number to listen on (default: %(default)s)"
    )
    args = parser.parse_args()

    # Use HTTPServer to ensure necessary attributes are present.
    with http.server.HTTPServer((args.host, args.port), Handler) as httpd:
        print("Collectd-web server running at http://%s:%s/" %
              (args.host, args.port))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            httpd.server_close()


if __name__ == "__main__":
    main()
