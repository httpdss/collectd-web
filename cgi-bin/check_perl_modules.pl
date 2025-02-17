#!/usr/bin/env perl
use warnings;
use strict;

my $filename=shift || &help; # command line argument is perl script to evaluate
my @modules;  # array of 'use' statements from code we are checking

open (IN,$filename) or die "couldn't open $filename for processing: $!
+\n";

while (<IN>)
{
        chomp;
        if ((/^use/) and not (/strict/ || /warnings/))
        {
                push @modules,$_;
        }
}
close IN;
for my $code (@modules)
{
        my (undef,$library)=split(/ /,$code);   # get the module name
        $library=~s/;//;                        # clean up the name
        eval $code;
        if ($@)
        {
                warn "couldn't load $library: $@","\n";
        }
        else
        {
                print "$library looks ok\n";
        };
}
sub help
{
        print <<"END";

check_perl_modules.pl

This script finds all the "use" statements loading modules in the target perl
file (specified as a command line argument) and attempts to load them.
If there are problems loading the module, the error mesage returned is printed.

END
        exit;
}
