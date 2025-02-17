#!/usr/bin/env perl
use strict;
use warnings;

my @modules = qw(
    CGI
    CGI::Carp
    JSON
    URI::Escape
    RRDs
);

for my $mod (@modules) {
    eval "use $mod";
    if ($@) {
        warn "Module $mod is not installed.\n";
    }
    else {
        no strict 'refs';
        my $version = ${"${mod}::VERSION"} // 'unknown';
        print "$mod version: $version\n";
    }
}
