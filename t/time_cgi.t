#!/usr/bin/env perl
use strict;
use warnings;
use Test::More tests => 3;
use IPC::Run qw(run);
use JSON;

# Path to your CGI script
my $script = './cgi-bin/time.cgi';

# Run the script and capture its output
my $output;
run [ $^X, $script ], '>', \$output or die "Could not run $script: $!";

# Test 1: Ensure the output starts with the correct Content-Type header.
like($output, qr/^Content-Type: application\/json/, 'Output contains correct Content-Type header');

# Test 2: Extract the JSON part by splitting output on the double newline that separates headers from content.
my (undef, $json_text) = split(/\r?\n\r?\n/, $output, 2);
ok($json_text, 'JSON response is present');

# Test 3: Parse the JSON response and verify that the "tz" key exists.
my $data = decode_json($json_text);
ok(defined $data->{tz}, 'Timezone key is present in JSON');
