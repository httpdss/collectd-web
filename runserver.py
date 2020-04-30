#!/usr/bin/env python3

import http.server
from optparse import OptionParser

class Handler(http.server.CGIHTTPRequestHandler):
    cgi_directories = ["/cgi-bin"]

PORT = 8888

def main():
    parser = OptionParser()
    opts, args = parser.parse_args()
    if args:
        httpd = http.server.HTTPServer((args[0], int(args[1])), Handler)
        print(("Collectd-web server running at http://%s:%s/" % (args[0], args[1])))
    else:
        httpd = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
        print(("Collectd-web server running at http://%s:%s/" % ("127.0.0.1", PORT)))
    httpd.serve_forever()

if __name__ == "__main__":
    main()
