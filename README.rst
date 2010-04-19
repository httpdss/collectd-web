============
Collectd-web
============

The main objective of this is to develop an easy to use and customizable web
interface for Collectd (Resource monitoring software). Two days of research
where enough to realize that collectd didn't have a real frontend and the one
bundled with the backend was really made for testing purposes, so much of the
usability and strength of statistics was left aside.

Features
========
 * [NEW] IPhone interface
 * [NEW] Comparison ruler
 * [NEW] Local and server clock
 * Host list and filtering
 * jQuery-based web interface
 * Themable UI using jQueryUI
 * Perl backend
 * Sortable graphs

Installation
============
You must have a path containing each host's files in a separate
sub-directory, named according to the host.

For example,
 /etc/collectd/collectd-web/localhost/

In this case, your datadir will be '/etc/collectd/collectd-web/'.
Create /etc/collectd/collection.conf with the content:

 datadir: "/etc/collectd/collectd-web/"

Still to be done
================
Check out the issues list ;)

License
=======
Collectd-web is licensed under the GNU General Public License (GPL), version 2
or later. The full licensing terms are available in the file "COPYING".

This package includes jQuery which is licensed under the GPL version 2 and the
MIT license. For more information on jQuery's license, visit their homepage at:
  <http://jquery.org/license>
