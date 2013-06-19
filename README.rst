============
Collectd-web
============

The main objective of this is to develop an easy to use and customizable web
interface for Collectd (Resource monitoring software). Two days of research
where enough to realize that collectd didn't have a real frontend and the one
bundled with the backend was really made for testing purposes, so much of the
usability and strength of statistics was left aside.

Installation
============
You must have a path containing each host's files in a separate
sub-directory, named according to the host.

For example,
 /etc/collectd/collectd-web/localhost/

In this case, your datadir will be '/etc/collectd/collectd-web/'.
Create /etc/collectd/collection.conf with the content:

 datadir: "/etc/collectd/collectd-web/"


Using the webserver
===================
Give collectd-web a try! Execute the standalone web server and you are done:

	python runserver.py

Links
=====
 * http://kenny.belitzky.com/projects/collectd-web
 * http://twitter.com/collectdweb
 * http://twitter.com/collectdweb_git (Commit tracker for collectd-web repository)

License
=======
Collectd-web is licensed under the GNU General Public License (GPL), version 2
or later. The full licensing terms are available in the file "COPYING".

This package includes jQuery which is licensed under the GPL version 2 and the
MIT license. For more information on jQuery's license, visit their homepage at:
  <http://jquery.org/license>
