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
 /var/db/collectd/localhost/

In this case, your datadir will be '/var/db/collectd/'.
Add in /etc/collectd.conf (for linux boxes) or in /usr/local/etc/collectd.conf (freebsd boxes) the following variable:

 datadir: "/var/db/collectd/"

For Debian-based linux distribution
-----------------------------------

Install the following dependencies

	apt-get install librrds-perl libjson-perl libhtml-parser-perl

For FreeBSD
-----------

Install the collectd issuing:

        pkg install collectd

Using the webserver
===================
Give collectd-web a try! Execute the standalone web server and you are done:

	python runserver.py 0.0.0.0 8000

Links
=====
 * http://collectdweb.appspot.com
 * https://twitter.com/collectdweb
 * https://www.facebook.com/collectdweb
 * https://plus.google.com/111037505131782971511/posts
 * https://twitter.com/collectdweb_git (Commit tracker for collectd-web repository)

License
=======
Collectd-web is licensed under the GNU General Public License (GPL), version 2
or later. The full licensing terms are available in the file "COPYING".

This package includes jQuery which is licensed under the GPL version 2 and the
MIT license. For more information on jQuery's license, visit their homepage at:
  <http://jquery.org/license>
