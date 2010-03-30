#!/usr/bin/perl

use strict;
use warnings;

use Time::Local;
use JSON;
use CGI (':cgi');
my $q = CGI->new;

my $tz = get_timezone();
my $response = to_json({'tz' => $tz});
print $q->header('application/json');
print $response;

sub get_timezone
{
     my $offset  = sprintf "%.1f", ( timegm(localtime) - time ) / 3600;
     return $offset;
}