#!/usr/bin/perl

# Collectd-web - time.cgi
# Copyright (C) 2009-2010  Kenneth Belitzky
# 
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
# 
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
# 
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
use strict;
use warnings;

use Time::Local;
use JSON ('objToJson');
use CGI (':cgi');
my $q = CGI->new;

my $tz = get_timezone();
my $response = objToJson({'tz' => $tz});
print $q->header('application/json');
print $response;

sub get_timezone
{
     my $offset  = sprintf "%.1f", ( timegm(localtime) - time ) / 3600;
     return $offset;
}
