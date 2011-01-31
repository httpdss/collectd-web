#!/usr/bin/env python

import CGIHTTPServer
import BaseHTTPServer

class Handler(CGIHTTPServer.CGIHTTPRequestHandler):
    cgi_directories = ["/cgi-bin"]



PORT = 8888

httpd = BaseHTTPServer.HTTPServer(("", PORT), Handler)
print "Collectd-web server running at http://%s:%s/" % ("127.0.0.1", PORT)
httpd.serve_forever()
