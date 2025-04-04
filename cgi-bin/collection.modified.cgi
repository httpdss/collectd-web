#!/usr/bin/env perl
# Collectd-web - collection.modified.cgi
# Copyright (C) 2006-2010  Florian "octo" Forster
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
no warnings qw(deprecated);
use Config;
use Carp           (qw(cluck confess));
use CGI            (':cgi');
use CGI::Carp      ('fatalsToBrowser');
use HTML::Entities ('encode_entities');
use URI::Escape    ('uri_escape');
use RRDs           ();
use Data::Dumper   ();
use JSON ('to_json');
our $config_file   = "/etc/collectd/collection.conf";
if ($Config{osname} eq q{freebsd}){
  $config_file = "/usr/local/etc/collectd-web.conf";
}
our @DataDirs = ();
our $LibDir;
our $make_transparent = 1;
our $ValidTimespan    = {
    hour    => 3600,
    day     => 86400,
    week    => 7 * 86400,
    month   => 31 * 86400,
    year    => 366 * 86400,
    decade  => 10 * 366 * 86400
};

# FIXEDish: This isn't working when talking to a daemon.
# The path given to rrd* needs to be relative to that of the -b option of
# rrdcached, so we hacked up a few things to allow for that.
# 2014-02-04
# bpkroth
#$ENV{'RRDCACHED_ADDRESS'} = undef;

our @RRDDefaultArgs = (
  '--rigid',
  '-w', '1040', '-h', '360',
  '--alt-autoscale-max',
  '--alt-y-grid',
  '--slope-mode',
  '--font', 'TITLE:28:Monospace',
  '--font', 'AXIS:10:Monospace',
  '--font', 'LEGEND:12:Monospace',
  '--font', 'UNIT:12:Monospace',
  '-c', 'BACK#EEEEEEFF',
  '-c', 'CANVAS#FFFFFF00',
  '-c', 'SHADEA#EEEEEEFF',
  '-c', 'SHADEB#EEEEEEFF',
  '-i',
);



our $Args = {};
our $GraphDefs;
our $MetaGraphDefs = {};
our $OutputFormat = '';
our $ContentType = 'image/png';

load_graph_definitions();

for (qw(action host plugin plugin_instance type type_instance timespan output enable-caching start end)) {
    $Args->{$_} = param($_);
}

exit( main() );

sub read_config {
    my $fh;
    open( $fh, "< $config_file" ) or confess("open ($config_file): $!");
    while ( my $line = <$fh> ) {
        chomp($line);
        next if ( !$line );
        next if ( $line =~ m/^\s*#/ );
        next if ( $line =~ m/^\s*$/ );
        my $key;
        my $value;
        if ( $line =~ m/^([A-Za-z]+):\s*"((?:[^"\\]+|\\.)*)"$/ ) {
            $key   = lc($1);
            $value = $2;
            $value =~ s/\\(.)/$1/g;
        }
        elsif ( $line =~ m/([A-Za-z]+):\s*([0-9]+)$/ ) {
            $key   = lc($1);
            $value = 0 + $2;
        }
        else {
            # print STDERR "Cannot parse line: $line\n";
            next;
        }
        if ( $key eq 'datadir' ) {
            $value =~ s#/*$##;
            push( @DataDirs, $value );
        }
        elsif ( $key eq 'libdir' ) {
            $value =~ s#/*$##;
            $LibDir = $value;
        }
        elsif ( $key eq 'uriprefix' ) {
            $value =~ s#/*$##;
            $ENV{'SCRIPT_NAME'} = $value . $ENV{'SCRIPT_NAME'};
        }
        else {
            print STDERR "Unknown key: $key\n";
        }
    }
    close($fh);
}    # read_config

sub validate_args {
    if ($Args->{'action'} && ( $Args->{'action'} =~ m/^(overview|show_host|show_plugin|show_type|show_graph|hostlist_json|pluginlist_json|graphs_json)$/ ))
    {
        $Args->{'action'} = $1;
    }
    else {
        $Args->{'action'} = 'overview';
    }
    if ($Args->{'host'} && ( $Args->{'host'} =~ m#/# ) ) {
        delete( $Args->{'host'} );
    }
    if ($Args->{'plugin'} && ( $Args->{'plugin'} =~ m#/# ) ) {
        delete( $Args->{'plugin'} );
    }
    if ($Args->{'type'} && ( $Args->{'type'} =~ m#/# ) ) {
        delete( $Args->{'type'} );
    }
    if (!$Args->{'plugin'} || ( $Args->{'plugin_instance'} && ( $Args->{'plugin_instance'} =~ m#/# ) ))
    {
        delete( $Args->{'plugin_instance'} );
    }
    if (!$Args->{'type'} || ( $Args->{'type_instance'} && ( $Args->{'type_instance'} =~ m#/# ) ))
    {
        delete( $Args->{'type_instance'} );
    }
    if (defined( $Args->{'timespan'} ) && ( $Args->{'timespan'} =~ m/^(hour|day|week|month|year|decade)$/ ) )
    {
        $Args->{'timespan'} = $1;
    }
    else {
        $Args->{'timespan'} = 'day';
    }

    if ( defined( $Args->{'output'} )
        && ( $Args->{'output'} =~ m/^(json)$/ ) )
    {
        $Args->{'output'} = $1;
    } else {
        $Args->{'output'} = "html";
    }
}    # validate_args
{
    my $hosts;

    sub _find_hosts {
        if ( defined($hosts) ) {
            return ( keys %$hosts );
        }
        $hosts = {};
        for ( my $i = 0 ; $i < @DataDirs ; $i++ ) {
            my @tmp;
            my $dh;
            opendir( $dh, $DataDirs[$i] ) or next;
            @tmp =
              grep { ( $_ !~ m/^\./ ) && ( -d $DataDirs[$i] . '/' . $_ ) }
              ( readdir($dh) );
            closedir($dh);
            $hosts->{$_} = 1 for (@tmp);
        }    # for (@DataDirs)
        return ( keys %$hosts );
    }    # _find_hosts
}

sub _get_menu_buttons {
    return '<span class="gc-menu fg-toolbar ui-widget-header ui-corner-all ui-helper-clearfix">
              <span class="icons ui-state-default ui-corner-all">
                <span class="ui-icon ui-icon-triangle-1-w"/>
              </span>
              <span class="icons ui-state-default ui-corner-all">
                <span class="ui-icon ui-icon-triangle-1-e"/>
              </span>
              <span class="icons ui-state-default ui-corner-all">
                <span class="ui-icon ui-icon-zoomin"/>
              </span>
              <span class="icons ui-state-default ui-corner-all">
                <span class="ui-icon ui-icon-zoomout"/>
              </span>
              <span class="icons ui-state-default ui-corner-all">
                <span class="ui-icon ui-icon-disk"/>
              </span>
              <span class="icons ui-state-default ui-corner-all">
                <span class="ui-icon ui-icon-star"/>
              </span>
              <span class="icons ui-state-default ui-corner-all">
                <span class="ui-icon ui-icon-close"/>
              </span>
            </span>
            <span class="selectable"></span>';
}

sub _get_param_host {
    my %all_hosts = map { $_ => 1 } ( _find_hosts() );
    my @selected_hosts = ();
    my $p = param('host');
    my @hosts = ref $p eq 'ARRAY' ? @$p : ($p);
    for ( @hosts ) {
        if ( defined( $all_hosts{$_} ) ) {
            push( @selected_hosts, "$_" );
        }
    }
    return (@selected_hosts);
}    # _get_param_host

sub _get_param_timespan {
    my $timespan = param('timespan');
    $timespan ||= 'day';
    $timespan = lc($timespan);
    if ( !defined( $ValidTimespan->{$timespan} ) ) {
        $timespan = 'day';
    }
    return ($timespan);
}    # _get_param_timespan

sub _find_plugins {
    my $host    = shift;
    my %plugins = ();
    for ( my $i = 0 ; $i < @DataDirs ; $i++ ) {
        my $dir = $DataDirs[$i] . "/$host";
        my @tmp;
        my $dh;
        opendir( $dh, $dir ) or next;
        @tmp = grep { ( $_ !~ m/^\./ ) && ( -d "$dir/$_" ) } ( readdir($dh) );
        closedir($dh);
        for (@tmp) {
            my ( $plugin, $instance ) = split( m/-/, $_, 2 );
            $plugins{$plugin} = [] if ( !exists $plugins{$plugin} );
            push( @{ $plugins{$plugin} }, $instance );
        }
    }    # for (@DataDirs)
    return (%plugins);
}    # _find_plugins

sub _find_types {
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my %types           = ();
    for ( my $i = 0 ; $i < @DataDirs ; $i++ ) {
        my $dir =
            $DataDirs[$i]
          . "/$host/$plugin"
          . ( defined($plugin_instance) ? "-$plugin_instance" : '' );
        my @tmp;
        my $dh;
        opendir( $dh, $dir ) or next;
        @tmp =
          grep { ( $_ !~ m/^\./ ) && ( $_ =~ m/\.rrd$/i ) && ( -f "$dir/$_" ) }
          ( readdir($dh) );
        closedir($dh);
        for (@tmp) {
            my $name = "$_";
            $name =~ s/\.rrd$//i;
            my ( $type, $instance ) = split( m/-/, $name, 2 );
            $types{$type} = [] if ( !$types{$type} );
            push( @{ $types{$type} }, $instance ) if ( defined($instance) );
        }
    }    # for (@DataDirs)
    return (%types);
}    # _find_types

sub _find_files_for_host {
    my $host    = shift;
    my $ret     = {};
    my %plugins = _find_plugins($host);
    for ( keys %plugins ) {
        my $plugin           = $_;
        my $plugin_instances = $plugins{$plugin};
        if ( !$plugin_instances || !@$plugin_instances ) {
            $plugin_instances = ['-'];
        }
        $ret->{$plugin} = {};
        for (@$plugin_instances) {
            my $plugin_instance = defined($_) ? $_ : '-';
            my %types =
              _find_types( $host, $plugin,
                ( $plugin_instance ne '-' )
                ? $plugin_instance
                : undef );
            $ret->{$plugin}{$plugin_instance} = {};
            for ( keys %types ) {
                my $type           = $_;
                my $type_instances = $types{$type};
                $ret->{$plugin}{$plugin_instance}{$type} = {};
                for (@$type_instances) {
                    $ret->{$plugin}{$plugin_instance}{$type}{$_} = 1;
                }
                if ( !@$type_instances ) {
                    $ret->{$plugin}{$plugin_instance}{$type}{'-'} = 1;
                }
            }    # for (keys %types)
        }    # for (@$plugin_instances)
    }    # for (keys %plugins)
    return ($ret);
}    # _find_files_for_host

sub _find_files_for_hosts {
    my @hosts       = @_;
    my $all_plugins = {};
    for ( my $i = 0 ; $i < @hosts ; $i++ ) {
        my $tmp = _find_files_for_host( $hosts[$i] );
        _files_union( $all_plugins, $tmp );
    }
    return ($all_plugins);
}    # _find_files_for_hosts

sub _files_union {
    my $dest = shift;
    my $src  = shift;
    for ( keys %$src ) {
        my $plugin = $_;
        $dest->{$plugin} ||= {};
        for ( keys %{ $src->{$plugin} } ) {
            my $pinst = $_;
            $dest->{$plugin}{$pinst} ||= {};
            for ( keys %{ $src->{$plugin}{$pinst} } ) {
                my $type = $_;
                $dest->{$plugin}{$pinst}{$type} ||= {};
                for ( keys %{ $src->{$plugin}{$pinst}{$type} } ) {
                    my $tinst = $_;
                    $dest->{$plugin}{$pinst}{$type}{$tinst} = 1;
                }
            }
        }
    }
}    # _files_union

sub _files_plugin_inst_count {
    my $src = shift;
    my $i   = 0;
    for ( keys %$src ) {
        if ( exists( $MetaGraphDefs->{$_} ) ) {
            $i++;
        }
        else {
            $i = $i + keys %{ $src->{$_} };
        }
    }
    return ($i);
}    # _files_plugin_count

sub list_hosts_json {
    my @hosts    = _find_hosts();
    my $host_ref = \@hosts;
    @hosts = sort (@hosts);

    # Enable autoflush
    $| = 1;
    print STDOUT header(
        -Content_Type => 'application/json',
        -Charset      => 'utf-8'
    );
    print STDOUT to_json( $host_ref, { pretty => 1, indent => 2 } );
    return (1);
}    # list_hosts_json

sub _string_to_color {
    my $color = shift;
    if ( $color =~ m/([0-9A-Fa-f][0-9A-Fa-f])([0-9A-Fa-f][0-9A-Fa-f])([0-9A-Fa-f][0-9A-Fa-f])/)
    {
        return ( [ hex($1) / 255.0, hex($2) / 255.0, hex($3) / 255.0 ] );
    }
    return;
}    # _string_to_color

sub _color_to_string {
    confess("Wrong number of arguments") if ( @_ != 1 );
    return (sprintf( '%02hx%02hx%02hx', map { int( 255.0 * $_ ) } @{ $_[0] } ) );
}    # _color_to_string

sub _get_random_color {
    my ( $r, $g, $b ) = ( rand(), rand() );
    my $min = 0.0;
    my $max = 1.0;
    if ( ( $r + $g ) < 1.0 ) {
        $min = 1.0 - ( $r + $g );
    }
    else {
        $max = 2.0 - ( $r + $g );
    }
    $b = $min + ( rand() * ( $max - $min ) );
    return ( [ $r, $g, $b ] );
}    # _get_random_color

sub _get_faded_color {
    my $fg = shift;
    my $bg;
    my %opts = @_;
    my $ret = [ undef, undef, undef ];
    $opts{'background'} ||= [ 1.0, 1.0, 1.0 ];
    $opts{'alpha'} ||= 0.25;
    if ( !ref( $opts{'background'} ) ) {
        $opts{'background'} = _string_to_color( $opts{'background'} )
          or confess( "Cannot parse background color " . $opts{'background'} );
    }
    $bg = $opts{'background'};
    for ( my $i = 0 ; $i < 3 ; $i++ ) {
        $ret->[$i] =
          ( $opts{'alpha'} * $fg->[$i] ) +
          ( ( 1.0 - $opts{'alpha'} ) * $bg->[$i] );
    }
    return ($ret);
}    # _get_faded_color

sub _custom_sort_arrayref {
    my $array_ref  = shift;
    my $array_sort = shift;
    my %elements   = map { $_ => 1 } (@$array_ref);
    splice( @$array_ref, 0 );
    for (@$array_sort) {
        next if ( !exists( $elements{$_} ) );
        push( @$array_ref, $_ );
        delete( $elements{$_} );
    }
    push( @$array_ref, sort ( keys %elements ) );
}    # _custom_sort_arrayref

sub action_show_host {
    my @hosts = _get_param_host();
    @hosts = sort (@hosts);
    my $timespan    = _get_param_timespan();
    my $all_plugins = _find_files_for_hosts(@hosts);
    my $url_prefix =
        script_name()
      . '?action=show_plugin'
      . join( '', map { ';host=' . uri_escape($_) } (@hosts) )
      . ';timespan='
      . uri_escape($timespan);
    print
qq(<div class="ui-widget-header ui-corner-top"><h3>Available Plugins</h3></div>\n);
    print
qq(<div id="plugin-container" class="ui-widget-content ui-corner-bottom  "><ul>\n);
    for ( sort ( keys %$all_plugins ) ) {
        my $plugin      = $_;
        my $plugin_html = encode_entities($plugin);
        my $url_plugin  = $url_prefix . ';plugin=' . uri_escape($plugin);
        print qq(      <li><a href="$url_plugin">$plugin_html</a></li>\n);
    }
    print "</ul></div>\n";
}    # action_show_host

sub action_show_host_json
{
    my @hosts = _get_param_host ();
    my $all_plugins = _find_files_for_hosts (@hosts);

    # Enable autoflush
    $| = 1;

    print STDOUT header (-Content_Type => 'application/json',
    -Charset => 'utf-8'
    );
    print STDOUT to_json ([sort (keys %$all_plugins)],
    { pretty => 1, indent => 2 }) . "\n";
    return (1);
} # action_show_host_json


sub action_show_plugin {
    my @hosts           = _get_param_host();
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $timespan        = _get_param_timespan();
    my $hosts_url   = join( ';', map { 'host=' . uri_escape($_) } (@hosts) );
    my $url_prefix  = script_name() . "?$hosts_url";
    my $all_plugins = {};
    my $plugins_per_host = {};
    my $selected_plugins = {};

    for ( my $i = 0 ; $i < @hosts ; $i++ ) {
        $plugins_per_host->{ $hosts[$i] } = _find_files_for_host( $hosts[$i] );
        _files_union( $all_plugins, $plugins_per_host->{ $hosts[$i] } );
    }
    for ( param('plugin') ) {
        if ( defined( $all_plugins->{$_} ) ) {
            $selected_plugins->{$_} = 1;
        }
    }
    for (@hosts) {
        print "\t<h2>", encode_entities($_), "</h2>\n";
    }
    for ( sort ( keys %$selected_plugins ) ) {
        my $plugin      = $_;
        my $plugin_html = encode_entities($plugin);
        my $plugin_url  = "$url_prefix;plugin=" . uri_escape($plugin);
        my $all_pinst   = $all_plugins->{$plugin};
        print qq(<ul class="sortable">);
        for ( sort ( keys %$all_pinst ) ) {
            my $pinst      = $_;
            my $pinst_html = '';
            my $pinst_url  = $plugin_url;
            if ( $pinst ne '-' ) {
                $pinst_html = encode_entities($pinst);
                $pinst_url .= ';plugin_instance=' . uri_escape($pinst);
            }
            my $files_printed = 0;
            my $files_num = _files_plugin_inst_count( $all_pinst->{$pinst} );
            if ( $files_num < 1 ) {
                next;
            }
            my $rowspan = ( $files_num == 1 ) ? '' : qq( rowspan="$files_num");
            for ( sort ( keys %{ $all_plugins->{$plugin}{$pinst} } ) ) {
                my $type      = $_;
                my $type_html = encode_entities($type);
                my $type_url  = "$pinst_url;type=" . uri_escape($type);
                if ( exists( $MetaGraphDefs->{$type} ) ) {
                    my $graph_url =
                        script_name()
                      . '?action=show_graph'
                      . ';plugin='
                      . uri_escape($plugin)
                      . ';type='
                      . uri_escape($type);
                    if ( $pinst ne '-' ) {
                        $graph_url .= ';plugin_instance=' . uri_escape($pinst);
                    }
                    for (@hosts) {
                        my $host = $_;
                        my $host_graph_url =
                          $graph_url . ';host=' . uri_escape($host);
                        print qq(<li class="ui-widget graph-image">);
                        if ( $files_printed == 0 ) {
                            my $title = $plugin_html;
                            if ( $pinst ne '-' ) {
                                $title .= " ($pinst_html)";
                            }
                            print "\t<h3>$title</h3>\n";
                        }
                        if ( exists $plugins_per_host->{$host}{$plugin}{$pinst}{$type} )
                        {
                            my $host_graph_url_hour =
                              $host_graph_url . ';timespan=hour';
                            my $host_graph_url_day =
                              $host_graph_url . ';timespan=day';
                            my $host_graph_url_week =
                              $host_graph_url . ';timespan=week';
                            my $host_graph_url_month =
                              $host_graph_url . ';timespan=month';
                            my $host_graph_url_year =
                              $host_graph_url . ';timespan=year';
                            my $host_graph_url_decade =
                              $host_graph_url . ';timespan=decade';
                            my $menu_buttons = _get_menu_buttons();
                            print qq(<ul>);
                            print qq(<li class="gc hour">$menu_buttons<img src="$host_graph_url_hour" /></li>);
                            print qq(<li class="gc day">$menu_buttons<img src="$host_graph_url_day" /></li>);
                            print qq(<li class="gc week">$menu_buttons<img src="$host_graph_url_week" /></li>);
                            print qq(<li class="gc month">$menu_buttons<img src="$host_graph_url_month" /></li>);
                            print qq(<li class="gc year">$menu_buttons<img src="$host_graph_url_year" /></li>);
                            print qq(<li class="gc decade">$menu_buttons<img src="$host_graph_url_decade" /></li>);
                            print qq(</ul>);
                        }
                        print "</li>\n";
                    }    # for (my $k = 0; $k < @hosts; $k++)
                    $files_printed++;
                    next;    # pinst
                }    # if (exists ($MetaGraphDefs->{$type}))
                for (
                    sort ( keys %{ $all_plugins->{$plugin}{$pinst}{$type} } ) )
                {
                    my $tinst     = $_;
                    my $graph_url =
                        script_name()
                      . '?action=show_graph'
                      . ';plugin='
                      . uri_escape($plugin)
                      . ';type='
                      . uri_escape($type);
                    if ( $pinst ne '-' ) {
                        $graph_url .= ';plugin_instance=' . uri_escape($pinst);
                    }
                    if ( $tinst ne '-' ) {
                        $graph_url .= ';type_instance=' . uri_escape($tinst);
                    }
                    for ( my $k = 0 ; $k < @hosts ; $k++ ) {
                        my $host = $hosts[$k];
                        my $host_graph_url =
                          $graph_url . ';host=' . uri_escape($host);
                        print qq(<li class="ui-widget graph-image">);
                        if ( $plugins_per_host->{$host}{$plugin}{$pinst}{$type}
                            {$tinst} )
                        {
                            my $host_graph_url_hour = $host_graph_url . ';timespan=hour';
                            my $host_graph_url_day = $host_graph_url . ';timespan=day';
                            my $host_graph_url_week = $host_graph_url . ';timespan=week';
                            my $host_graph_url_month = $host_graph_url . ';timespan=month';
                            my $host_graph_url_year = $host_graph_url . ';timespan=year';
                            my $host_graph_url_decade = $host_graph_url . ';timespan=decade';
                            my $menu_buttons = _get_menu_buttons();
                            print qq(<ul>);
                            print qq(<li class="gc hour">$menu_buttons<img src="$host_graph_url_hour" /></li>);
                            print qq(<li class="gc day">$menu_buttons<img src="$host_graph_url_day" /></li>);
                            print qq(<li class="gc week">$menu_buttons<img src="$host_graph_url_week" /></li>);
                            print qq(<li class="gc month">$menu_buttons<img src="$host_graph_url_month" /></li>);
                            print qq(<li class="gc year">$menu_buttons<img src="$host_graph_url_year" /></li>);
                            print qq(<li class="gc decade">$menu_buttons<img src="$host_graph_url_decade" /></li>);
                            print qq(</ul>);
                        }
                        print "</li>\n";
                    }    # for (my $k = 0; $k < @hosts; $k++)
                    $files_printed++;
                }    # for ($tinst)
            }    # for ($type)
        }    # for ($pinst)
        print "</ul>";
    }    # for ($plugin)
}    # action_show_plugin

sub action_show_plugin_json {
    my @hosts           = _get_param_host();
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $timespan        = _get_param_timespan();
    my $hosts_url   = join( ';', map { 'host=' . uri_escape($_) } (@hosts) );
    my $url_prefix  = script_name() . "?$hosts_url";
    my $all_plugins = {};
    my $plugins_per_host = {};
    my $selected_plugins = {};
    my @plugin_list_hour =  ();
    my @plugin_list_day =   ();
    my @plugin_list_week =  ();
    my @plugin_list_month = ();
    my @plugin_list_year =  ();
    my @plugin_list_decade = ();
    my $p = param('plugin');
    my @plugins = ref $p eq 'ARRAY' ? @$p : ($p);

    for ( my $i = 0 ; $i < @hosts ; $i++ ) {
        $plugins_per_host->{ $hosts[$i] } = _find_files_for_host( $hosts[$i] );
        _files_union( $all_plugins, $plugins_per_host->{ $hosts[$i] } );
    }
    for ( @plugins ) {
        if ( defined( $all_plugins->{$_} ) ) {
            $selected_plugins->{$_} = 1;
        }
    }
    # TODO: send list of hosts

    for ( sort ( keys %$selected_plugins ) ) {
        my $plugin      = $_;
        my $plugin_html = encode_entities($plugin);
        my $plugin_url  = "$url_prefix;plugin=" . uri_escape($plugin);
        my $all_pinst   = $all_plugins->{$plugin};

        for ( sort ( keys %$all_pinst ) ) {
            my $pinst      = $_;
            my $pinst_html = '';
            my $pinst_url  = $plugin_url;
            if ( $pinst ne '-' ) {
                $pinst_html = encode_entities($pinst);
                $pinst_url .= ';plugin_instance=' . uri_escape($pinst);
            }
            my $files_printed = 0;
            my $files_num = _files_plugin_inst_count( $all_pinst->{$pinst} );
            if ( $files_num < 1 ) {
                next;
            }
            my $rowspan = ( $files_num == 1 ) ? '' : qq( rowspan="$files_num");
            for ( sort ( keys %{ $all_plugins->{$plugin}{$pinst} } ) ) {
                my $type      = $_;
                my $type_html = encode_entities($type);
                my $type_url  = "$pinst_url;type=" . uri_escape($type);
                if ( exists( $MetaGraphDefs->{$type} ) ) {
                    my $graph_url =
                        script_name()
                      . '?action=show_graph'
                      . ';plugin='
                      . uri_escape($plugin)
                      . ';type='
                      . uri_escape($type);
                    if ( $pinst ne '-' ) {
                        $graph_url .= ';plugin_instance=' . uri_escape($pinst);
                    }
                    for (@hosts) {
                        my $host = $_;
                        my $host_graph_url = $graph_url . ';host=' . uri_escape($host);

                        if ( exists $plugins_per_host->{$host}{$plugin}{$pinst}{$type} ) {
                            my $host_graph_url_hour = $host_graph_url . ';timespan=hour';
                            my $host_graph_url_day = $host_graph_url . ';timespan=day';
                            my $host_graph_url_week = $host_graph_url . ';timespan=week';
                            my $host_graph_url_month = $host_graph_url . ';timespan=month';
                            my $host_graph_url_year = $host_graph_url . ';timespan=year';
                            my $host_graph_url_decade = $host_graph_url . ';timespan=decade';
                            push( @plugin_list_hour, $host_graph_url_hour);
                            push( @plugin_list_day, $host_graph_url_day);
                            push( @plugin_list_week, $host_graph_url_week);
                            push( @plugin_list_month, $host_graph_url_month);
                            push( @plugin_list_year, $host_graph_url_year);
                            push( @plugin_list_decade, $host_graph_url_decade);
                        }
                    }    # for (my $k = 0; $k < @hosts; $k++)
                    $files_printed++;
                    next;    # pinst
                }    # if (exists ($MetaGraphDefs->{$type}))
                for ( sort ( keys %{ $all_plugins->{$plugin}{$pinst}{$type} } ) )
                {
                    my $tinst     = $_;
                    my $graph_url =
                        script_name()
                      . '?action=show_graph'
                      . ';plugin='
                      . uri_escape($plugin)
                      . ';type='
                      . uri_escape($type);
                    if ( $pinst ne '-' ) {
                        $graph_url .= ';plugin_instance=' . uri_escape($pinst);
                    }
                    if ( $tinst ne '-' ) {
                        $graph_url .= ';type_instance=' . uri_escape($tinst);
                    }
                    for ( my $k = 0 ; $k < @hosts ; $k++ ) {
                        my $host = $hosts[$k];
                        my $host_graph_url =
                          $graph_url . ';host=' . uri_escape($host);
                        if ( $plugins_per_host->{$host}{$plugin}{$pinst}{$type}{$tinst} )
                        {
                            my $host_graph_url_hour = $host_graph_url . ';timespan=hour';
                            my $host_graph_url_day = $host_graph_url . ';timespan=day';
                            my $host_graph_url_week = $host_graph_url . ';timespan=week';
                            my $host_graph_url_month = $host_graph_url . ';timespan=month';
                            my $host_graph_url_year = $host_graph_url . ';timespan=year';
                            my $host_graph_url_decade = $host_graph_url . ';timespan=decade';
                            push( @plugin_list_hour, $host_graph_url_hour);
                            push( @plugin_list_day, $host_graph_url_day);
                            push( @plugin_list_week, $host_graph_url_week);
                            push( @plugin_list_month, $host_graph_url_month);
                            push( @plugin_list_year, $host_graph_url_year);
                            push( @plugin_list_decade, $host_graph_url_decade);
                        }
                    }    # for (my $k = 0; $k < @hosts; $k++)
                    $files_printed++;
                }    # for ($tinst)
            }    # for ($type)
        }    # for ($pinst)
    }    # for ($plugin)

    # Enable autoflush
    $| = 1;

    print STDOUT header (-Content_Type => 'application/json',
    -Charset => 'utf-8');
    print STDOUT to_json ({hour => [@plugin_list_hour],
                           day =>  [@plugin_list_day] ,
                           week => [@plugin_list_week],
                           month => [@plugin_list_month],
                           year => [@plugin_list_year],
                           decade => [@plugin_list_decade]},
    { pretty => 1, indent => 2 }) . "\n";
    return (1);
}    # action_show_plugin_json

sub action_show_type {
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instance   = shift;
    my $host_url        = uri_escape($host);
    my $plugin_url      = uri_escape($plugin);
    my $plugin_html     = encode_entities($plugin);
    my $plugin_instance_url =
      defined($plugin_instance) ? uri_escape($plugin_instance) : undef;
    my $type_url = uri_escape($type);
    my $type_instance_url =
      defined($type_instance) ? uri_escape($type_instance) : undef;
    my $url_prefix =
      script_name() . "?action=show_plugin;host=$host_url;plugin=$plugin_url";
    $url_prefix .= ";plugin_instance=$plugin_instance_url"
      if ( defined($plugin_instance) );
    print qq(    <div><a href="$url_prefix">Back to plugin &quot;$plugin_html&quot;</a></div>\n);
    $url_prefix = script_name() . "?action=show_graph;host=$host_url;plugin=$plugin_url";
    $url_prefix .= ";plugin_instance=$plugin_instance_url"
      if ( defined($plugin_instance) );
    $url_prefix .= ";type=$type_url";
    $url_prefix .= ";type_instance=$type_instance_url"
      if ( defined($type_instance) );

    for (qw(hour day week month year decade)) {
        my $timespan = $_;
        print qq#  <div><img src="$url_prefix;timespan=$timespan" /></div>\n#;
    }
}    # action_show_type

sub action_show_graph {
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instance   = shift;
    my @rrd_args;
    my $title;
    my %times = (
        hour  => -3600,
        day   => -86400,
        week  => 7 * -86400,
        month => 31 * -86400,
        year  => 366 * -86400,
        decade => 10 * 366 * -86400
    );

    my $start_time;
    my $end_time;
    if (defined($Args->{'end'})) {
        $start_time = $Args->{'start'};
        $end_time = $Args->{'end'};
    } else {
        $start_time = $times{ $Args->{'timespan'} } || -86400;
    }

    #print STDERR Data::Dumper->Dump ([$Args], ['Args']);
    # FIXME

    # REDIS plugin generates results for MEMORY, but default RRD memory definition
    # causes error. That's why we should redifine rrd_args for redis/memory graph
    #
    if( $plugin eq 'redis' && $type eq 'memory' ) {
        @rrd_args = @{ $GraphDefs->{'gauge'} };
    } else {
        if ( exists( $MetaGraphDefs->{$type} ) ) {
            my %types = _find_types( $host, $plugin, $plugin_instance );
            return $MetaGraphDefs->{$type}
              ->( $host, $plugin, $plugin_instance, $type, $types{$type} );
        }
    }
    return if ( !defined( $GraphDefs->{$type} ) );

    # REDIS plugin generates results for MEMORY, but default RRD memory definition
    # causes error. That's why we should redifine rrd_args for redis/memory graph
    #
    if( $plugin eq 'redis' && $type eq 'memory' ) {
        @rrd_args = @{ $GraphDefs->{'gauge'} };
    } else {
        @rrd_args = @{ $GraphDefs->{$type} };
    }
    my $short_title =
        ( defined($plugin_instance) ? "$plugin_instance/" : '' ) . "$type"
      . ( defined($type_instance)   ? "-$type_instance"   : '' );
    $title =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type"
      . ( defined($type_instance) ? "-$type_instance" : '' );

    for ( my $i = 0 ; $i < @DataDirs ; $i++ ) {
        my $file = $DataDirs[$i] . "/$title.rrd";
        next if ( !-f $file );
	# Workaround some RRDCACHED_FLUSH absolute path issues.
        $title =~ s/:/\\:/g;
        s/{file}/$title.rrd/ for (@rrd_args);
	chdir($DataDirs[$i]);
    if (defined($Args->{'end'})) {
        RRDs::graph(
            '-',
            '-a', $OutputFormat,
            '-s', $start_time,
            '-e', $end_time,
            '-t', $short_title,
            @RRDDefaultArgs,
            @rrd_args
        );
    } else {
        RRDs::graph(
            '-',
            '-a', $OutputFormat,
            '-s', $start_time,
            '-t', $short_title,
            @RRDDefaultArgs,
            @rrd_args
        );
    }
        if ( my $err = RRDs::error() ) {
            die("RRDs::graph: $err");
        }
    }
}    # action_show_graph

sub print_header {
    print <<HEAD;
Content-Type: application/xhtml+xml; charset=utf-8
Cache-Control: no-cache

HEAD
}    # print_header

sub print_footer {
    print <<FOOT;
FOOT
}    # print_footer

sub _get_format_param {
    if ( param('format') ) {
        my $temp = param('format') || '';
        $temp = uc($temp);
        if ( $temp =~ m/^(PNG|SVG|EPS|PDF)$/ ) {
            $OutputFormat = $temp;
            if    ( $OutputFormat eq 'SVG' ) { $ContentType = 'image/svg+xml'; }
            elsif ( $OutputFormat eq 'EPS' ) { $ContentType = 'image/eps'; }
            elsif ( $OutputFormat eq 'PDF' ) {
                $ContentType = 'application/pdf';
            }
        }
    } else {
        $OutputFormat = 'SVG';
        $ContentType = 'image/svg+xml';
    }
}

sub main {
    read_config();
    validate_args();
    _get_format_param();

    if ( defined( $Args->{'action'} )
        && ( $Args->{'action'} eq 'hostlist_json' ) )
    {
        return ( list_hosts_json() );
    }
    if ( defined( $Args->{'action'} )
        && ( $Args->{'action'} eq 'pluginlist_json' ) )
    {
        return ( action_show_host_json() );
    }

    if ( defined( $Args->{'action'} )
        && ( $Args->{'action'} eq 'graphs_json' ) )
    {
        return ( action_show_plugin_json() );
    }
    if (   defined( $Args->{'host'} )
        && defined( $Args->{'plugin'} )
        && defined( $Args->{'type'} )
        && ( $Args->{'action'} eq 'show_graph' ) )
    {
        $| = 1;
        if(defined ($Args->{'enable-caching'})){
            print STDOUT header(-Content_Type => $ContentType,
                                -Cache_Control=>'maxage=3600',
                                -Pragma=>'public');
        } else {
            print STDOUT header( -Content_Type => $ContentType);
        }


        action_show_graph(
            $Args->{'host'},            $Args->{'plugin'},
            $Args->{'plugin_instance'}, $Args->{'type'},
            $Args->{'type_instance'}
        );
        return (0);
    }

    # custom graphdef
    if (   defined( $Args->{'host'} )
        && defined( $Args->{'plugin'} )
        && defined( $Args->{'type'} )
        && ( $Args->{'action'} eq 'show_custom_graph' ) )
    {
        $| = 1;
        if(defined ($Args->{'enable-caching'})){
            print STDOUT header(-Content_Type => $ContentType,
                                -Cache_Control=>'maxage=3600',
                                -Pragma=>'public' );
        } else {
            print STDOUT header( -Content_Type => $ContentType);
        }
        action_show_graph(
            $Args->{'host'},            $Args->{'plugin'},
            $Args->{'plugin_instance'}, $Args->{'type'},
            $Args->{'type_instance'}
        );
        return (0);
    }
    print_header();
    print "<div>";
    if ( !$Args->{'host'} ) {
        print "<p>No host defined</p>"
    }
    elsif ( !$Args->{'plugin'} ) {
        action_show_host( $Args->{'host'} );
    }
    elsif ( !$Args->{'type'} ) {
        action_show_plugin( $Args->{'plugin'}, $Args->{'plugin_instance'} );
    }
    else {
        action_show_type(
            $Args->{'host'},            $Args->{'plugin'},
            $Args->{'plugin_instance'}, $Args->{'type'},
            $Args->{'type_instance'}
        );
    }
    print "</div>\n";
    return (0);
}

sub load_graph_definitions {
    # Check for dark theme
    my $dark = (defined(param('theme')) && param('theme') eq 'dark') ? 1 : 0;

    if ($dark) {
        @RRDDefaultArgs = (
            '--rigid',
            '-w', '1040', '-h', '360',
            '--alt-autoscale-max',
            '--alt-y-grid',
            '--slope-mode',
            '--font', 'TITLE:28:Monospace',
            '--font', 'AXIS:10:Monospace',
            '--font', 'LEGEND:12:Monospace',
            '--font', 'UNIT:12:Monospace',
            '-c', 'BACK#222222FF',   # dark background
            '-c', 'CANVAS#222222FF',
            '-c', 'FONT#EEEEEEFF',
            '-c', 'SHADEA#222222FF',
            '-c', 'SHADEB#222222FF',
            '-c', 'GRID#666666FF',
            '-c', 'MGRID#666666FF',
            '-c', 'FRAME#666666FF',
            '-c', 'ARROW#FFFFFF',
            '-c', 'AXIS#FFFFFF',
            '-i',
        );
    }

    my $Canvas      = $dark ? '222222' : 'FFFFFF';
    my $FullRed     = $dark ? 'FF6666' : 'FF0000';
    my $FullGreen   = $dark ? '66FF66' : '00E000';
    my $FullBlue    = $dark ? '6666FF' : '0000FF';
    my $FullYellow  = $dark ? 'FFFF66' : 'F0A000';
    my $FullCyan    = $dark ? '66FFFF' : '00A0FF';
    my $FullMagenta = $dark ? 'FF66FF' : 'A000FF';
    my $HalfRed     = $dark ? 'FF9999' : 'F7B7B7';
    my $HalfGreen   = $dark ? '99FF99' : 'B7EFB7';
    my $HalfBlue    = $dark ? '9999FF' : 'B7B7F7';
    my $HalfYellow  = $dark ? 'FFFF99' : 'F3DFB7';
    my $HalfCyan    = $dark ? '99FFFF' : 'B7DFF7';
    my $HalfMagenta = $dark ? 'FF99FF' : 'DFB7F7';
    my $HalfBlueGreen = $dark ? '88CCCC' : '89B3C9';
    $GraphDefs = {
        activity => [
            'DEF:avg={file}:value:AVERAGE',
            'CDEF:all_area=avg,UN,UNKN,1,IF',
            'CDEF:act_area=avg,0,GT,1,UNKN,IF',
            'CDEF:avg_sum=avg,PREV,ADDNAN',
            'CDEF:all_sum=all_area,PREV,ADDNAN',
            'CDEF:avg_msec=avg_sum,STEPWIDTH,*,1000,*',
            'CDEF:avg_perc=avg_sum,100,*,all_sum,/',
            "AREA:all_area#$HalfGreen",
            "AREA:act_area#$HalfRed",
            "LINE:avg#$FullRed:Active",
            'GPRINT:avg_msec:LAST:%02h\:%02m Total:valstrfduration',
            'GPRINT:avg_perc:LAST:[ %.0lf%% ]\l'
        ],
        apache_bytes => [
            'DEF:min_raw={file}:value:MIN',
            'DEF:avg_raw={file}:value:AVERAGE',
            'DEF:max_raw={file}:value:MAX',
            'CDEF:min=min_raw,8,*',
            'CDEF:avg=avg_raw,8,*',
            'CDEF:max=max_raw,8,*',
            'CDEF:mytime=avg_raw,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg_raw,UN,0,avg_raw,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:avg#$HalfBlue",
            "LINE1:avg#$FullBlue:Bit/s",
            'GPRINT:min:MIN:%5.1lf%s Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%sB Total)\l'
        ],
        apache_connections => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Connections",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        apache_idle_workers => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Idle Workers",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        apache_requests => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Requests/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        connections => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Connections/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        conntrack => [
            '-v', 'Entries',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Count",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        cache_result => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Requests/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        hash_collisions => [
            '-v',
            'Collisions',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:mytime=avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg,UN,0,avg,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Hash Collisions ",
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%s Total)\l'
        ],
        io_octets => ['-v', 'Octets/s',
            'DEF:out_min={file}:tx:MIN',
            'DEF:out_avg={file}:tx:AVERAGE',
            'DEF:out_max={file}:tx:MAX',
            'DEF:inc_min={file}:rx:MIN',
            'DEF:inc_avg={file}:rx:AVERAGE',
            'DEF:inc_max={file}:rx:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Written",
            'GPRINT:out_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:out_max:MAX:%6.2lf Max,',
            'GPRINT:out_avg:LAST:%6.2lf Last\l',
            "LINE1:inc_avg#$FullBlue:Read   ",
            'GPRINT:inc_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:inc_max:MAX:%6.2lf Max,',
            'GPRINT:inc_avg:LAST:%6.2lf Last\l'
        ],
        memory_throttle_count => [
            '-v',
            'Memory Throttle Count',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:mytime=avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg,UN,0,avg,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Memory Throttles ",
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%s Total)\l'
        ],
        mutex_operations => [
            '-v',
            'Mutex Operations',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:mytime=avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg,UN,0,avg,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Mutex Ops ",
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%s Total)\l'
        ],
        cache_ratio => ['-v', 'Cache Ratio',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            'CDEF:bsm=temp_max,temp_max,-',
            'CDEF:bsmn=temp_max,1,+,temp_max,-',
            "AREA:temp_max#$HalfBlue",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullBlue:Ratio ",
            'GPRINT:temp_min:MIN:%6.2lf Min,',
            'GPRINT:temp_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:temp_max:MAX:%6.2lf Max,',
            'GPRINT:temp_avg:LAST:%6.2lf Last\l',
            'LINE2:bsm#FFFFFF',
            'LINE3:bsmn#FFFFFF'
        ],
        cache_operation => [
            '-v',
            'Cache Operations',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:mytime=avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg,UN,0,avg,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Cache Ops ",
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%s Total)\l'
        ],
        cache_eviction => [
            '-v',
            'Cache Evictions',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:mytime=avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg,UN,0,avg,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Cache Evictions ",
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%s Total)\l'
        ],
        apache_scoreboard => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Processes",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        bitrate => [
            '-v',
            'Bits/s',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Bits/s",
            'GPRINT:min:MIN:%5.1lf%s Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s Average,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last\l'
        ],
        charge => [
            '-v',
            'Ah',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Charge",
            'GPRINT:min:MIN:%5.1lf%sAh Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%sAh Avg,',
            'GPRINT:max:MAX:%5.1lf%sAh Max,',
            'GPRINT:avg:LAST:%5.1lf%sAh Last\l'
        ],
        contextswitch => [
            'DEF:avg={file}:contextswitches:AVERAGE',
            'DEF:min={file}:contextswitches:MIN',
            'DEF:max={file}:contextswitches:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Switches/s",
            'GPRINT:min:MIN:%4.1lf ms Min,',
            'GPRINT:avg:AVERAGE:%4.1lf ms Avg,',
            'GPRINT:max:MAX:%4.1lf ms Max,',
            'GPRINT:avg:LAST:%4.1lf ms Last'
        ],
        cpu => [
            '-v',
            'CPU load',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Percent",
            'GPRINT:min:MIN:%6.2lf%% Min,',
            'GPRINT:avg:AVERAGE:%6.2lf%% Avg,',
            'GPRINT:max:MAX:%6.2lf%% Max,',
            'GPRINT:avg:LAST:%6.2lf%% Last\l'
        ],
       virt_vcpu => [
            '-v', 'CPU load (%)',
            '-X', '0',
            'DEF:avg_1={file}:value:AVERAGE',
            'DEF:min_1={file}:value:MIN',
            'DEF:max_1={file}:value:MAX',
            'CDEF:avg=avg_1,10000000,/',
            'CDEF:min=min_1,10000000,/',
            'CDEF:max=max_1,10000000,/',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Percent",
            'GPRINT:min:MIN:%6.2lf%% Min,',
            'GPRINT:avg:AVERAGE:%6.2lf%% Avg,',
            'GPRINT:max:MAX:%6.2lf%% Max,',
            'GPRINT:avg:LAST:%6.2lf%% Last\l'
        ],
        virt_cpu_total => [
            '-v', 'CPU load (%)',
            '-X', '0',
            'DEF:avg_1={file}:value:AVERAGE',
            'DEF:min_1={file}:value:MIN',
            'DEF:max_1={file}:value:MAX',
            'CDEF:avg=avg_1,10000000,/',
            'CDEF:min=min_1,10000000,/',
            'CDEF:max=max_1,10000000,/',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Percent",
            'GPRINT:min:MIN:%6.2lf%% Min,',
            'GPRINT:avg:AVERAGE:%6.2lf%% Avg,',
            'GPRINT:max:MAX:%6.2lf%% Max,',
            'GPRINT:avg:LAST:%6.2lf%% Last\l'
        ],
        current => [
            '-v',
            'Ampere',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            'CDEF:avg_neg=avg,0,LE,avg,UNKN,IF',
            'CDEF:avg_pos=avg,0,GE,avg,UNKN,IF',
            'CDEF:avg_neg_ln=PREV(avg_neg),avg,avg_neg,IF',
            'CDEF:avg_pos_ln=PREV(avg_pos),avg,avg_pos,IF',
            'CDEF:max_neg=max,0,LT,max,UNKN,IF',
            'CDEF:max_pos=max,0,GT,max,UNKN,IF',
            'CDEF:min_neg=min,0,LT,min,UNKN,IF',
            'CDEF:min_pos=min,0,GT,min,UNKN,IF',
            "AREA:min_neg#$HalfRed",
            "AREA:max_pos#$HalfGreen",
            "AREA:max_neg#$Canvas",
            "AREA:min_pos#$Canvas",
            "LINE:avg_neg_ln#$FullRed:-",
            "LINE:avg_pos_ln#$FullGreen:+ Current",
            'GPRINT:min:MIN:%5.1lf%sA Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%sA Avg,',
            'GPRINT:max:MAX:%5.1lf%sA Max,',
            'GPRINT:avg:LAST:%5.1lf%sA Last\l'
        ],
        count => [
            '-v', 'Count', '-l', '0',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfRed",
            "AREA:min#$Canvas",
            "LINE1:max#$FullRed:Count ",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        counter => [
            '-v',
            'Count',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfRed",
            "AREA:min#$Canvas",
            "LINE1:max#$FullRed:Count ",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        http_requests => [
            '-v',
            'Count',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfRed",
            "AREA:min#$Canvas",
            "LINE1:max#$FullRed:Count ",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        pkg => [
            '-v',
            'FreeBSD PKG-NG',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:mytime=avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg,UN,0,avg,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:PKGs ",
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%s Total)\l'
        ],
        derive => [
            '-v',
            'Derive',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:mytime=avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg,UN,0,avg,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:max#$HalfRed",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullRed:Derive ",
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%s Total)\l'
        ],
        df => [
            '-v',
            'Percent',
            '-l',
            '0',
            'DEF:free_avg={file}:free:AVERAGE',
            'DEF:free_min={file}:free:MIN',
            'DEF:free_max={file}:free:MAX',
            'DEF:used_avg={file}:used:AVERAGE',
            'DEF:used_min={file}:used:MIN',
            'DEF:used_max={file}:used:MAX',
            'CDEF:total=free_avg,used_avg,+',
            'CDEF:free_pct=100,free_avg,*,total,/',
            'CDEF:used_pct=100,used_avg,*,total,/',
            'CDEF:free_acc=free_pct,used_pct,+',
            'CDEF:used_acc=used_pct',
            "AREA:free_acc#$HalfGreen",
            "AREA:used_acc#$HalfRed",
            "LINE1:free_acc#$FullGreen:Free",
            'GPRINT:free_min:MIN:%5.1lf%sB Min,',
            'GPRINT:free_avg:AVERAGE:%5.1lf%sB Avg,',
            'GPRINT:free_max:MAX:%5.1lf%sB Max,',
            'GPRINT:free_avg:LAST:%5.1lf%sB Last\l',
            "LINE1:used_acc#$FullRed:Used",
            'GPRINT:used_min:MIN:%5.1lf%sB Min,',
            'GPRINT:used_avg:AVERAGE:%5.1lf%sB Avg,',
            'GPRINT:used_max:MAX:%5.1lf%sB Max,',
            'GPRINT:used_avg:LAST:%5.1lf%sB Last\l'
        ],
        disk => [
            'DEF:rtime_avg={file}:rtime:AVERAGE',
            'DEF:rtime_min={file}:rtime:MIN',
            'DEF:rtime_max={file}:rtime:MAX',
            'DEF:wtime_avg={file}:wtime:AVERAGE',
            'DEF:wtime_min={file}:wtime:MIN',
            'DEF:wtime_max={file}:wtime:MAX',
            'CDEF:rtime_avg_ms=rtime_avg,1000,/',
            'CDEF:rtime_min_ms=rtime_min,1000,/',
            'CDEF:rtime_max_ms=rtime_max,1000,/',
            'CDEF:wtime_avg_ms=wtime_avg,1000,/',
            'CDEF:wtime_min_ms=wtime_min,1000,/',
            'CDEF:wtime_max_ms=wtime_max,1000,/',
            'CDEF:total_avg_ms=rtime_avg_ms,wtime_avg_ms,+',
            'CDEF:total_min_ms=rtime_min_ms,wtime_min_ms,+',
            'CDEF:total_max_ms=rtime_max_ms,wtime_max_ms,+',
            "AREA:total_max_ms#$HalfRed",
            "AREA:total_min_ms#$Canvas",
            "LINE1:wtime_avg_ms#$FullGreen:Write",
            'GPRINT:wtime_min_ms:MIN:%5.1lf%s Min,',
            'GPRINT:wtime_avg_ms:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:wtime_max_ms:MAX:%5.1lf%s Max,',
            'GPRINT:wtime_avg_ms:LAST:%5.1lf%s Last\n',
            "LINE1:rtime_avg_ms#$FullBlue:Read ",
            'GPRINT:rtime_min_ms:MIN:%5.1lf%s Min,',
            'GPRINT:rtime_avg_ms:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:rtime_max_ms:MAX:%5.1lf%s Max,',
            'GPRINT:rtime_avg_ms:LAST:%5.1lf%s Last\n',
            "LINE1:total_avg_ms#$FullRed:Total",
            'GPRINT:total_min_ms:MIN:%5.1lf%s Min,',
            'GPRINT:total_avg_ms:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:total_max_ms:MAX:%5.1lf%s Max,',
            'GPRINT:total_avg_ms:LAST:%5.1lf%s Last'
        ],
        disk_io_time => [
            '-v', 'IO-Time in Sec',
            'DEF:_iot_avg={file}:io_time:AVERAGE',
            'DEF:_iot_min={file}:io_time:MIN',
            'DEF:_iot_max={file}:io_time:MAX',
            'DEF:wiot_avg={file}:weighted_io_time:AVERAGE',
            'DEF:wiot_min={file}:weighted_io_time:MIN',
            'DEF:wiot_max={file}:weighted_io_time:MAX',
            "AREA:wiot_max#$HalfCyan",
            "AREA:wiot_min#$Canvas",
            "LINE1:_iot_avg#$FullBlue:         IO Time",
            'GPRINT:_iot_min:MIN:%5.0lf%ss Min,',
            'GPRINT:_iot_avg:AVERAGE:%5.0lf%ss Avg,',
            'GPRINT:_iot_max:MAX:%5.0lf%ss Max,',
            'GPRINT:_iot_avg:LAST:%5.0lf%ss Last\l',
            "LINE1:wiot_avg#$FullCyan:Weighted IO Time",
            'GPRINT:wiot_min:MIN:%5.0lf%ss Min,',
            'GPRINT:wiot_avg:AVERAGE:%5.0lf%ss Avg,',
            'GPRINT:wiot_max:MAX:%5.0lf%ss Max,',
            'GPRINT:wiot_avg:LAST:%5.0lf%ss Last\l',
        ],
        disk_octets => [
            '-v',
            'Bytes/s',
            'DEF:out_min={file}:write:MIN',
            'DEF:out_avg={file}:write:AVERAGE',
            'DEF:out_max={file}:write:MAX',
            'DEF:inc_min={file}:read:MIN',
            'DEF:inc_avg={file}:read:AVERAGE',
            'DEF:inc_max={file}:read:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            'CDEF:mytime=out_avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:out_avg_sample=out_avg,UN,0,out_avg,IF,sample_len,*',
            'CDEF:out_avg_sum=PREV,UN,0,PREV,IF,out_avg_sample,+',
            'CDEF:inc_avg_sample=inc_avg,UN,0,inc_avg,IF,sample_len,*',
            'CDEF:inc_avg_sum=PREV,UN,0,PREV,IF,inc_avg_sample,+',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Written",
            'GPRINT:out_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:out_max:MAX:%5.1lf%s Max,',
            'GPRINT:out_avg:LAST:%5.1lf%s Last',
            'GPRINT:out_avg_sum:LAST:(ca. %5.1lf%sB Total)\l',
            "LINE1:inc_avg#$FullBlue:Read   ",
            'GPRINT:inc_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:inc_max:MAX:%5.1lf%s Max,',
            'GPRINT:inc_avg:LAST:%5.1lf%s Last',
            'GPRINT:inc_avg_sum:LAST:(ca. %5.1lf%sB Total)\l'
        ],
        disk_merged => [
            '-v',
            'Merged Ops/s',
            'DEF:out_min={file}:write:MIN',
            'DEF:out_avg={file}:write:AVERAGE',
            'DEF:out_max={file}:write:MAX',
            'DEF:inc_min={file}:read:MIN',
            'DEF:inc_avg={file}:read:AVERAGE',
            'DEF:inc_max={file}:read:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Written",
            'GPRINT:out_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:out_max:MAX:%6.2lf Max,',
            'GPRINT:out_avg:LAST:%6.2lf Last\l',
            "LINE1:inc_avg#$FullBlue:Read   ",
            'GPRINT:inc_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:inc_max:MAX:%6.2lf Max,',
            'GPRINT:inc_avg:LAST:%6.2lf Last\l'
        ],
        disk_ops => [
            '-v',
            'Ops/s',
            'DEF:out_min={file}:write:MIN',
            'DEF:out_avg={file}:write:AVERAGE',
            'DEF:out_max={file}:write:MAX',
            'DEF:inc_min={file}:read:MIN',
            'DEF:inc_avg={file}:read:AVERAGE',
            'DEF:inc_max={file}:read:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Written",
            'GPRINT:out_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:out_max:MAX:%6.2lf Max,',
            'GPRINT:out_avg:LAST:%6.2lf Last\l',
            "LINE1:inc_avg#$FullBlue:Read   ",
            'GPRINT:inc_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:inc_max:MAX:%6.2lf Max,',
            'GPRINT:inc_avg:LAST:%6.2lf Last\l'
        ],
        disk_io_time => ['-v', 'ms',
            'DEF:out_min={file}:weighted_io_time:MIN',
            'DEF:out_avg={file}:weighted_io_time:AVERAGE',
            'DEF:out_max={file}:weighted_io_time:MAX',
            'DEF:inc_min={file}:io_time:MIN',
            'DEF:inc_avg={file}:io_time:AVERAGE',
            'DEF:inc_max={file}:io_time:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Weighted I/O Time",
            'GPRINT:out_avg:AVERAGE:%5.1lf%ss Avg,',
            'GPRINT:out_max:MAX:%5.1lf%ss Max,',
            'GPRINT:out_avg:LAST:%5.1lf%ss Last\l',
            "LINE1:inc_avg#$FullBlue:I/O Time         ",
            'GPRINT:inc_avg:AVERAGE:%5.1lf%ss Avg,',
            'GPRINT:inc_max:MAX:%5.1lf%ss Max,',
            'GPRINT:inc_avg:LAST:%5.1lf%ss Last\l'
        ],
        disk_time => [
            '-v',
            'Seconds/s',
            'DEF:out_min_raw={file}:write:MIN',
            'DEF:out_avg_raw={file}:write:AVERAGE',
            'DEF:out_max_raw={file}:write:MAX',
            'DEF:inc_min_raw={file}:read:MIN',
            'DEF:inc_avg_raw={file}:read:AVERAGE',
            'DEF:inc_max_raw={file}:read:MAX',
            'CDEF:out_min=out_min_raw,1000,/',
            'CDEF:out_avg=out_avg_raw,1000,/',
            'CDEF:out_max=out_max_raw,1000,/',
            'CDEF:inc_min=inc_min_raw,1000,/',
            'CDEF:inc_avg=inc_avg_raw,1000,/',
            'CDEF:inc_max=inc_max_raw,1000,/',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Written",
            'GPRINT:out_avg:AVERAGE:%5.1lf%ss Avg,',
            'GPRINT:out_max:MAX:%5.1lf%ss Max,',
            'GPRINT:out_avg:LAST:%5.1lf%ss Last\l',
            "LINE1:inc_avg#$FullBlue:Read   ",
            'GPRINT:inc_avg:AVERAGE:%5.1lf%ss Avg,',
            'GPRINT:inc_max:MAX:%5.1lf%ss Max,',
            'GPRINT:inc_avg:LAST:%5.1lf%ss Last\l'
        ],
        dns_traffic => [
            'DEF:rsp_min_raw={file}:responses:MIN',
            'DEF:rsp_avg_raw={file}:responses:AVERAGE',
            'DEF:rsp_max_raw={file}:responses:MAX',
            'DEF:qry_min_raw={file}:queries:MIN',
            'DEF:qry_avg_raw={file}:queries:AVERAGE',
            'DEF:qry_max_raw={file}:queries:MAX',
            'CDEF:rsp_min=rsp_min_raw,8,*',
            'CDEF:rsp_avg=rsp_avg_raw,8,*',
            'CDEF:rsp_max=rsp_max_raw,8,*',
            'CDEF:qry_min=qry_min_raw,8,*',
            'CDEF:qry_avg=qry_avg_raw,8,*',
            'CDEF:qry_max=qry_max_raw,8,*',
            'CDEF:overlap=rsp_avg,qry_avg,GT,qry_avg,rsp_avg,IF',
            'CDEF:mytime=rsp_avg_raw,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:rsp_avg_sample=rsp_avg_raw,UN,0,rsp_avg_raw,IF,sample_len,*',
            'CDEF:rsp_avg_sum=PREV,UN,0,PREV,IF,rsp_avg_sample,+',
            'CDEF:qry_avg_sample=qry_avg_raw,UN,0,qry_avg_raw,IF,sample_len,*',
            'CDEF:qry_avg_sum=PREV,UN,0,PREV,IF,qry_avg_sample,+',
            "AREA:rsp_avg#$HalfGreen",
            "AREA:qry_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:rsp_avg#$FullGreen:Responses",
            'GPRINT:rsp_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:rsp_max:MAX:%5.1lf%s Max,',
            'GPRINT:rsp_avg:LAST:%5.1lf%s Last',
            'GPRINT:rsp_avg_sum:LAST:(ca. %5.1lf%sB Total)\l',
            "LINE1:qry_avg#$FullBlue:Queries  ",

            #'GPRINT:qry_min:MIN:%5.1lf %s Min,',
            'GPRINT:qry_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:qry_max:MAX:%5.1lf%s Max,',
            'GPRINT:qry_avg:LAST:%5.1lf%s Last',
            'GPRINT:qry_avg_sum:LAST:(ca. %5.1lf%sB Total)\l'
        ],

        dns_octets => [
            'DEF:rsp_min_raw={file}:responses:MIN',
            'DEF:rsp_avg_raw={file}:responses:AVERAGE',
            'DEF:rsp_max_raw={file}:responses:MAX',
            'DEF:qry_min_raw={file}:queries:MIN',
            'DEF:qry_avg_raw={file}:queries:AVERAGE',
            'DEF:qry_max_raw={file}:queries:MAX',
            'CDEF:rsp_min=rsp_min_raw,8,*',
            'CDEF:rsp_avg=rsp_avg_raw,8,*',
            'CDEF:rsp_max=rsp_max_raw,8,*',
            'CDEF:qry_min=qry_min_raw,8,*',
            'CDEF:qry_avg=qry_avg_raw,8,*',
            'CDEF:qry_max=qry_max_raw,8,*',
            'CDEF:overlap=rsp_avg,qry_avg,GT,qry_avg,rsp_avg,IF',
            'CDEF:mytime=rsp_avg_raw,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:rsp_avg_sample=rsp_avg_raw,UN,0,rsp_avg_raw,IF,sample_len,*',
            'CDEF:rsp_avg_sum=PREV,UN,0,PREV,IF,rsp_avg_sample,+',
            'CDEF:qry_avg_sample=qry_avg_raw,UN,0,qry_avg_raw,IF,sample_len,*',
            'CDEF:qry_avg_sum=PREV,UN,0,PREV,IF,qry_avg_sample,+',
            "AREA:rsp_avg#$HalfGreen",
            "AREA:qry_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:rsp_avg#$FullGreen:Responses",
            'GPRINT:rsp_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:rsp_max:MAX:%5.1lf%s Max,',
            'GPRINT:rsp_avg:LAST:%5.1lf%s Last',
            'GPRINT:rsp_avg_sum:LAST:(ca. %5.1lf%sB Total)\l',
            "LINE1:qry_avg#$FullBlue:Queries  ",
            #'GPRINT:qry_min:MIN:%5.1lf %s Min,',
            'GPRINT:qry_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:qry_max:MAX:%5.1lf%s Max,',
            'GPRINT:qry_avg:LAST:%5.1lf%s Last',
            'GPRINT:qry_avg_sum:LAST:(ca. %5.1lf%sB Total)\l'
        ],
        dns_opcode => [
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Queries/s",
            'GPRINT:min:MIN:%9.3lf Min,',
            'GPRINT:avg:AVERAGE:%9.3lf Average,',
            'GPRINT:max:MAX:%9.3lf Max,',
            'GPRINT:avg:LAST:%9.3lf Last\l'
        ],
        email_count => [
            '-v',
            'Mails',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfMagenta",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullMagenta:Count ",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        email_size => [
            '-v',
            'Bytes',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfMagenta",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullMagenta:Count ",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        fork_rate => [
            '-v',
            'Forks/s',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Forks/s",
            'GPRINT:min:MIN:%5.1lf%s Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s Average,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last\l'
        ],
        spam_score => [
            '-v',
            'Score',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Score ",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        spam_check => [
            'DEF:avg={file}:hits:AVERAGE',
            'DEF:min={file}:hits:MIN',
            'DEF:max={file}:hits:MAX',
            "AREA:max#$HalfMagenta",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullMagenta:Count ",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        entropy => [
            '-v',
            'Bits',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Bits",
            'GPRINT:min:MIN:%4.0lfbit Min,',
            'GPRINT:avg:AVERAGE:%4.0lfbit Avg,',
            'GPRINT:max:MAX:%4.0lfbit Max,',
            'GPRINT:avg:LAST:%4.0lfbit Last\l'
        ],
        fanspeed => [
            '-v',
            'RPM',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfMagenta",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullMagenta:RPM",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        frequency => [
            '-v',
            'Hertz',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Frequency [Hz]",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        delay => [    # NTPd
            'DEF:s_avg={file}:value:AVERAGE',
            'DEF:s_min={file}:value:MIN',
            'DEF:s_max={file}:value:MAX',
            "AREA:s_max#$HalfBlue",
            "AREA:s_min#$Canvas",
            "LINE1:s_avg#$FullBlue:Delay",
            'GPRINT:s_min:MIN:%7.3lf%s Min,',
            'GPRINT:s_avg:AVERAGE:%7.3lf%s Avg,',
            'GPRINT:s_max:MAX:%7.3lf%s Max,',
            'GPRINT:s_avg:LAST:%7.3lf%s Last'
        ],
        time_dispersion => [    # NTPd
            'DEF:s_avg={file}:value:AVERAGE',
            'DEF:s_min={file}:value:MIN',
            'DEF:s_max={file}:value:MAX',
            "AREA:s_max#$HalfBlue",
            "AREA:s_min#$Canvas",
            "LINE1:s_avg#$FullBlue:Seconds",
            'GPRINT:s_min:MIN:%7.3lf%s Min,',
            'GPRINT:s_avg:AVERAGE:%7.3lf%s Avg,',
            'GPRINT:s_max:MAX:%7.3lf%s Max,',
            'GPRINT:s_avg:LAST:%7.3lf%s Last'
        ],
        frequency_offset => [    # NTPd
            'DEF:ppm_avg={file}:value:AVERAGE',
            'DEF:ppm_min={file}:value:MIN',
            'DEF:ppm_max={file}:value:MAX',
            "AREA:ppm_max#$HalfBlue",
            "AREA:ppm_min#$Canvas",
            "LINE1:ppm_avg#$FullBlue:Offset",
            'GPRINT:ppm_min:MIN:%5.2lf Min,',
            'GPRINT:ppm_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:ppm_max:MAX:%5.2lf Max,',
            'GPRINT:ppm_avg:LAST:%5.2lf Last'
        ],
        gauge => [
            '-v',
            'Value',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_max#$HalfBlue",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullBlue:Value",
            'GPRINT:temp_min:MIN:%6.2lf Min,',
            'GPRINT:temp_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:temp_max:MAX:%6.2lf Max,',
            'GPRINT:temp_avg:LAST:%6.2lf Last\l'
        ],
        listen_queue => [
            '-v',
            'Exec value',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_max#$HalfBlue",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullBlue:Exec value",
            'GPRINT:temp_min:MIN:%6.2lf Min,',
            'GPRINT:temp_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:temp_max:MAX:%6.2lf Max,',
            'GPRINT:temp_avg:LAST:%6.2lf Last\l'
        ],
        active_processes => [
            '-v',
            'Exec value',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_max#$HalfBlue",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullBlue:Exec value",
            'GPRINT:temp_min:MIN:%6.2lf Min,',
            'GPRINT:temp_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:temp_max:MAX:%6.2lf Max,',
            'GPRINT:temp_avg:LAST:%6.2lf Last\l'
        ],
        total_processes => [
            '-v',
            'Exec value',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_max#$HalfBlue",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullBlue:Exec value",
            'GPRINT:temp_min:MIN:%6.2lf Min,',
            'GPRINT:temp_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:temp_max:MAX:%6.2lf Max,',
            'GPRINT:temp_avg:LAST:%6.2lf Last\l'
        ],
        hddtemp => [
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_max#$HalfRed",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullRed:Temperature",
            'GPRINT:temp_min:MIN:%4.1lf Min,',
            'GPRINT:temp_avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:temp_max:MAX:%4.1lf Max,',
            'GPRINT:temp_avg:LAST:%4.1lf Last\l'
        ],
        humidity => [
            '-v',
            'Percent',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_max#$HalfGreen",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullGreen:Humidity",
            'GPRINT:temp_min:MIN:%4.1lf%% Min,',
            'GPRINT:temp_avg:AVERAGE:%4.1lf%% Avg,',
            'GPRINT:temp_max:MAX:%4.1lf%% Max,',
            'GPRINT:temp_avg:LAST:%4.1lf%% Last\l'
        ],
        if_errors => [
            '-v', 'Errors/s',
            'DEF:tx_min={file}:tx:MIN',
            'DEF:tx_avg={file}:tx:AVERAGE',
            'DEF:tx_max={file}:tx:MAX',
            'DEF:rx_min={file}:rx:MIN',
            'DEF:rx_avg={file}:rx:AVERAGE',
            'DEF:rx_max={file}:rx:MAX',
            'CDEF:overlap=tx_avg,rx_avg,GT,rx_avg,tx_avg,IF',
            'CDEF:mytime=tx_avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:tx_avg_sample=tx_avg,UN,0,tx_avg,IF,sample_len,*',
            'CDEF:tx_avg_sum=PREV,UN,0,PREV,IF,tx_avg_sample,+',
            'CDEF:rx_avg_sample=rx_avg,UN,0,rx_avg,IF,sample_len,*',
            'CDEF:rx_avg_sum=PREV,UN,0,PREV,IF,rx_avg_sample,+',
            "AREA:tx_avg#$HalfGreen",
            "AREA:rx_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:tx_avg#$FullGreen:TX",
            'GPRINT:tx_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:tx_max:MAX:%5.1lf%s Max,',
            'GPRINT:tx_avg:LAST:%5.1lf%s Last',
            'GPRINT:tx_avg_sum:LAST:(ca. %4.0lf%s Total)\l',
            "LINE1:rx_avg#$FullBlue:RX",

            #'GPRINT:rx_min:MIN:%5.1lf %s Min,',
            'GPRINT:rx_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:rx_max:MAX:%5.1lf%s Max,',
            'GPRINT:rx_avg:LAST:%5.1lf%s Last',
            'GPRINT:rx_avg_sum:LAST:(ca. %4.0lf%s Total)\l'
        ],
        if_collisions => [
            '-v',
            'Collisions/s',
            'DEF:min_raw={file}:value:MIN',
            'DEF:avg_raw={file}:value:AVERAGE',
            'DEF:max_raw={file}:value:MAX',
            'CDEF:min=min_raw,8,*',
            'CDEF:avg=avg_raw,8,*',
            'CDEF:max=max_raw,8,*',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Collisions/s",
            'GPRINT:min:MIN:%5.1lf %s Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last\l'
        ],
        if_dropped => [
            '-v', 'Packets/s',
            'DEF:tx_min={file}:tx:MIN',
            'DEF:tx_avg={file}:tx:AVERAGE',
            'DEF:tx_max={file}:tx:MAX',
            'DEF:rx_min={file}:rx:MIN',
            'DEF:rx_avg={file}:rx:AVERAGE',
            'DEF:rx_max={file}:rx:MAX',
            'CDEF:overlap=tx_avg,rx_avg,GT,rx_avg,tx_avg,IF',
            'CDEF:mytime=tx_avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:tx_avg_sample=tx_avg,UN,0,tx_avg,IF,sample_len,*',
            'CDEF:tx_avg_sum=PREV,UN,0,PREV,IF,tx_avg_sample,+',
            'CDEF:rx_avg_sample=rx_avg,UN,0,rx_avg,IF,sample_len,*',
            'CDEF:rx_avg_sum=PREV,UN,0,PREV,IF,rx_avg_sample,+',
            "AREA:tx_avg#$HalfGreen",
            "AREA:rx_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:tx_avg#$FullGreen:TX",
            'GPRINT:tx_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:tx_max:MAX:%5.1lf%s Max,',
            'GPRINT:tx_avg:LAST:%5.1lf%s Last',
            'GPRINT:tx_avg_sum:LAST:(ca. %4.0lf%s Total)\l',
            "LINE1:rx_avg#$FullBlue:RX",

            #'GPRINT:rx_min:MIN:%5.1lf %s Min,',
            'GPRINT:rx_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:rx_max:MAX:%5.1lf%s Max,',
            'GPRINT:rx_avg:LAST:%5.1lf%s Last',
            'GPRINT:rx_avg_sum:LAST:(ca. %4.0lf%s Total)\l'
        ],
        if_packets => [
            '-v', 'Packets/s',
            'DEF:tx_min={file}:tx:MIN',
            'DEF:tx_avg={file}:tx:AVERAGE',
            'DEF:tx_max={file}:tx:MAX',
            'DEF:rx_min={file}:rx:MIN',
            'DEF:rx_avg={file}:rx:AVERAGE',
            'DEF:rx_max={file}:rx:MAX',
            'CDEF:overlap=tx_avg,rx_avg,GT,rx_avg,tx_avg,IF',
            'CDEF:mytime=tx_avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:tx_avg_sample=tx_avg,UN,0,tx_avg,IF,sample_len,*',
            'CDEF:tx_avg_sum=PREV,UN,0,PREV,IF,tx_avg_sample,+',
            'CDEF:rx_avg_sample=rx_avg,UN,0,rx_avg,IF,sample_len,*',
            'CDEF:rx_avg_sum=PREV,UN,0,PREV,IF,rx_avg_sample,+',
            "AREA:tx_avg#$HalfGreen",
            "AREA:rx_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:tx_avg#$FullGreen:TX",
            'GPRINT:tx_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:tx_max:MAX:%5.1lf%s Max,',
            'GPRINT:tx_avg:LAST:%5.1lf%s Last',
            'GPRINT:tx_avg_sum:LAST:(ca. %4.0lf%s Total)\l',
            "LINE1:rx_avg#$FullBlue:RX",

            #'GPRINT:rx_min:MIN:%5.1lf %s Min,',
            'GPRINT:rx_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:rx_max:MAX:%5.1lf%s Max,',
            'GPRINT:rx_avg:LAST:%5.1lf%s Last',
            'GPRINT:rx_avg_sum:LAST:(ca. %4.0lf%s Total)\l'
        ],
        if_rx_errors => [
            '-v',
            'Errors/s',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:mytime=avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg,UN,0,avg,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:avg#$HalfBlue",
            "LINE1:avg#$FullBlue:Errors/s",
            'GPRINT:avg:AVERAGE:%3.1lf%s Avg,',
            'GPRINT:max:MAX:%3.1lf%s Max,',
            'GPRINT:avg:LAST:%3.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %2.0lf%s Total)\l'
        ],
        illuminance => [
            '-v', 'Lux',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfYellow",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullYellow:Value",
            'GPRINT:min:MIN:%7.1lf Min,',
            'GPRINT:avg:AVERAGE:%7.1lf Avg,',
            'GPRINT:max:MAX:%7.1lf Max,',
            'GPRINT:avg:LAST:%7.1lf Last\l'
        ],
        ipt_bytes => [
            '-v', 'Bits/s',
            'DEF:min_raw={file}:value:MIN',
            'DEF:avg_raw={file}:value:AVERAGE',
            'DEF:max_raw={file}:value:MAX',
            'CDEF:min=min_raw,8,*',
            'CDEF:avg=avg_raw,8,*',
            'CDEF:max=max_raw,8,*',
            'CDEF:mytime=avg_raw,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:avg_sample=avg_raw,UN,0,avg_raw,IF,sample_len,*',
            'CDEF:avg_sum=PREV,UN,0,PREV,IF,avg_sample,+',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Bits/s",

            #'GPRINT:min:MIN:%5.1lf %s Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last',
            'GPRINT:avg_sum:LAST:(ca. %5.1lf%sB Total)\l'
        ],
        ipt_packets => [
            '-v',
            'Packets/s',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Packets/s",
            'GPRINT:min:MIN:%5.1lf %s Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last\l'
        ],
        irq => [
            '-v',
            'Issues/s',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Issues/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last\l'
        ],
        lighttpd => [
           'DEF:binraw={file}:InOctets:AVERAGE',
           'DEF:binmaxraw={file}:InOctets:MAX',
           'DEF:binminraw={file}:InOctets:MIN',
           'DEF:bout={file}:OutOctets:AVERAGE',
           'DEF:boutmax={file}:OutOctets:MAX',
           'DEF:boutmin={file}:OutOctets:MIN',
           'CDEF:bin=binraw,-1,*',
           'CDEF:binmax=binmaxraw,-1,*',
           'CDEF:binmin=binminraw,-1,*',
           'CDEF:binminmax=binmaxraw,binminraw,-',
           'CDEF:boutminmax=boutmax,boutmin,-',
           'AREA:binmin#ffffff:',
           'STACK:binmax#f00000:',
           'LINE1:binmin#a0a0a0:',
           'LINE1:binmax#a0a0a0:',
           'LINE2:bin#efb71d:incoming',
           'GPRINT:bin:MIN:%.2lf',
           'GPRINT:bin:AVERAGE:%.2lf',
           'GPRINT:bin:MAX:%.2lf',
           'AREA:boutmin#ffffff:',
           'STACK:boutminmax#00f000:',
           'LINE1:boutmin#a0a0a0:',
           'LINE1:boutmax#a0a0a0:',
           'LINE2:bout#a0a735:outgoing',
           'GPRINT:bout:MIN:%.2lf',
           'GPRINT:bout:AVERAGE:%.2lf',
           'GPRINT:bout:MAX:%.2lf',
        ],
        load => [
            '-v',
            'System load',
            'DEF:s_avg={file}:shortterm:AVERAGE',
            'DEF:s_min={file}:shortterm:MIN',
            'DEF:s_max={file}:shortterm:MAX',
            'DEF:m_avg={file}:midterm:AVERAGE',
            'DEF:m_min={file}:midterm:MIN',
            'DEF:m_max={file}:midterm:MAX',
            'DEF:l_avg={file}:longterm:AVERAGE',
            'DEF:l_min={file}:longterm:MIN',
            'DEF:l_max={file}:longterm:MAX',
            "AREA:s_max#$HalfGreen",
            "AREA:s_min#$Canvas",
            "LINE1:s_avg#$FullGreen: 1m average",
            'GPRINT:s_min:MIN:%4.2lf Min,',
            'GPRINT:s_avg:AVERAGE:%4.2lf Avg,',
            'GPRINT:s_max:MAX:%4.2lf Max,',
            'GPRINT:s_avg:LAST:%4.2lf Last\l',
            "LINE1:m_avg#$FullBlue: 5m average",
            'GPRINT:m_min:MIN:%4.2lf Min,',
            'GPRINT:m_avg:AVERAGE:%4.2lf Avg,',
            'GPRINT:m_max:MAX:%4.2lf Max,',
            'GPRINT:m_avg:LAST:%4.2lf Last\l',
            "LINE1:l_avg#$FullRed:15m average",
            'GPRINT:l_min:MIN:%4.2lf Min,',
            'GPRINT:l_avg:AVERAGE:%4.2lf Avg,',
            'GPRINT:l_max:MAX:%4.2lf Max,',
            'GPRINT:l_avg:LAST:%4.2lf Last\l'
        ],
        load_avg => [
            '-v',
            'Load',
            'DEF:n_avg={file}:now:AVERAGE',
            'DEF:n_min={file}:now:MIN',
            'DEF:n_max={file}:now:MAX',
            'DEF:a_avg={file}:all:AVERAGE',
            'DEF:a_min={file}:all:MIN',
            'DEF:a_max={file}:all:MAX',
            "AREA:n_max#$HalfGreen",
            "AREA:n_min#$Canvas",
            "LINE1:n_avg#$FullGreen:Now average",
            'GPRINT:n_min:MIN:%4.2lf Min,',
            'GPRINT:n_avg:AVERAGE:%4.2lf Avg,',
            'GPRINT:n_max:MAX:%4.2lf Max,',
            'GPRINT:n_avg:LAST:%4.2lf Last\l',
            "LINE1:a_avg#$FullRed:All average",
            'GPRINT:a_min:MIN:%4.2lf Min,',
            'GPRINT:a_avg:AVERAGE:%4.2lf Avg,',
            'GPRINT:a_max:MAX:%4.2lf Max,',
            'GPRINT:a_avg:LAST:%4.2lf Last\l'
        ],
        load_percent => [
            'DEF:avg={file}:percent:AVERAGE',
            'DEF:min={file}:percent:MIN',
            'DEF:max={file}:percent:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Load",
            'GPRINT:min:MIN:%5.1lf%s%% Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s%% Avg,',
            'GPRINT:max:MAX:%5.1lf%s%% Max,',
            'GPRINT:avg:LAST:%5.1lf%s%% Last\l'
        ],
        mails => [
            'DEF:rawgood={file}:good:AVERAGE',
            'DEF:rawspam={file}:spam:AVERAGE',
            'CDEF:good=rawgood,UN,0,rawgood,IF',
            'CDEF:spam=rawspam,UN,0,rawspam,IF',
            'CDEF:negspam=spam,-1,*',
            "AREA:good#$HalfGreen",
            "LINE1:good#$FullGreen:Good mails",
            'GPRINT:good:AVERAGE:%4.1lf Avg,',
            'GPRINT:good:MAX:%4.1lf Max,',
            'GPRINT:good:LAST:%4.1lf Last\n',
            "AREA:negspam#$HalfRed",
            "LINE1:negspam#$FullRed:Spam mails",
            'GPRINT:spam:AVERAGE:%4.1lf Avg,',
            'GPRINT:spam:MAX:%4.1lf Max,',
            'GPRINT:spam:LAST:%4.1lf Last',
            'HRULE:0#000000'
        ],
        memory => [
            '-b',
            '1024',
            '-v',
            'Bytes',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Memory",
            'GPRINT:min:MIN:%5.1lf%sbyte Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%sbyte Avg,',
            'GPRINT:max:MAX:%5.1lf%sbyte Max,',
            'GPRINT:avg:LAST:%5.1lf%sbyte Last\l'
        ],
        old_memory => [
            'DEF:used_avg={file}:used:AVERAGE',
            'DEF:free_avg={file}:free:AVERAGE',
            'DEF:buffers_avg={file}:buffers:AVERAGE',
            'DEF:cached_avg={file}:cached:AVERAGE',
            'DEF:used_min={file}:used:MIN',
            'DEF:free_min={file}:free:MIN',
            'DEF:buffers_min={file}:buffers:MIN',
            'DEF:cached_min={file}:cached:MIN',
            'DEF:used_max={file}:used:MAX',
            'DEF:free_max={file}:free:MAX',
            'DEF:buffers_max={file}:buffers:MAX',
            'DEF:cached_max={file}:cached:MAX',
            'CDEF:cached_avg_nn=cached_avg,UN,0,cached_avg,IF',
            'CDEF:buffers_avg_nn=buffers_avg,UN,0,buffers_avg,IF',
            'CDEF:free_cached_buffers_used=free_avg,cached_avg_nn,+,buffers_avg_nn,+,used_avg,+',
            'CDEF:cached_buffers_used=cached_avg,buffers_avg_nn,+,used_avg,+',
            'CDEF:buffers_used=buffers_avg,used_avg,+',
            "AREA:free_cached_buffers_used#$HalfGreen",
            "AREA:cached_buffers_used#$HalfBlue",
            "AREA:buffers_used#$HalfYellow",
            "AREA:used_avg#$HalfRed",
            "LINE1:free_cached_buffers_used#$FullGreen:Free        ",
            'GPRINT:free_min:MIN:%5.1lf%s Min,',
            'GPRINT:free_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:free_max:MAX:%5.1lf%s Max,',
            'GPRINT:free_avg:LAST:%5.1lf%s Last\n',
            "LINE1:cached_buffers_used#$FullBlue:Page cache  ",
            'GPRINT:cached_min:MIN:%5.1lf%s Min,',
            'GPRINT:cached_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:cached_max:MAX:%5.1lf%s Max,',
            'GPRINT:cached_avg:LAST:%5.1lf%s Last\n',
            "LINE1:buffers_used#$FullYellow:Buffer cache",
            'GPRINT:buffers_min:MIN:%5.1lf%s Min,',
            'GPRINT:buffers_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:buffers_max:MAX:%5.1lf%s Max,',
            'GPRINT:buffers_avg:LAST:%5.1lf%s Last\n',
            "LINE1:used_avg#$FullRed:Used        ",
            'GPRINT:used_min:MIN:%5.1lf%s Min,',
            'GPRINT:used_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:used_max:MAX:%5.1lf%s Max,',
            'GPRINT:used_avg:LAST:%5.1lf%s Last'
        ],
        mysql_bpool_bytes => [
            '-v', 'Bytes/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Bytes/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_bpool_counters => [
            '-v', 'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_bpool_pages => [
            '-v', 'Pages/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Pages/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_commands => [
            '-v',
            'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_handler => [
            '-v',
            'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_innodb_data => [
            '-v',
            'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_innodb_dblwr => [
            '-v',
            'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_innodb_log => [
            '-v',
            'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_innodb_locks => [
            '-v',
            'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_innodb_pages => [
            '-v',
            'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_innodb_row_lock => [
            '-v',
            'Locks/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Rows/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_innodb_rows => [
            '-v',
            'Rows/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Rows/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_octets => [
            '-v',
            'Bytes/s',
            'DEF:out_min={file}:tx:MIN',
            'DEF:out_avg={file}:tx:AVERAGE',
            'DEF:out_max={file}:tx:MAX',
            'DEF:inc_min={file}:rx:MIN',
            'DEF:inc_avg={file}:rx:AVERAGE',
            'DEF:inc_max={file}:rx:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            'CDEF:mytime=out_avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:out_avg_sample=out_avg,UN,0,out_avg,IF,sample_len,*',
            'CDEF:out_avg_sum=PREV,UN,0,PREV,IF,out_avg_sample,+',
            'CDEF:inc_avg_sample=inc_avg,UN,0,inc_avg,IF,sample_len,*',
            'CDEF:inc_avg_sum=PREV,UN,0,PREV,IF,inc_avg_sample,+',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Transmitted",
            'GPRINT:out_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:out_max:MAX:%5.1lf%s Max,',
            'GPRINT:out_avg:LAST:%5.1lf%s Last',
            'GPRINT:out_avg_sum:LAST:(ca. %5.1lf%sB Total)\l',
            "LINE1:inc_avg#$FullBlue:Received   ",
            'GPRINT:inc_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:inc_max:MAX:%5.1lf%s Max,',
            'GPRINT:inc_avg:LAST:%5.1lf%s Last',
            'GPRINT:inc_avg_sum:LAST:(ca. %5.1lf%sB Total)\l'
        ],
        mysql_qcache => [
            '-v',
            'Queries/s',
            "DEF:hits_min={file}:hits:MIN",
            "DEF:hits_avg={file}:hits:AVERAGE",
            "DEF:hits_max={file}:hits:MAX",
            "DEF:inserts_min={file}:inserts:MIN",
            "DEF:inserts_avg={file}:inserts:AVERAGE",
            "DEF:inserts_max={file}:inserts:MAX",
            "DEF:not_cached_min={file}:not_cached:MIN",
            "DEF:not_cached_avg={file}:not_cached:AVERAGE",
            "DEF:not_cached_max={file}:not_cached:MAX",
            "DEF:lowmem_prunes_min={file}:lowmem_prunes:MIN",
            "DEF:lowmem_prunes_avg={file}:lowmem_prunes:AVERAGE",
            "DEF:lowmem_prunes_max={file}:lowmem_prunes:MAX",
            "DEF:queries_min={file}:queries_in_cache:MIN",
            "DEF:queries_avg={file}:queries_in_cache:AVERAGE",
            "DEF:queries_max={file}:queries_in_cache:MAX",
            "CDEF:unknown=queries_avg,UNKN,+",
            "CDEF:not_cached_agg=hits_avg,inserts_avg,+,not_cached_avg,+",
            "CDEF:inserts_agg=hits_avg,inserts_avg,+",
            "CDEF:hits_agg=hits_avg",
            "AREA:not_cached_agg#$HalfYellow",
            "AREA:inserts_agg#$HalfBlue",
            "AREA:hits_agg#$HalfGreen",
            "LINE1:not_cached_agg#$FullYellow:Not Cached      ",
            'GPRINT:not_cached_min:MIN:%5.2lf Min,',
            'GPRINT:not_cached_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:not_cached_max:MAX:%5.2lf Max,',
            'GPRINT:not_cached_avg:LAST:%5.2lf Last\l',
            "LINE1:inserts_agg#$FullBlue:Inserts         ",
            'GPRINT:inserts_min:MIN:%5.2lf Min,',
            'GPRINT:inserts_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:inserts_max:MAX:%5.2lf Max,',
            'GPRINT:inserts_avg:LAST:%5.2lf Last\l',
            "LINE1:hits_agg#$FullGreen:Hits            ",
            'GPRINT:hits_min:MIN:%5.2lf Min,',
            'GPRINT:hits_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:hits_max:MAX:%5.2lf Max,',
            'GPRINT:hits_avg:LAST:%5.2lf Last\l',
            "LINE1:lowmem_prunes_avg#$FullRed:Lowmem Prunes   ",
            'GPRINT:lowmem_prunes_min:MIN:%5.2lf Min,',
            'GPRINT:lowmem_prunes_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:lowmem_prunes_max:MAX:%5.2lf Max,',
            'GPRINT:lowmem_prunes_avg:LAST:%5.2lf Last\l',
            "LINE1:unknown#$Canvas:Queries in cache",
            'GPRINT:queries_min:MIN:%5.0lf Min,',
            'GPRINT:queries_avg:AVERAGE:%5.0lf Avg,',
            'GPRINT:queries_max:MAX:%5.0lf Max,',
            'GPRINT:queries_avg:LAST:%5.0lf Last\l'
        ],
        mysql_select => [
            '-v', 'Selects/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Selects/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_slow_queries => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Queries/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        mysql_sort => [
            '-v',
            'Issues/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Issues/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        mysql_threads => [
            '-v',
            'Threads',
            "DEF:running_min={file}:running:MIN",
            "DEF:running_avg={file}:running:AVERAGE",
            "DEF:running_max={file}:running:MAX",
            "DEF:connected_min={file}:connected:MIN",
            "DEF:connected_avg={file}:connected:AVERAGE",
            "DEF:connected_max={file}:connected:MAX",
            "DEF:cached_min={file}:cached:MIN",
            "DEF:cached_avg={file}:cached:AVERAGE",
            "DEF:cached_max={file}:cached:MAX",
            "DEF:created_min={file}:created:MIN",
            "DEF:created_avg={file}:created:AVERAGE",
            "DEF:created_max={file}:created:MAX",
            "CDEF:unknown=created_avg,UNKN,+",
            "CDEF:cached_agg=connected_avg,cached_avg,+",
            "AREA:cached_agg#$HalfGreen",
            "AREA:connected_avg#$HalfBlue",
            "AREA:running_avg#$HalfRed",
            "LINE1:cached_agg#$FullGreen:Cached   ",
            'GPRINT:cached_min:MIN:%5.1lf Min,',
            'GPRINT:cached_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:cached_max:MAX:%5.1lf Max,',
            'GPRINT:cached_avg:LAST:%5.1lf Last\l',
            "LINE1:connected_avg#$FullBlue:Connected",
            'GPRINT:connected_min:MIN:%5.1lf Min,',
            'GPRINT:connected_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:connected_max:MAX:%5.1lf Max,',
            'GPRINT:connected_avg:LAST:%5.1lf Last\l',
            "LINE1:running_avg#$FullRed:Running  ",
            'GPRINT:running_min:MIN:%5.1lf Min,',
            'GPRINT:running_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:running_max:MAX:%5.1lf Max,',
            'GPRINT:running_avg:LAST:%5.1lf Last\l',
            "LINE1:unknown#$Canvas:Created  ",
            'GPRINT:created_min:MIN:%5.0lf Min,',
            'GPRINT:created_avg:AVERAGE:%5.0lf Avg,',
            'GPRINT:created_max:MAX:%5.0lf Max,',
            'GPRINT:created_avg:LAST:%5.0lf Last\l'
        ],
        nfs_procedure => [
            '-v',                           'Issues/s',
            'DEF:avg={file}:value:AVERAGE', 'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',     "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",             "LINE1:avg#$FullBlue:Issues/s",
            'GPRINT:min:MIN:%6.2lf Min,',   'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',   'GPRINT:avg:LAST:%6.2lf Last\l'
        ],
        nfs3_procedures => [
            "DEF:null_avg={file}:null:AVERAGE",
            "DEF:getattr_avg={file}:getattr:AVERAGE",
            "DEF:setattr_avg={file}:setattr:AVERAGE",
            "DEF:lookup_avg={file}:lookup:AVERAGE",
            "DEF:access_avg={file}:access:AVERAGE",
            "DEF:readlink_avg={file}:readlink:AVERAGE",
            "DEF:read_avg={file}:read:AVERAGE",
            "DEF:write_avg={file}:write:AVERAGE",
            "DEF:create_avg={file}:create:AVERAGE",
            "DEF:mkdir_avg={file}:mkdir:AVERAGE",
            "DEF:symlink_avg={file}:symlink:AVERAGE",
            "DEF:mknod_avg={file}:mknod:AVERAGE",
            "DEF:remove_avg={file}:remove:AVERAGE",
            "DEF:rmdir_avg={file}:rmdir:AVERAGE",
            "DEF:rename_avg={file}:rename:AVERAGE",
            "DEF:link_avg={file}:link:AVERAGE",
            "DEF:readdir_avg={file}:readdir:AVERAGE",
            "DEF:readdirplus_avg={file}:readdirplus:AVERAGE",
            "DEF:fsstat_avg={file}:fsstat:AVERAGE",
            "DEF:fsinfo_avg={file}:fsinfo:AVERAGE",
            "DEF:pathconf_avg={file}:pathconf:AVERAGE",
            "DEF:commit_avg={file}:commit:AVERAGE",
            "DEF:null_max={file}:null:MAX",
            "DEF:getattr_max={file}:getattr:MAX",
            "DEF:setattr_max={file}:setattr:MAX",
            "DEF:lookup_max={file}:lookup:MAX",
            "DEF:access_max={file}:access:MAX",
            "DEF:readlink_max={file}:readlink:MAX",
            "DEF:read_max={file}:read:MAX",
            "DEF:write_max={file}:write:MAX",
            "DEF:create_max={file}:create:MAX",
            "DEF:mkdir_max={file}:mkdir:MAX",
            "DEF:symlink_max={file}:symlink:MAX",
            "DEF:mknod_max={file}:mknod:MAX",
            "DEF:remove_max={file}:remove:MAX",
            "DEF:rmdir_max={file}:rmdir:MAX",
            "DEF:rename_max={file}:rename:MAX",
            "DEF:link_max={file}:link:MAX",
            "DEF:readdir_max={file}:readdir:MAX",
            "DEF:readdirplus_max={file}:readdirplus:MAX",
            "DEF:fsstat_max={file}:fsstat:MAX",
            "DEF:fsinfo_max={file}:fsinfo:MAX",
            "DEF:pathconf_max={file}:pathconf:MAX",
            "DEF:commit_max={file}:commit:MAX",
            "CDEF:other_avg=null_avg,readlink_avg,create_avg,mkdir_avg,symlink_avg,mknod_avg,remove_avg,rmdir_avg,rename_avg,link_avg,readdir_avg,readdirplus_avg,fsstat_avg,fsinfo_avg,pathconf_avg,+,+,+,+,+,+,+,+,+,+,+,+,+,+",
            "CDEF:other_max=null_max,readlink_max,create_max,mkdir_max,symlink_max,mknod_max,remove_max,rmdir_max,rename_max,link_max,readdir_max,readdirplus_max,fsstat_max,fsinfo_max,pathconf_max,+,+,+,+,+,+,+,+,+,+,+,+,+,+",
            "CDEF:stack_read=read_avg",
            "CDEF:stack_getattr=stack_read,getattr_avg,+",
            "CDEF:stack_access=stack_getattr,access_avg,+",
            "CDEF:stack_lookup=stack_access,lookup_avg,+",
            "CDEF:stack_write=stack_lookup,write_avg,+",
            "CDEF:stack_commit=stack_write,commit_avg,+",
            "CDEF:stack_setattr=stack_commit,setattr_avg,+",
            "CDEF:stack_other=stack_setattr,other_avg,+",
            "AREA:stack_other#$HalfRed",
            "AREA:stack_setattr#$HalfGreen",
            "AREA:stack_commit#$HalfYellow",
            "AREA:stack_write#$HalfGreen",
            "AREA:stack_lookup#$HalfBlue",
            "AREA:stack_access#$HalfMagenta",
            "AREA:stack_getattr#$HalfCyan",
            "AREA:stack_read#$HalfBlue",
            "LINE1:stack_other#$FullRed:Other  ",
            'GPRINT:other_max:MAX:%5.1lf Max,',
            'GPRINT:other_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:other_avg:LAST:%5.1lf Last\l',
            "LINE1:stack_setattr#$FullGreen:setattr",
            'GPRINT:setattr_max:MAX:%5.1lf Max,',
            'GPRINT:setattr_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:setattr_avg:LAST:%5.1lf Last\l',
            "LINE1:stack_commit#$FullYellow:commit ",
            'GPRINT:commit_max:MAX:%5.1lf Max,',
            'GPRINT:commit_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:commit_avg:LAST:%5.1lf Last\l',
            "LINE1:stack_write#$FullGreen:write  ",
            'GPRINT:write_max:MAX:%5.1lf Max,',
            'GPRINT:write_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:write_avg:LAST:%5.1lf Last\l',
            "LINE1:stack_lookup#$FullBlue:lookup ",
            'GPRINT:lookup_max:MAX:%5.1lf Max,',
            'GPRINT:lookup_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:lookup_avg:LAST:%5.1lf Last\l',
            "LINE1:stack_access#$FullMagenta:access ",
            'GPRINT:access_max:MAX:%5.1lf Max,',
            'GPRINT:access_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:access_avg:LAST:%5.1lf Last\l',
            "LINE1:stack_getattr#$FullCyan:getattr",
            'GPRINT:getattr_max:MAX:%5.1lf Max,',
            'GPRINT:getattr_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:getattr_avg:LAST:%5.1lf Last\l',
            "LINE1:stack_read#$FullBlue:read   ",
            'GPRINT:read_max:MAX:%5.1lf Max,',
            'GPRINT:read_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:read_avg:LAST:%5.1lf Last\l'
        ],
        nginx_requests => [
             'DEF:min={file}:value:MIN',
             'DEF:avg={file}:value:AVERAGE',
             'DEF:max={file}:value:MAX',
             "AREA:max#$HalfBlue",
             "AREA:min#$Canvas",
             "LINE1:avg#$FullBlue:Requests/s",
             'GPRINT:min:MIN:%6.2lf Min,',
             'GPRINT:avg:AVERAGE:%6.2lf Avg,',
             'GPRINT:max:MAX:%6.2lf Max,',
             'GPRINT:avg:LAST:%6.2lf Last'
         ],
         nginx_connections => [
             'DEF:min={file}:value:MIN',
             'DEF:avg={file}:value:AVERAGE',
             'DEF:max={file}:value:MAX',
             "AREA:max#$HalfBlue",
             "AREA:min#$Canvas",
             "LINE1:avg#$FullBlue:Requests/s",
             'GPRINT:min:MIN:%6.2lf Min,',
             'GPRINT:avg:AVERAGE:%6.2lf Avg,',
             'GPRINT:max:MAX:%6.2lf Max,',
             'GPRINT:avg:LAST:%6.2lf Last'
         ],
        opcode => [
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Queries/s",
            'GPRINT:min:MIN:%9.3lf Min,',
            'GPRINT:avg:AVERAGE:%9.3lf Average,',
            'GPRINT:max:MAX:%9.3lf Max,',
            'GPRINT:avg:LAST:%9.3lf Last\l'
        ],
        operations => [
            '-v',
            'Operations/s',
            "DEF:val_avg={file}:value:AVERAGE",
            "DEF:val_min={file}:value:MIN",
            "DEF:val_max={file}:value:MAX",
            "AREA:val_max#$HalfBlue",
            "AREA:val_min#$Canvas",
            "LINE1:val_avg#$FullBlue:Operations/s",
            'GPRINT:val_min:MIN:%5.2lf Min,',
            'GPRINT:val_avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:val_max:MAX:%5.2lf Max,',
            'GPRINT:val_avg:LAST:%5.2lf Last'
        ],
        partition => [
            "DEF:rbyte_avg={file}:rbytes:AVERAGE",
            "DEF:rbyte_min={file}:rbytes:MIN",
            "DEF:rbyte_max={file}:rbytes:MAX",
            "DEF:wbyte_avg={file}:wbytes:AVERAGE",
            "DEF:wbyte_min={file}:wbytes:MIN",
            "DEF:wbyte_max={file}:wbytes:MAX",
            'CDEF:overlap=wbyte_avg,rbyte_avg,GT,rbyte_avg,wbyte_avg,IF',
            "AREA:wbyte_avg#$HalfGreen",
            "AREA:rbyte_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:wbyte_avg#$FullGreen:Write",
            'GPRINT:wbyte_min:MIN:%5.1lf%s Min,',
            'GPRINT:wbyte_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:wbyte_max:MAX:%5.1lf%s Max,',
            'GPRINT:wbyte_avg:LAST:%5.1lf%s Last\l',
            "LINE1:rbyte_avg#$FullBlue:Read ",
            'GPRINT:rbyte_min:MIN:%5.1lf%s Min,',
            'GPRINT:rbyte_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:rbyte_max:MAX:%5.1lf%s Max,',
            'GPRINT:rbyte_avg:LAST:%5.1lf%s Last\l'
        ],
        pending_operations => [
            '-v', 'Pending Requests',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfRed",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullRed:Requests",
            'GPRINT:min:MIN:%5.2lf Min,',
            'GPRINT:avg:AVERAGE:%5.2lf Avg,',
            'GPRINT:max:MAX:%5.2lf Max,',
            'GPRINT:avg:LAST:%5.2lf Last'
        ],
# jaf-18aug11 Changed to work with memcache... which was calling for it. But
# if it worked with something else its now broken.
        percent => [
            '-v',
            'Percent',
#            'DEF:avg={file}:percent:AVERAGE',
#            'DEF:min={file}:percent:MIN',
#            'DEF:max={file}:percent:MAX',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Percent",
            'GPRINT:min:MIN:%5.1lf%% Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%% Avg,',
            'GPRINT:max:MAX:%5.1lf%% Max,',
            'GPRINT:avg:LAST:%5.1lf%% Last\l'
        ],
# jaf-18aug11 END
        ping => [
            'DEF:ping_avg={file}:value:AVERAGE',
            'DEF:ping_min={file}:value:MIN',
            'DEF:ping_max={file}:value:MAX',
            "AREA:ping_max#$HalfBlue",
            "AREA:ping_min#$Canvas",
            "LINE1:ping_avg#$FullBlue:Ping",
            'GPRINT:ping_min:MIN:%4.1lf ms Min,',
            'GPRINT:ping_avg:AVERAGE:%4.1lf ms Avg,',
            'GPRINT:ping_max:MAX:%4.1lf ms Max,',
            'GPRINT:ping_avg:LAST:%4.1lf ms Last'
        ],
        ping_droprate => [
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfRed",
            "AREA:min#$Canvas",
            "LINE2:avg#$FullRed:DropRate",
            'GPRINT:min:MIN:%3.2lf Min,',
            'GPRINT:avg:AVERAGE:%3.2lf Avg,',
            'GPRINT:max:MAX:%3.2lf Max,',
            'GPRINT:avg:LAST:%3.2lf Last\l'
        ],
        ping_stddev => [
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfCyan",
            "AREA:min#$Canvas",
            "LINE2:avg#$FullCyan:StdDev",
            'GPRINT:min:MIN:%5.1lf Min,',
            'GPRINT:avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:max:MAX:%5.1lf Max,',
            'GPRINT:avg:LAST:%5.1lf Last\l'
        ],
        pg_blks => [
            'DEF:pg_blks_avg={file}:value:AVERAGE',
            'DEF:pg_blks_min={file}:value:MIN',
            'DEF:pg_blks_max={file}:value:MAX',
            "AREA:pg_blks_max#$HalfBlue",
            "AREA:pg_blks_min#$Canvas",
            "LINE1:pg_blks_avg#$FullBlue:Blocks",
            'GPRINT:pg_blks_min:MIN:%4.1lf%s Min,',
            'GPRINT:pg_blks_avg:AVERAGE:%4.1lf%s Avg,',
            'GPRINT:pg_blks_max:MAX:%4.1lf%s Max,',
            'GPRINT:pg_blks_avg:LAST:%4.1lf%s Last'],
        pg_db_size => [
            'DEF:pg_db_size_avg={file}:value:AVERAGE',
            'DEF:pg_db_size_min={file}:value:MIN',
            'DEF:pg_db_size_max={file}:value:MAX',
            "AREA:pg_db_size_max#$HalfBlue",
            "AREA:pg_db_size_min#$Canvas",
            "LINE1:pg_db_size_avg#$FullBlue:Bytes",
            'GPRINT:pg_db_size_min:MIN:%4.1lf%s Min,',
            'GPRINT:pg_db_size_avg:AVERAGE:%4.1lf%s Avg,',
            'GPRINT:pg_db_size_max:MAX:%4.1lf%s Max,',
            'GPRINT:pg_db_size_avg:LAST:%4.1lf%s Last'],
        pg_n_tup_c => [
            'DEF:pg_n_tup_avg={file}:value:AVERAGE',
            'DEF:pg_n_tup_min={file}:value:MIN',
            'DEF:pg_n_tup_max={file}:value:MAX',
            "AREA:pg_n_tup_max#$HalfBlue",
            "AREA:pg_n_tup_min#$Canvas",
            "LINE1:pg_n_tup_avg#$FullBlue:Tuples",
            'GPRINT:pg_n_tup_min:MIN:%4.1lf%s Min,',
            'GPRINT:pg_n_tup_avg:AVERAGE:%4.1lf%s Avg,',
            'GPRINT:pg_n_tup_max:MAX:%4.1lf%s Max,',
            'GPRINT:pg_n_tup_avg:LAST:%4.1lf%s Last'],
        pg_n_tup_g => [
            'DEF:pg_n_tup_avg={file}:value:AVERAGE',
            'DEF:pg_n_tup_min={file}:value:MIN',
            'DEF:pg_n_tup_max={file}:value:MAX',
            "AREA:pg_n_tup_max#$HalfBlue",
            "AREA:pg_n_tup_min#$Canvas",
            "LINE1:pg_n_tup_avg#$FullBlue:Tuples",
            'GPRINT:pg_n_tup_min:MIN:%4.1lf%s Min,',
            'GPRINT:pg_n_tup_avg:AVERAGE:%4.1lf%s Avg,',
            'GPRINT:pg_n_tup_max:MAX:%4.1lf%s Max,',
            'GPRINT:pg_n_tup_avg:LAST:%4.1lf%s Last'],
        pg_numbackends => [
            'DEF:pg_numbackends_avg={file}:value:AVERAGE',
            'DEF:pg_numbackends_min={file}:value:MIN',
            'DEF:pg_numbackends_max={file}:value:MAX',
            "AREA:pg_numbackends_max#$HalfBlue",
            "AREA:pg_numbackends_min#$Canvas",
            "LINE1:pg_numbackends_avg#$FullBlue:Backends",
            'GPRINT:pg_numbackends_min:MIN:%4.1lf%s Min,',
            'GPRINT:pg_numbackends_avg:AVERAGE:%4.1lf%s Avg,',
            'GPRINT:pg_numbackends_max:MAX:%4.1lf%s Max,',
            'GPRINT:pg_numbackends_avg:LAST:%4.1lf%s Last'],
        pg_scan => [
            'DEF:pg_scan_avg={file}:value:AVERAGE',
            'DEF:pg_scan_min={file}:value:MIN',
            'DEF:pg_scan_max={file}:value:MAX',
            "AREA:pg_scan_max#$HalfBlue",
            "AREA:pg_scan_min#$Canvas",
            "LINE1:pg_scan_avg#$FullBlue:Scans",
            'GPRINT:pg_scan_min:MIN:%4.1lf%s Min,',
            'GPRINT:pg_scan_avg:AVERAGE:%4.1lf%s Avg,',
            'GPRINT:pg_scan_max:MAX:%4.1lf%s Max,',
            'GPRINT:pg_scan_avg:LAST:%4.1lf%s Last'],
        pg_xact => [
            'DEF:pg_xact_avg={file}:value:AVERAGE',
            'DEF:pg_xact_min={file}:value:MIN',
            'DEF:pg_xact_max={file}:value:MAX',
            "AREA:pg_xact_max#$HalfBlue",
            "AREA:pg_xact_min#$Canvas",
            "LINE1:pg_xact_avg#$FullBlue:Transactions",
            'GPRINT:pg_xact_min:MIN:%4.1lf%s Min,',
            'GPRINT:pg_xact_avg:AVERAGE:%4.1lf%s Avg,',
            'GPRINT:pg_xact_max:MAX:%4.1lf%s Max,',
            'GPRINT:pg_xact_avg:LAST:%4.1lf%s Last'],
        power => [
            '-v',
            'Watt',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            'CDEF:avg_neg=avg,0,LE,avg,UNKN,IF',
            'CDEF:avg_pos=avg,0,GE,avg,UNKN,IF',
            'CDEF:avg_neg_ln=PREV(avg_neg),avg,avg_neg,IF',
            'CDEF:avg_pos_ln=PREV(avg_pos),avg,avg_pos,IF',
            'CDEF:max_neg=max,0,LT,max,UNKN,IF',
            'CDEF:max_pos=max,0,GT,max,UNKN,IF',
            'CDEF:min_neg=min,0,LT,min,UNKN,IF',
            'CDEF:min_pos=min,0,GT,min,UNKN,IF',
            'CDEF:stime=avg,TIME,UNKN,IF',
            'CDEF:dtime=stime,PREV(stime),-',
            'CDEF:denergy=dtime,avg,dtime,*,0,IF',
            'CDEF:senergy=PREV,PREV,0,IF,denergy,+',
            'CDEF:henergy=senergy,3600,/',
            "AREA:min_neg#$HalfRed",
            "AREA:max_pos#$HalfGreen",
            "LINE:avg_neg_ln#$FullRed:-",
            "LINE:avg_pos_ln#$FullGreen:+ Power",
            'GPRINT:min:MIN:%5.1lf%sW Min,',
            'GPRINT:max:MAX:%5.1lf%sW Max,',
            'GPRINT:avg:LAST:%5.1lf%sW Last',
            'GPRINT:henergy:LAST:(ca. %5.1lf%sWh Total)\l'
        ],
        pressure => [
            '-v', 'mmHg',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfCyan",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullCyan:Value",
            'GPRINT:min:MIN:%5.1lf Min,',
            'GPRINT:avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:max:MAX:%5.1lf Max,',
            'GPRINT:avg:LAST:%5.1lf Last\l'
        ],
        processes => [
            "DEF:running_avg={file}:running:AVERAGE",
            "DEF:running_min={file}:running:MIN",
            "DEF:running_max={file}:running:MAX",
            "DEF:sleeping_avg={file}:sleeping:AVERAGE",
            "DEF:sleeping_min={file}:sleeping:MIN",
            "DEF:sleeping_max={file}:sleeping:MAX",
            "DEF:zombies_avg={file}:zombies:AVERAGE",
            "DEF:zombies_min={file}:zombies:MIN",
            "DEF:zombies_max={file}:zombies:MAX",
            "DEF:stopped_avg={file}:stopped:AVERAGE",
            "DEF:stopped_min={file}:stopped:MIN",
            "DEF:stopped_max={file}:stopped:MAX",
            "DEF:paging_avg={file}:paging:AVERAGE",
            "DEF:paging_min={file}:paging:MIN",
            "DEF:paging_max={file}:paging:MAX",
            "DEF:blocked_avg={file}:blocked:AVERAGE",
            "DEF:blocked_min={file}:blocked:MIN",
            "DEF:blocked_max={file}:blocked:MAX",
            'CDEF:paging_acc=sleeping_avg,running_avg,stopped_avg,zombies_avg,blocked_avg,paging_avg,+,+,+,+,+',
            'CDEF:blocked_acc=sleeping_avg,running_avg,stopped_avg,zombies_avg,blocked_avg,+,+,+,+',
            'CDEF:zombies_acc=sleeping_avg,running_avg,stopped_avg,zombies_avg,+,+,+',
            'CDEF:stopped_acc=sleeping_avg,running_avg,stopped_avg,+,+',
            'CDEF:running_acc=sleeping_avg,running_avg,+',
            'CDEF:sleeping_acc=sleeping_avg',
            "AREA:paging_acc#$HalfYellow",
            "AREA:blocked_acc#$HalfCyan",
            "AREA:zombies_acc#$HalfRed",
            "AREA:stopped_acc#$HalfMagenta",
            "AREA:running_acc#$HalfGreen",
            "AREA:sleeping_acc#$HalfBlue",
            "LINE1:paging_acc#$FullYellow:Paging  ",
            'GPRINT:paging_min:MIN:%5.1lf Min,',
            'GPRINT:paging_avg:AVERAGE:%5.1lf Average,',
            'GPRINT:paging_max:MAX:%5.1lf Max,',
            'GPRINT:paging_avg:LAST:%5.1lf Last\l',
            "LINE1:blocked_acc#$FullCyan:Blocked ",
            'GPRINT:blocked_min:MIN:%5.1lf Min,',
            'GPRINT:blocked_avg:AVERAGE:%5.1lf Average,',
            'GPRINT:blocked_max:MAX:%5.1lf Max,',
            'GPRINT:blocked_avg:LAST:%5.1lf Last\l',
            "LINE1:zombies_acc#$FullRed:Zombies ",
            'GPRINT:zombies_min:MIN:%5.1lf Min,',
            'GPRINT:zombies_avg:AVERAGE:%5.1lf Average,',
            'GPRINT:zombies_max:MAX:%5.1lf Max,',
            'GPRINT:zombies_avg:LAST:%5.1lf Last\l',
            "LINE1:stopped_acc#$FullMagenta:Stopped ",
            'GPRINT:stopped_min:MIN:%5.1lf Min,',
            'GPRINT:stopped_avg:AVERAGE:%5.1lf Average,',
            'GPRINT:stopped_max:MAX:%5.1lf Max,',
            'GPRINT:stopped_avg:LAST:%5.1lf Last\l',
            "LINE1:running_acc#$FullGreen:Running ",
            'GPRINT:running_min:MIN:%5.1lf Min,',
            'GPRINT:running_avg:AVERAGE:%5.1lf Average,',
            'GPRINT:running_max:MAX:%5.1lf Max,',
            'GPRINT:running_avg:LAST:%5.1lf Last\l',
            "LINE1:sleeping_acc#$FullBlue:Sleeping",
            'GPRINT:sleeping_min:MIN:%5.1lf Min,',
            'GPRINT:sleeping_avg:AVERAGE:%5.1lf Average,',
            'GPRINT:sleeping_max:MAX:%5.1lf Max,',
            'GPRINT:sleeping_avg:LAST:%5.1lf Last\l'
        ],
        ps_count => [
            '-v',
            'Processes',
            'DEF:procs_avg={file}:processes:AVERAGE',
            'DEF:procs_min={file}:processes:MIN',
            'DEF:procs_max={file}:processes:MAX',
            'DEF:thrds_avg={file}:threads:AVERAGE',
            'DEF:thrds_min={file}:threads:MIN',
            'DEF:thrds_max={file}:threads:MAX',
            "AREA:thrds_avg#$HalfBlue",
            "AREA:procs_avg#$HalfRed",
            "LINE1:thrds_avg#$FullBlue:Threads  ",
            'GPRINT:thrds_min:MIN:%5.1lf Min,',
            'GPRINT:thrds_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:thrds_max:MAX:%5.1lf Max,',
            'GPRINT:thrds_avg:LAST:%5.1lf Last\l',
            "LINE1:procs_avg#$FullRed:Processes",
            'GPRINT:procs_min:MIN:%5.1lf Min,',
            'GPRINT:procs_avg:AVERAGE:%5.1lf Avg,',
            'GPRINT:procs_max:MAX:%5.1lf Max,',
            'GPRINT:procs_avg:LAST:%5.1lf Last\l'
        ],
        ps_cputime => [
            '-v',
            'Jiffies',
            'DEF:user_avg_raw={file}:user:AVERAGE',
            'DEF:user_min_raw={file}:user:MIN',
            'DEF:user_max_raw={file}:user:MAX',
            'DEF:syst_avg_raw={file}:syst:AVERAGE',
            'DEF:syst_min_raw={file}:syst:MIN',
            'DEF:syst_max_raw={file}:syst:MAX',
            'CDEF:user_avg=user_avg_raw,1000000,/',
            'CDEF:user_min=user_min_raw,1000000,/',
            'CDEF:user_max=user_max_raw,1000000,/',
            'CDEF:syst_avg=syst_avg_raw,1000000,/',
            'CDEF:syst_min=syst_min_raw,1000000,/',
            'CDEF:syst_max=syst_max_raw,1000000,/',
            'CDEF:user_syst=syst_avg,UN,0,syst_avg,IF,user_avg,+',
            "AREA:user_syst#$HalfBlue",
            "AREA:syst_avg#$HalfRed",
            "LINE1:user_syst#$FullBlue:User  ",
            'GPRINT:user_min:MIN:%5.1lf%s Min,',
            'GPRINT:user_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:user_max:MAX:%5.1lf%s Max,',
            'GPRINT:user_avg:LAST:%5.1lf%s Last\l',
            "LINE1:syst_avg#$FullRed:System",
            'GPRINT:syst_min:MIN:%5.1lf%s Min,',
            'GPRINT:syst_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:syst_max:MAX:%5.1lf%s Max,',
            'GPRINT:syst_avg:LAST:%5.1lf%s Last\l'
        ],
        ps_pagefaults => [
            '-v',
            'Pagefaults/s',
            'DEF:minor_avg={file}:minflt:AVERAGE',
            'DEF:minor_min={file}:minflt:MIN',
            'DEF:minor_max={file}:minflt:MAX',
            'DEF:major_avg={file}:majflt:AVERAGE',
            'DEF:major_min={file}:majflt:MIN',
            'DEF:major_max={file}:majflt:MAX',
            'CDEF:minor_major=major_avg,UN,0,major_avg,IF,minor_avg,+',
            "AREA:minor_major#$HalfBlue",
            "AREA:major_avg#$HalfRed",
            "LINE1:minor_major#$FullBlue:Minor",
            'GPRINT:minor_min:MIN:%5.1lf%s Min,',
            'GPRINT:minor_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:minor_max:MAX:%5.1lf%s Max,',
            'GPRINT:minor_avg:LAST:%5.1lf%s Last\l',
            "LINE1:major_avg#$FullRed:Major",
            'GPRINT:major_min:MIN:%5.1lf%s Min,',
            'GPRINT:major_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:major_max:MAX:%5.1lf%s Max,',
            'GPRINT:major_avg:LAST:%5.1lf%s Last\l'
        ],
        ps_rss => [
            '-v',
            'Bytes',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:avg#$HalfBlue",
            "LINE1:avg#$FullBlue:RSS",
            'GPRINT:min:MIN:%5.1lf%s Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last\l'
        ],
        ps_state => [
            '-v',
            'Processes',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Processes",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last\l'
        ],
        ps_disk_octets => [
            '-v',
            'Bytes/s',
            'DEF:out_min={file}:write:MIN',
            'DEF:out_avg={file}:write:AVERAGE',
            'DEF:out_max={file}:write:MAX',
            'DEF:inc_min={file}:read:MIN',
            'DEF:inc_avg={file}:read:AVERAGE',
            'DEF:inc_max={file}:read:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            'CDEF:mytime=out_avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:out_avg_sample=out_avg,UN,0,out_avg,IF,sample_len,*',
            'CDEF:out_avg_sum=PREV,UN,0,PREV,IF,out_avg_sample,+',
            'CDEF:inc_avg_sample=inc_avg,UN,0,inc_avg,IF,sample_len,*',
            'CDEF:inc_avg_sum=PREV,UN,0,PREV,IF,inc_avg_sample,+',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Written",
            'GPRINT:out_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:out_max:MAX:%5.1lf%s Max,',
            'GPRINT:out_avg:LAST:%5.1lf%s Last',
            'GPRINT:out_avg_sum:LAST:(ca. %5.1lf%sB Total)\l',
            "LINE1:inc_avg#$FullBlue:Read   ",
            'GPRINT:inc_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:inc_max:MAX:%5.1lf%s Max,',
            'GPRINT:inc_avg:LAST:%5.1lf%s Last',
            'GPRINT:inc_avg_sum:LAST:(ca. %5.1lf%sB Total)\l'
        ],
        ps_disk_ops => [
            '-v',
            'Ops/s',
            'DEF:out_min={file}:write:MIN',
            'DEF:out_avg={file}:write:AVERAGE',
            'DEF:out_max={file}:write:MAX',
            'DEF:inc_min={file}:read:MIN',
            'DEF:inc_avg={file}:read:AVERAGE',
            'DEF:inc_max={file}:read:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Written",
            'GPRINT:out_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:out_max:MAX:%6.2lf Max,',
            'GPRINT:out_avg:LAST:%6.2lf Last\l',
            "LINE1:inc_avg#$FullBlue:Read   ",
            'GPRINT:inc_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:inc_max:MAX:%6.2lf Max,',
            'GPRINT:inc_avg:LAST:%6.2lf Last\l'
        ],
        queue_length => [
            '-v', 'Length',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfMagenta",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullMagenta:Length ",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        signal_noise => [
            '-v', 'Noise',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_min#$HalfRed",
            "AREA:temp_max#$Canvas",
            "LINE1:temp_avg#$FullRed:Value",
            'GPRINT:temp_min:MIN:%6.2lf Min,',
            'GPRINT:temp_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:temp_max:MAX:%6.2lf Max,',
            'GPRINT:temp_avg:LAST:%6.2lf Last\l'
        ],
        signal_power => [
            '-v', 'Power',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_min#$HalfBlue",
            "AREA:temp_max#$Canvas",
            "LINE1:temp_avg#$FullBlue:Value",
            'GPRINT:temp_min:MIN:%6.2lf Min,',
            'GPRINT:temp_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:temp_max:MAX:%6.2lf Max,',
            'GPRINT:temp_avg:LAST:%6.2lf Last\l'
        ],
        signal_quality => [
            '-v', 'Quality',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_max#$HalfBlue",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullBlue:Value",
            'GPRINT:temp_min:MIN:%6.2lf Min,',
            'GPRINT:temp_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:temp_max:MAX:%6.2lf Max,',
            'GPRINT:temp_avg:LAST:%6.2lf Last\l'
        ],
        spectrum => [
            '-v', 'Value',
            '--lower-limit', '0',
            'DEF:all_min={file}:all:MIN',
            'DEF:all_avg={file}:all:AVERAGE',
            'DEF:all_max={file}:all:MAX',
            'DEF:ir_min={file}:ir:MIN',
            'DEF:ir_avg={file}:ir:AVERAGE',
            'DEF:ir_max={file}:ir:MAX',
            "AREA:all_avg#$HalfGreen",
            "AREA:ir_avg#$HalfRed",
            "LINE1:all_avg#$FullGreen:All",
            'GPRINT:all_min:MIN:%6.2lf Min,',
            'GPRINT:all_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:all_max:MAX:%6.2lf Max,',
            'GPRINT:all_avg:LAST:%6.2lf Last\n',
            "LINE1:ir_avg#$FullRed:IR ",
            'GPRINT:ir_min:MIN:%6.2lf Min,',
            'GPRINT:ir_avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:ir_max:MAX:%6.2lf Max,',
            'GPRINT:ir_avg:LAST:%6.2lf Last\l'
        ],
        uptime => [
            '-v', 'Days',
            '--logarithmic', '--units=si',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            'CDEF:avg_days=avg,86400,/',
            'CDEF:max_days=max,86400,/',
            'CDEF:avg_msec=avg,1000,*',
            'CDEF:max_msec=max,1000,*',
            'CDEF:val_time=avg,STEPWIDTH,UNKN,IF,PREV,ADDNAN',
            'CDEF:all_time=avg,STEPWIDTH,STEPWIDTH,IF,PREV,ADDNAN',
            'CDEF:pct_time=val_time,100,*,all_time,/',
            "AREA:max_days#$HalfBlue",
            "LINE1:avg_days#$FullBlue:Uptime",
            'GPRINT:max_msec:MAX:%Dd %02h\:%02m Max,:valstrfduration',
            'GPRINT:avg_msec:LAST:%Dd %02h\:%02m Last,:valstrfduration',
            'GPRINT:pct_time:LAST:%3.0lf%% Active\l'
        ],
        vmpage_number => [
        '-v',
        'Pages',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Number",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        vmpage_faults => [
            "DEF:minf_avg={file}:minflt:AVERAGE",
            "DEF:minf_min={file}:minflt:MIN",
            "DEF:minf_max={file}:minflt:MAX",
            "DEF:majf_avg={file}:majflt:AVERAGE",
            "DEF:majf_min={file}:majflt:MIN",
            "DEF:majf_max={file}:majflt:MAX",
            'CDEF:overlap=majf_avg,minf_avg,GT,minf_avg,majf_avg,IF',
            "AREA:majf_avg#$HalfGreen",
            "AREA:minf_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:majf_avg#$FullGreen:Major",
            'GPRINT:majf_min:MIN:%5.1lf%s Min,',
            'GPRINT:majf_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:majf_max:MAX:%5.1lf%s Max,',
            'GPRINT:majf_avg:LAST:%5.1lf%s Last\l',
            "LINE1:minf_avg#$FullBlue:Minor",
            'GPRINT:minf_min:MIN:%5.1lf%s Min,',
            'GPRINT:minf_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:minf_max:MAX:%5.1lf%s Max,',
            'GPRINT:minf_avg:LAST:%5.1lf%s Last\l'
        ],
        vmpage_io => [
            "DEF:rpag_avg={file}:in:AVERAGE",
            "DEF:rpag_min={file}:in:MIN",
            "DEF:rpag_max={file}:in:MAX",
            "DEF:wpag_avg={file}:out:AVERAGE",
            "DEF:wpag_min={file}:out:MIN",
            "DEF:wpag_max={file}:out:MAX",
            'CDEF:overlap=wpag_avg,rpag_avg,GT,rpag_avg,wpag_avg,IF',
            "AREA:wpag_avg#$HalfGreen",
            "AREA:rpag_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:wpag_avg#$FullGreen:OUT",
            'GPRINT:wpag_min:MIN:%5.1lf%s Min,',
            'GPRINT:wpag_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:wpag_max:MAX:%5.1lf%s Max,',
            'GPRINT:wpag_avg:LAST:%5.1lf%s Last\l',
            "LINE1:rpag_avg#$FullBlue:IN ",
            'GPRINT:rpag_min:MIN:%5.1lf%s Min,',
            'GPRINT:rpag_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:rpag_max:MAX:%5.1lf%s Max,',
            'GPRINT:rpag_avg:LAST:%5.1lf%s Last\l'
        ],
        vmpage_action => [
        '-v',
        'Pages',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Number",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        records => [
            '-v',
            'Records',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            "AREA:temp_max#$HalfBlue",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullBlue:Records",
            'GPRINT:temp_min:MIN:%.3lf%s Min,',
            'GPRINT:temp_avg:AVERAGE:%.3lf%s Avg,',
            'GPRINT:temp_max:MAX:%.3lf%s Max,',
            'GPRINT:temp_avg:LAST:%.3lf%s Last\l'
        ],
        qtype => [
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Queries/s",
            'GPRINT:min:MIN:%9.3lf Min,',
            'GPRINT:avg:AVERAGE:%9.3lf Average,',
            'GPRINT:max:MAX:%9.3lf Max,',
            'GPRINT:avg:LAST:%9.3lf Last\l'
        ],
        rcode => [
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Queries/s",
            'GPRINT:min:MIN:%9.3lf Min,',
            'GPRINT:avg:AVERAGE:%9.3lf Average,',
            'GPRINT:max:MAX:%9.3lf Max,',
            'GPRINT:avg:LAST:%9.3lf Last\l'
        ],
        swap => [
            '-v',
            'Bytes',
            '-b',
            '1024',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Bytes",
            'GPRINT:min:MIN:%6.2lf%sByte Min,',
            'GPRINT:avg:AVERAGE:%6.2lf%sByte Avg,',
            'GPRINT:max:MAX:%6.2lf%sByte Max,',
            'GPRINT:avg:LAST:%6.2lf%sByte Last\l'
        ],
        swap_io => [
             'DEF:min={file}:value:MIN',   'DEF:avg={file}:value:AVERAGE',
             'DEF:max={file}:value:MAX',   "AREA:max#$HalfBlue",
             "AREA:min#$Canvas",           "LINE1:avg#$FullBlue",
             'GPRINT:min:MIN:%6.2lf Min,', 'GPRINT:avg:AVERAGE:%6.2lf Avg,',
             'GPRINT:max:MAX:%6.2lf Max,', 'GPRINT:avg:LAST:%6.2lf Last'
         ],
        old_swap => [
            'DEF:used_avg={file}:used:AVERAGE',
            'DEF:used_min={file}:used:MIN',
            'DEF:used_max={file}:used:MAX',
            'DEF:free_avg={file}:free:AVERAGE',
            'DEF:free_min={file}:free:MIN',
            'DEF:free_max={file}:free:MAX',
            'DEF:cach_avg={file}:cached:AVERAGE',
            'DEF:cach_min={file}:cached:MIN',
            'DEF:cach_max={file}:cached:MAX',
            'DEF:resv_avg={file}:resv:AVERAGE',
            'DEF:resv_min={file}:resv:MIN',
            'DEF:resv_max={file}:resv:MAX',
            'CDEF:cach_avg_notnull=cach_avg,UN,0,cach_avg,IF',
            'CDEF:resv_avg_notnull=resv_avg,UN,0,resv_avg,IF',
            'CDEF:used_acc=used_avg',
            'CDEF:resv_acc=used_acc,resv_avg_notnull,+',
            'CDEF:cach_acc=resv_acc,cach_avg_notnull,+',
            'CDEF:free_acc=cach_acc,free_avg,+',
            "AREA:free_acc#$HalfGreen",
            "AREA:cach_acc#$HalfBlue",
            "AREA:resv_acc#$HalfYellow",
            "AREA:used_acc#$HalfRed",
            "LINE1:free_acc#$FullGreen:Free    ",
            'GPRINT:free_min:MIN:%5.1lf%s Min,',
            'GPRINT:free_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:free_max:MAX:%5.1lf%s Max,',
            'GPRINT:free_avg:LAST:%5.1lf%s Last\n',
            "LINE1:cach_acc#$FullBlue:Cached  ",
            'GPRINT:cach_min:MIN:%5.1lf%s Min,',
            'GPRINT:cach_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:cach_max:MAX:%5.1lf%s Max,',
            'GPRINT:cach_avg:LAST:%5.1lf%s Last\l',
            "LINE1:resv_acc#$FullYellow:Reserved",
            'GPRINT:resv_min:MIN:%5.1lf%s Min,',
            'GPRINT:resv_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:resv_max:MAX:%5.1lf%s Max,',
            'GPRINT:resv_avg:LAST:%5.1lf%s Last\n',
            "LINE1:used_acc#$FullRed:Used    ",
            'GPRINT:used_min:MIN:%5.1lf%s Min,',
            'GPRINT:used_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:used_max:MAX:%5.1lf%s Max,',
            'GPRINT:used_avg:LAST:%5.1lf%s Last\l'
        ],
        tcp_connections => [
            '-v',
            'Connections',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Connections",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last\l'
        ],
        temperature => [
            '-v',
            'Celsius',
            'DEF:temp_avg={file}:value:AVERAGE',
            'DEF:temp_min={file}:value:MIN',
            'DEF:temp_max={file}:value:MAX',
            'CDEF:average=temp_avg,0.2,*,PREV,UN,temp_avg,PREV,IF,0.8,*,+',
            "AREA:temp_max#$HalfRed",
            "AREA:temp_min#$Canvas",
            "LINE1:temp_avg#$FullRed:Temperature",
            'GPRINT:temp_min:MIN:%4.1lf Min,',
            'GPRINT:temp_avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:temp_max:MAX:%4.1lf Max,',
            'GPRINT:temp_avg:LAST:%4.1lf Last\l'
        ],
        timeleft => [
            '-v',
            'Minutes',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Time left [min]",
            'GPRINT:min:MIN:%5.1lf%s Min,',
            'GPRINT:avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max:MAX:%5.1lf%s Max,',
            'GPRINT:avg:LAST:%5.1lf%s Last\l'
        ],
        time_offset => [    # NTPd
            'DEF:s_avg={file}:value:AVERAGE',
            'DEF:s_min={file}:value:MIN',
            'DEF:s_max={file}:value:MAX',
            "AREA:s_max#$HalfBlue",
            "AREA:s_min#$Canvas",
            "LINE1:s_avg#$FullBlue:Seconds",
            'GPRINT:s_min:MIN:%7.3lf%s Min,',
            'GPRINT:s_avg:AVERAGE:%7.3lf%s Avg,',
            'GPRINT:s_max:MAX:%7.3lf%s Max,',
            'GPRINT:s_avg:LAST:%7.3lf%s Last'
        ],
        if_octets => [
            '-v', 'Bits/s', '-l', '0',
            'DEF:out_min_raw={file}:tx:MIN',
            'DEF:out_avg_raw={file}:tx:AVERAGE',
            'DEF:out_max_raw={file}:tx:MAX',
            'DEF:inc_min_raw={file}:rx:MIN',
            'DEF:inc_avg_raw={file}:rx:AVERAGE',
            'DEF:inc_max_raw={file}:rx:MAX',
            'CDEF:out_min=out_min_raw,8,*',
            'CDEF:out_avg=out_avg_raw,8,*',
            'CDEF:out_max=out_max_raw,8,*',
            'CDEF:inc_min=inc_min_raw,8,*',
            'CDEF:inc_avg=inc_avg_raw,8,*',
            'CDEF:inc_max=inc_max_raw,8,*',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            'CDEF:mytime=out_avg_raw,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:out_avg_sample=out_avg_raw,UN,0,out_avg_raw,IF,sample_len,*',
            'CDEF:out_avg_sum=PREV,UN,0,PREV,IF,out_avg_sample,+',
            'CDEF:inc_avg_sample=inc_avg_raw,UN,0,inc_avg_raw,IF,sample_len,*',
            'CDEF:inc_avg_sum=PREV,UN,0,PREV,IF,inc_avg_sample,+',
            'VDEF:out_95=out_avg,95,PERCENT',
            'VDEF:inc_95=inc_avg,95,PERCENT',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE2:out_95#$FullRed",
            "LINE2:inc_95#$FullRed",
            "LINE1:out_avg#$FullGreen:Outgoing",
            'GPRINT:out_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:out_max:MAX:%5.1lf%s Max,',
            'GPRINT:out_avg:LAST:%5.1lf%s Last',
            'GPRINT:out_avg_sum:LAST:(ca. %5.1lf%sB Total)\l',
            "LINE1:out_avg#$FullGreen:Outgoing",
            'GPRINT:out_95:%5.1lf%s 95th Percentile\l',
            "LINE1:inc_avg#$FullBlue:Incoming",
            'GPRINT:inc_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:inc_max:MAX:%5.1lf%s Max,',
            'GPRINT:inc_avg:LAST:%5.1lf%s Last',
            'GPRINT:inc_avg_sum:LAST:(ca. %5.1lf%sB Total)\l',
            "LINE1:inc_avg#$FullBlue:Incoming",
            'GPRINT:inc_95:%5.1lf%s 95th Percentile\l',
        ],
        cpufreq => [
            '-l', '0',
            'DEF:cpufreq_avg={file}:value:AVERAGE',
            'DEF:cpufreq_min={file}:value:MIN',
            'DEF:cpufreq_max={file}:value:MAX',
            "AREA:cpufreq_max#$HalfBlue",
            "AREA:cpufreq_min#$Canvas",
            "LINE1:cpufreq_avg#$FullBlue:Frequency",
            'GPRINT:cpufreq_min:MIN:%5.1lf%s Min,',
            'GPRINT:cpufreq_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:cpufreq_max:MAX:%5.1lf%s Max,',
            'GPRINT:cpufreq_avg:LAST:%5.1lf%s Last\l'
        ],
        total_values => [
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:value",
            'GPRINT:min:MIN:%9.3lf Min,',
            'GPRINT:avg:AVERAGE:%9.3lf Average,',
            'GPRINT:max:MAX:%9.3lf Max,',
            'GPRINT:avg:LAST:%9.3lf Last\l'
        ],
        queue_length => [
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:value",
            'GPRINT:min:MIN:%9.3lf Min,',
            'GPRINT:avg:AVERAGE:%9.3lf Average,',
            'GPRINT:max:MAX:%9.3lf Max,',
            'GPRINT:avg:LAST:%9.3lf Last\l'
        ],
        multimeter => [
            'DEF:multimeter_avg={file}:value:AVERAGE',
            'DEF:multimeter_min={file}:value:MIN',
            'DEF:multimeter_max={file}:value:MAX',
            "AREA:multimeter_max#$HalfBlue",
            "AREA:multimeter_min#$Canvas",
            "LINE1:multimeter_avg#$FullBlue:Multimeter",
            'GPRINT:multimeter_min:MIN:%4.1lf Min,',
            'GPRINT:multimeter_avg:AVERAGE:%4.1lf Average,',
            'GPRINT:multimeter_max:MAX:%4.1lf Max,',
            'GPRINT:multimeter_avg:LAST:%4.1lf Last\l'
        ],
        users => [
            '-v',
            'Users',
            'DEF:users_avg={file}:value:AVERAGE',
            'DEF:users_min={file}:value:MIN',
            'DEF:users_max={file}:value:MAX',
            "AREA:users_max#$HalfBlue",
            "AREA:users_min#$Canvas",
            "LINE1:users_avg#$FullBlue:Users",
            'GPRINT:users_min:MIN:%4.1lf Min,',
            'GPRINT:users_avg:AVERAGE:%4.1lf Average,',
            'GPRINT:users_max:MAX:%4.1lf Max,',
            'GPRINT:users_avg:LAST:%4.1lf Last\l'
        ],
        voltage => [
            '-v',
            'Voltage',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Voltage",
            'GPRINT:min:MIN:%5.2lf%sV Min,',
            'GPRINT:avg:AVERAGE:%5.2lf%sV Avg,',
            'GPRINT:max:MAX:%5.2lf%sV Max,',
            'GPRINT:avg:LAST:%5.2lf%sV Last\l'
        ],
        vs_threads => [
            "DEF:total_avg={file}:total:AVERAGE",
            "DEF:total_min={file}:total:MIN",
            "DEF:total_max={file}:total:MAX",
            "DEF:running_avg={file}:running:AVERAGE",
            "DEF:running_min={file}:running:MIN",
            "DEF:running_max={file}:running:MAX",
            "DEF:uninterruptible_avg={file}:uninterruptible:AVERAGE",
            "DEF:uninterruptible_min={file}:uninterruptible:MIN",
            "DEF:uninterruptible_max={file}:uninterruptible:MAX",
            "DEF:onhold_avg={file}:onhold:AVERAGE",
            "DEF:onhold_min={file}:onhold:MIN",
            "DEF:onhold_max={file}:onhold:MAX",
            "LINE1:total_avg#$FullYellow:Total   ",
            'GPRINT:total_min:MIN:%5.1lf Min,',
            'GPRINT:total_avg:AVERAGE:%5.1lf Avg.,',
            'GPRINT:total_max:MAX:%5.1lf Max,',
            'GPRINT:total_avg:LAST:%5.1lf Last\l',
            "LINE1:running_avg#$FullRed:Running ",
            'GPRINT:running_min:MIN:%5.1lf Min,',
            'GPRINT:running_avg:AVERAGE:%5.1lf Avg.,',
            'GPRINT:running_max:MAX:%5.1lf Max,',
            'GPRINT:running_avg:LAST:%5.1lf Last\l',
            "LINE1:uninterruptible_avg#$FullGreen:Unintr  ",
            'GPRINT:uninterruptible_min:MIN:%5.1lf Min,',
            'GPRINT:uninterruptible_avg:AVERAGE:%5.1lf Avg.,',
            'GPRINT:uninterruptible_max:MAX:%5.1lf Max,',
            'GPRINT:uninterruptible_avg:LAST:%5.1lf Last\l',
            "LINE1:onhold_avg#$FullBlue:Onhold  ",
            'GPRINT:onhold_min:MIN:%5.1lf Min,',
            'GPRINT:onhold_avg:AVERAGE:%5.1lf Avg.,',
            'GPRINT:onhold_max:MAX:%5.1lf Max,',
            'GPRINT:onhold_avg:LAST:%5.1lf Last\l'
        ],
        vs_memory => [
            'DEF:vm_avg={file}:vm:AVERAGE',
            'DEF:vm_min={file}:vm:MIN',
            'DEF:vm_max={file}:vm:MAX',
            'DEF:vml_avg={file}:vml:AVERAGE',
            'DEF:vml_min={file}:vml:MIN',
            'DEF:vml_max={file}:vml:MAX',
            'DEF:rss_avg={file}:rss:AVERAGE',
            'DEF:rss_min={file}:rss:MIN',
            'DEF:rss_max={file}:rss:MAX',
            'DEF:anon_avg={file}:anon:AVERAGE',
            'DEF:anon_min={file}:anon:MIN',
            'DEF:anon_max={file}:anon:MAX',
            "LINE1:vm_avg#$FullYellow:VM     ",
            'GPRINT:vm_min:MIN:%5.1lf%s Min,',
            'GPRINT:vm_avg:AVERAGE:%5.1lf%s Avg.,',
            'GPRINT:vm_max:MAX:%5.1lf%s Avg.,',
            'GPRINT:vm_avg:LAST:%5.1lf%s Last\l',
            "LINE1:vml_avg#$FullRed:Locked ",
            'GPRINT:vml_min:MIN:%5.1lf%s Min,',
            'GPRINT:vml_avg:AVERAGE:%5.1lf%s Avg.,',
            'GPRINT:vml_max:MAX:%5.1lf%s Avg.,',
            'GPRINT:vml_avg:LAST:%5.1lf%s Last\l',
            "LINE1:rss_avg#$FullGreen:RSS    ",
            'GPRINT:rss_min:MIN:%5.1lf%s Min,',
            'GPRINT:rss_avg:AVERAGE:%5.1lf%s Avg.,',
            'GPRINT:rss_max:MAX:%5.1lf%s Avg.,',
            'GPRINT:rss_avg:LAST:%5.1lf%s Last\l',
            "LINE1:anon_avg#$FullBlue:Anon.  ",
            'GPRINT:anon_min:MIN:%5.1lf%s Min,',
            'GPRINT:anon_avg:AVERAGE:%5.1lf%s Avg.,',
            'GPRINT:anon_max:MAX:%5.1lf%s Avg.,',
            'GPRINT:anon_avg:LAST:%5.1lf%s Last\l',
        ],
        vs_processes => [
            'DEF:proc_avg={file}:total:AVERAGE',
            'DEF:proc_min={file}:total:MIN',
            'DEF:proc_max={file}:total:MAX',
            "AREA:proc_max#$HalfBlue",
            "AREA:proc_min#$Canvas",
            "LINE1:proc_avg#$FullBlue:Processes",
            'GPRINT:proc_min:MIN:%4.1lf Min,',
            'GPRINT:proc_avg:AVERAGE:%4.1lf Avg.,',
            'GPRINT:proc_max:MAX:%4.1lf Max,',
            'GPRINT:proc_avg:LAST:%4.1lf Last\l'
        ],
        haproxy_sessions => [
            '-v', 'Sessions', '-l', '0',
            'DEF:que_min={file}:qcur:MIN',
            'DEF:que_ave={file}:qcur:AVERAGE',
            'DEF:que_max={file}:qcur:MAX',
            'DEF:ses_min={file}:scur:MIN',
            'DEF:ses_ave={file}:scur:AVERAGE',
            'DEF:ses_max={file}:scur:MAX',
            "AREA:que_ave#$HalfRed",
            "LINE1:ses_ave#$FullGreen:Current Sessions",
            'GPRINT:ses_min:MIN:Min\: %2.lf',
            'GPRINT:ses_ave:AVERAGE:Ave\: %2.lf',
            'GPRINT:ses_max:MAX:Max\: %2.lf',
            'GPRINT:ses_ave:LAST:Last\: %2.lf\j',
            "LINE1:que_ave#$FullRed:Average Queue",
            'GPRINT:que_min:MIN:Min\: %2.lf',
            'GPRINT:que_ave:AVERAGE:Ave\: %2.lf',
            'GPRINT:que_max:MAX:Max\: %2.lf',
            'GPRINT:que_ave:LAST:Last\: %2.lf\j',
            'COMMENT: \n',
            'COMMENT: qcur is the current queue size \n',
            'COMMENT: scur is the current number of sessions '
        ],
        haproxy_traffic => [
            '-v', 'Req/s', '-l', '0',
            'DEF:stot_min={file}:stot:MIN',
            'DEF:stot_ave={file}:stot:AVERAGE',
            'DEF:stot_max={file}:stot:MAX',
            "AREA:stot_ave#$HalfRed",
            "LINE1:stot_ave#$FullRed:Total Session",
            'GPRINT:stot_min:MIN:Min\: %2.lf',
            'GPRINT:stot_ave:AVERAGE:Ave\: %2.lf',
            'GPRINT:stot_max:MAX:Max\: %2.lf',
            'GPRINT:stot_ave:LAST:Last\: %2.lf\j'
        ],
        haproxy_status => [
            '-v', 'Status', '-l', '0',
            'DEF:stat_min={file}:status:MIN',
            'DEF:stat_ave={file}:status:AVERAGE',
            'DEF:stat_max={file}:status:MAX',
            "AREA:stat_ave#$HalfRed",
            "LINE1:stat_ave#$FullRed:Status",
            'GPRINT:stat_min:MIN:Min\: %2.lf',
            'GPRINT:stat_ave:AVERAGE:Ave\: %2.lf',
            'GPRINT:stat_max:MAX:Max\: %2.lf',
            'GPRINT:stat_ave:LAST:Last\: %2.lf\j'
        ],
        response_time => [
            '-v', 'Seconds', '-l', '0',
            'DEF:rt_avg={file}:value:AVERAGE',
            'DEF:rt_min={file}:value:MIN',
            'DEF:rt_max={file}:value:MAX',
            "AREA:rt_max#$HalfBlue",
            "AREA:rt_min#$Canvas",
            "LINE1:rt_avg#$FullBlue:Response Time",
            'GPRINT:rt_min:MIN:%4.1lf%ss Min,',
            'GPRINT:rt_avg:AVERAGE:%4.1lf%ss Avg,',
            'GPRINT:rt_max:MAX:%4.1lf%ss Max,',
            'GPRINT:rt_avg:LAST:%4.1lf%ss Last'
        ],
        response_code => [
            '-v', 'HTTP Status', '-l', '0',
            'DEF:rt_avg={file}:value:AVERAGE',
            'DEF:rt_min={file}:value:MIN',
            'DEF:rt_max={file}:value:MAX',
            "AREA:rt_max#$HalfBlue",
            "AREA:rt_min#$Canvas",
            "LINE1:rt_avg#$FullBlue:Response Code",
            'GPRINT:rt_min:MIN:%3.0lf Min,',
            'GPRINT:rt_max:MAX:%3.0lf Max,',
            'GPRINT:rt_avg:LAST:%3.0lf Last'
        ],
# jaf-18aug11 additional memcache graphs
        memcached_items => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Items/s",
            'GPRINT:min:MIN:%6.2lf%s Min,',
            'GPRINT:avg:AVERAGE:%6.2lf%s Avg,',
            'GPRINT:max:MAX:%6.2lf%s Max,',
            'GPRINT:avg:LAST:%6.2lf%s Last'
        ],
        memcached_octets => [
            '-v',
            'Bytes/s',
            'DEF:out_min={file}:tx:MIN',
            'DEF:out_avg={file}:tx:AVERAGE',
            'DEF:out_max={file}:tx:MAX',
            'DEF:inc_min={file}:rx:MIN',
            'DEF:inc_avg={file}:rx:AVERAGE',
            'DEF:inc_max={file}:rx:MAX',
            'CDEF:overlap=out_avg,inc_avg,GT,inc_avg,out_avg,IF',
            'CDEF:mytime=out_avg,TIME,TIME,IF',
            'CDEF:sample_len_raw=mytime,PREV(mytime),-',
            'CDEF:sample_len=sample_len_raw,UN,0,sample_len_raw,IF',
            'CDEF:out_avg_sample=out_avg,UN,0,out_avg,IF,sample_len,*',
            'CDEF:out_avg_sum=PREV,UN,0,PREV,IF,out_avg_sample,+',
            'CDEF:inc_avg_sample=inc_avg,UN,0,inc_avg,IF,sample_len,*',
            'CDEF:inc_avg_sum=PREV,UN,0,PREV,IF,inc_avg_sample,+',
            "AREA:out_avg#$HalfGreen",
            "AREA:inc_avg#$HalfBlue",
            "AREA:overlap#$HalfBlueGreen",
            "LINE1:out_avg#$FullGreen:Read   ",
            'GPRINT:out_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:out_max:MAX:%5.1lf%s Max,',
            'GPRINT:out_avg:LAST:%5.1lf%s Last',
            'GPRINT:out_avg_sum:LAST:(ca. %5.1lf%sB Total)\l',
            "LINE1:inc_avg#$FullBlue:Written",
            'GPRINT:inc_avg:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:inc_max:MAX:%5.1lf%s Max,',
            'GPRINT:inc_avg:LAST:%5.1lf%s Last',
            'GPRINT:inc_avg_sum:LAST:(ca. %5.1lf%sB Total)\l'
        ],
# jaf-18aug11 END
# jaf-19aug11 additional MySQL graphs
        cache_size => [
            '-v',
            'Bytes',
            '-b',
            '1024',
            'DEF:raw_avg={file}:value:AVERAGE',
            'DEF:raw_min={file}:value:MIN',
            'DEF:raw_max={file}:value:MAX',
            'CDEF:avg=raw_avg,1024,*',
            'CDEF:min=raw_min,1024,*',
            'CDEF:max=raw_max,1024,*',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Bytes",
            'GPRINT:min:MIN:%6.2lf%sByte Min,',
            'GPRINT:avg:AVERAGE:%6.2lf%sByte Avg,',
            'GPRINT:max:MAX:%6.2lf%sByte Max,',
            'GPRINT:avg:LAST:%6.2lf%sByte Last\l'
        ],
        mysql_locks => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Locks/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
# jaf-19aug11 END
# jaf-18aug11 additional Varnish graphs
        threads => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Threads/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        total_operations => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Operations/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        total_sessions => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Sessions/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
        total_time_in_ms => [
            '-v', 'ms/s',
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:ms/s",
            'GPRINT:min:MIN:%4.1lf Min,',
            'GPRINT:avg:AVERAGE:%4.1lf Avg,',
            'GPRINT:max:MAX:%4.1lf Max,',
            'GPRINT:avg:LAST:%4.1lf Last'
        ],
# jaf-18aug11 END
        total_values => [
            'DEF:min={file}:value:MIN',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:max={file}:value:MAX',
            "AREA:max#$HalfBlue",
            "AREA:min#$Canvas",
            "LINE1:avg#$FullBlue:Values/s",
            'GPRINT:min:MIN:%6.2lf Min,',
            'GPRINT:avg:AVERAGE:%6.2lf Avg,',
            'GPRINT:max:MAX:%6.2lf Max,',
            'GPRINT:avg:LAST:%6.2lf Last'
        ],
# nm-4Sept13 filecount
        files => [
            '-v',
            'File Count',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:avg#$HalfBlue",
            "LINE1:avg#$FullBlue:Files",
            'GPRINT:min:MIN:%9.3lf Min,',
            'GPRINT:avg:AVERAGE:%9.3lf Average,',
            'GPRINT:max:MAX:%9.3lf Max,',
            'GPRINT:avg:LAST:%9.3lf Last'
        ],
        bytes => [
            '-b',
            '1024',
            '-v',
            'Bytes',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:avg#$HalfRed",
            "LINE1:avg#$FullRed:Bytes",
            'GPRINT:min:MIN:%3.3lf%s Min,',
            'GPRINT:avg:AVERAGE:%3.3lf%s Average,',
            'GPRINT:max:MAX:%3.3lf%s Max,',
            'GPRINT:avg:LAST:%3.3lf%s Last'
        ],
# nm-4Sept13 filecount - END
# nm-4Sept13 contextswitch
        contextswitch => [
            '-v',
            'Context Switches /s',
            'DEF:avg={file}:value:AVERAGE',
            'DEF:min={file}:value:MIN',
            'DEF:max={file}:value:MAX',
            "AREA:avg#$HalfBlue",
            "LINE1:avg#$FullBlue:Switches/s",
            'GPRINT:min:MIN:%9.3lf Min,',
            'GPRINT:avg:AVERAGE:%9.3lf Average,',
            'GPRINT:max:MAX:%9.3lf Max,',
            'GPRINT:avg:LAST:%9.3lf Last'
        ],
# nm-4Sept13 contextswitch - END
# mbr-2Nov20 radsniff BEGIN
       radius_count => [ '-l', 0,
              '--vertical-label', 'PPS',
               'DEF:received={file}:received:AVERAGE',
               'DEF:linked={file}:linked:AVERAGE',
               'DEF:unlinked={file}:unlinked:AVERAGE',
               'DEF:reused={file}:reused:AVERAGE',
               'AREA:received#DD44CC:received',
               'AREA:linked#66BBCC:linked',
               'STACK:unlinked#7FFF00:unlinked',
               'STACK:reused#FF8C00:reused'
       ],
       radius_latency => [ '-l', 0,
               '--vertical-label', 'Latency (ms)',
               'DEF:high={file}:high:MAX',
               'DEF:low={file}:low:MIN',
               'DEF:avg={file}:avg:AVERAGE',
               'CDEF:trend1800=avg,1800,TRENDNAN',
               'CDEF:trend86400=avg,86400,TRENDNAN',
               'LINE:high#66BBCC:high',
               'LINE:low#DD44CC:low',
               'LINE:avg#7FFF00:avg',
               'LINE:trend1800#718D00:avg_30m',
               'LINE:trend86400#946A00:avg_day'
       ],
       radius_rtx => [ '-l', 0,
               '--vertical-label', 'Requests completed per second',
               'DEF:none={file}:none:AVERAGE',
               'DEF:1={file}:1:AVERAGE',
               'DEF:2={file}:2:AVERAGE',
               'DEF:3={file}:3:AVERAGE',
               'DEF:4={file}:4:AVERAGE',
               'DEF:more={file}:more:AVERAGE',
               'DEF:lost={file}:lost:AVERAGE',
               'AREA:none#2AD400:none',
               'STACK:1#4DB000:1',
               'STACK:2#718D00:2',
               'STACK:3#946A00:3',
               'STACK:4#B84600:4',
               'STACK:more#DB2300:more',
               'STACK:lost#FF0000:lost'
       ],
# mbr-2Nov20 radsniff END
    };
    $GraphDefs->{'if_multicast'}        = $GraphDefs->{'ipt_packets'};
    $GraphDefs->{'if_tx_errors'}        = $GraphDefs->{'if_rx_errors'};
    #$GraphDefs->{'dns_rcode'}           = $GraphDefs->{'dns_opcode'};
    #$GraphDefs->{'dns_qtype'}           = $GraphDefs->{'dns_opcode'};
    $GraphDefs->{'ps_code'}             = $GraphDefs->{'ps_state'};
    $GraphDefs->{'ps_data'}             = $GraphDefs->{'ps_state'};
    $GraphDefs->{'ps_stacksize'}        = $GraphDefs->{'ps_state'};
    $GraphDefs->{'ps_vm'}               = $GraphDefs->{'ps_state'};
    $GraphDefs->{'full_join'}        = $GraphDefs->{'mysql_qcache'};
    $GraphDefs->{'mysql_sort_merge_passes'} = $GraphDefs->{'mysql_slow_queries'};
    $GraphDefs->{'mysql_sort_rows'} = $GraphDefs->{'mysql_slow_queries'};
# jaf-18aug11 additional Varnish graphs
    $GraphDefs->{'memcached_command'}       = $GraphDefs->{'total_operations'};
    $GraphDefs->{'memcached_connections'}   = $GraphDefs->{'apache_connections'};
    $GraphDefs->{'memcached_ops'}           = $GraphDefs->{'total_operations'};
# jaf-18aug11 END
# jaf-18aug11 additional Varnish graphs
    $GraphDefs->{'total_bytes'}         = $GraphDefs->{'apache_bytes'};
    $GraphDefs->{'total_requests'}      = $GraphDefs->{'apache_requests'};
    $GraphDefs->{'total_threads'}       = $GraphDefs->{'threads'};
# jaf-18aug11 END
    $GraphDefs->{'vmpage_io-memory'}    = $GraphDefs->{'vmpage_io'};
    $GraphDefs->{'vmpage_io-swap'}      = $GraphDefs->{'vmpage_io'};
    $GraphDefs->{'cache_operation'}     = $GraphDefs->{'cache_result'};
    $GraphDefs->{'memory_throttle_count'} = $GraphDefs->{'cache_result'};
    $GraphDefs->{'hash_collisions'}     = $GraphDefs->{'cache_result'};
    $GraphDefs->{'operations'} = $GraphDefs->{'derive'};
    $GraphDefs->{'queue_length'} = $GraphDefs->{'gauge'};
    $GraphDefs->{'total_values'} = $GraphDefs->{'gauge'};
    $GraphDefs->{'total_events'}    = $GraphDefs->{'gauge'};
    $GraphDefs->{'current_connections'} = $GraphDefs->{'connections'};
    $GraphDefs->{'total_connections'}   = $GraphDefs->{'connections'};
    $GraphDefs->{'blocked_clients'}     = $GraphDefs->{'gauge'};
    $GraphDefs->{'evicted_keys'}        = $GraphDefs->{'derive'};
    $GraphDefs->{'expired_keys'}        = $GraphDefs->{'derive'};
    $GraphDefs->{'memory_lua'}          = $GraphDefs->{'gauge'};
    $GraphDefs->{'operations_per_second'}    = $GraphDefs->{'gauge'};
    $GraphDefs->{'volatile_changes'}    = $GraphDefs->{'gauge'};
    $GraphDefs->{'pending_operations'} = $GraphDefs->{'derive'};
    $MetaGraphDefs->{'cpu'}             = \&meta_graph_cpu;
    $MetaGraphDefs->{'df_complex'}      = \&meta_graph_df_complex;
    $MetaGraphDefs->{'dns_qtype'}       = \&meta_graph_dns;
    $MetaGraphDefs->{'dns_rcode'}       = \&meta_graph_dns;
    $MetaGraphDefs->{'if_rx_errors'}    = \&meta_graph_if_rx_errors;
    $MetaGraphDefs->{'if_tx_errors'}    = \&meta_graph_if_rx_errors;
    $MetaGraphDefs->{'memory'}          = \&meta_graph_memory;
    $MetaGraphDefs->{'pubsub'}          = \&meta_graph_memory;
    $MetaGraphDefs->{'nfs_procedure'}   = \&meta_graph_nfs_procedure;
    $MetaGraphDefs->{'pkg'}             = \&meta_graph_pkg;
    $MetaGraphDefs->{'ps_state'}        = \&meta_graph_ps_state;
    $MetaGraphDefs->{'swap'}            = \&meta_graph_swap;
    $MetaGraphDefs->{'mysql_commands'}  = \&meta_graph_mysql_commands;
    $MetaGraphDefs->{'mysql_handler'}   = \&meta_graph_mysql_commands;
    $MetaGraphDefs->{'mysql_select'}    = \&meta_graph_mysql_commands;
    $MetaGraphDefs->{'mysql_sort'}      = \&meta_graph_mysql_commands;
    $MetaGraphDefs->{'tcp_connections'} = \&meta_graph_tcp_connections;
    $MetaGraphDefs->{'vmpage_number'}   = \&meta_graph_vmpage_number;
    $MetaGraphDefs->{'vmpage_action'}   = \&meta_graph_vmpage_action;
    $MetaGraphDefs->{'fscache_stat'}    = \&meta_graph_dns;
    $MetaGraphDefs->{'num_class'}       = \&meta_graph_dns;
    $MetaGraphDefs->{'num_type'}        = \&meta_graph_dns;
    $MetaGraphDefs->{'num_opcode'}      = \&meta_graph_dns;
    $MetaGraphDefs->{'num_rcode'}       = \&meta_graph_dns;
    $MetaGraphDefs->{'thread1_num'}     = \&meta_graph_dns;
    $MetaGraphDefs->{'thread2_num'}     = \&meta_graph_dns;
    $MetaGraphDefs->{'thread3_num'}     = \&meta_graph_dns;
    $MetaGraphDefs->{'thread4_num'}     = \&meta_graph_dns;
}    # load_graph_definitions

sub meta_graph_generic_stack {
    confess("Wrong number of arguments") if ( @_ != 2 );
    my $opts    = shift;
    my $sources = shift;
    my $i;
    my $timespan_str = _get_param_timespan();
    my $timespan_int = (-1) * $ValidTimespan->{$timespan_str};
    $opts->{'title'}    ||= 'Unknown title';
    $opts->{'rrd_opts'} ||= [];
    $opts->{'colors'}   ||= {};
    $opts->{'ds'}       ||= 'rate';

    my $start_time;
    my $end_time;
    my @cmd;
    if (defined($Args->{'end'})) {
        $start_time = $Args->{'start'};
        $end_time = $Args->{'end'};
        @cmd = (
            '-',
            '-a', $OutputFormat,
            '-s', $start_time,
            '-e', $end_time,
            '-t', $opts->{'title'} || 'Unknown title',
            @RRDDefaultArgs,
            @{ $opts->{'rrd_opts'} }
        );
    } else {
        @cmd = (
            '-',
            '-a', $OutputFormat,
            '-s', $timespan_int,
            '-t', $opts->{'title'} || 'Unknown title',
            @RRDDefaultArgs,
            @{ $opts->{'rrd_opts'} }
        );
    }
    my $max_inst_name = 0;

    for ( $i = 0 ; $i < @$sources ; $i++ ) {
        my $inst_data = $sources->[$i];
        my $inst_name = $inst_data->{'name'} || confess;
        my $file      = $inst_data->{'file'} || confess;
        if ( length($inst_name) > $max_inst_name ) {
            $max_inst_name = length($inst_name);
        }
        confess("No such file: $file") if ( !-e $file );

	# Workaround some RRDCACHED_FLUSH absolute path issues.
	for (@DataDirs) {
	    if ($file =~ qr|^$_/(.*)$|) {
		$file = $1;
		chdir($_);
		last;
	    }
	}

        push( @cmd,
            qq#DEF:${inst_name}_min=$file:value:MIN#,
            qq#DEF:${inst_name}_avg=$file:value:AVERAGE#,
            qq#DEF:${inst_name}_max=$file:value:MAX#,
        );
        if ( $opts->{'ds'} eq 'rate' ) {
            push( @cmd,
                qq#CDEF:${inst_name}_nnl=${inst_name}_avg,UN,0,${inst_name}_avg,IF#
            );
        } else {
            push( @cmd,
                qq#CDEF:${inst_name}_nnl=${inst_name}_avg,UN,0,${inst_name}_avg,IF,STEPWIDTH,*#
            );
        }
    }
    {
        my $inst_data = $sources->[ @$sources - 1 ];
        my $inst_name = $inst_data->{'name'};
        push( @cmd, qq#CDEF:${inst_name}_stk=${inst_name}_nnl# );
    }
    for ( my $i = 1 ; $i < @$sources ; $i++ ) {
        my $inst_data0 = $sources->[ @$sources - ( $i + 1 ) ];
        my $inst_data1 = $sources->[ @$sources - $i ];
        my $inst_name0 = $inst_data0->{'name'};
        my $inst_name1 = $inst_data1->{'name'};
        push( @cmd,
            qq#CDEF:${inst_name0}_stk=${inst_name0}_nnl,${inst_name1}_stk,+# );
    }
    for ( my $i = 0 ; $i < @$sources ; $i++ ) {
        my $inst_data = $sources->[$i];
        my $inst_name = $inst_data->{'name'};
        my $legend    = sprintf( '%-*s\t', $max_inst_name, $inst_name );
        my $line_color;
        my $area_color;
        my $number_format = $opts->{'number_format'} || '%6.1lf';
        if ( exists( $opts->{'colors'}{$inst_name} ) ) {
            $line_color = $opts->{'colors'}{$inst_name};
            $area_color = _string_to_color($line_color);
        }
        else {
            $area_color = _get_random_color();
            $line_color = _color_to_string($area_color);
        }
        $area_color = _color_to_string( _get_faded_color($area_color) );
        push( @cmd,
            qq(AREA:${inst_name}_stk#$area_color),
            qq(LINE1:${inst_name}_stk#$line_color:$legend),
        );
        if ( $opts->{'ds'} eq 'rate' ) {
            push( @cmd,
                qq(GPRINT:${inst_name}_min:MIN:$number_format Min,),
                qq(GPRINT:${inst_name}_avg:AVERAGE:$number_format Avg,),
                qq(GPRINT:${inst_name}_max:MAX:$number_format Max,),
                qq(GPRINT:${inst_name}_avg:LAST:$number_format Last\\l),
            );
        } else {
            push( @cmd,
                qq(GPRINT:${inst_name}_nnl:MIN:$number_format Min,),
                qq(GPRINT:${inst_name}_nnl:AVERAGE:$number_format Avg,),
                qq(GPRINT:${inst_name}_nnl:MAX:$number_format Max,),
                qq(GPRINT:${inst_name}_nnl:LAST:$number_format Last\\l),
            );
        }
    }
    RRDs::graph(@cmd);
    if ( my $errmsg = RRDs::error() ) {
        confess("RRDs::graph: $errmsg");
    }
}    # meta_graph_generic_stack

sub meta_graph_cpu {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'rrd_opts'} = [ '-v', 'Percent' ];
    my @files = ();
    $opts->{'colors'} = {
        'idle'      => '333333',
        'nice'      => '00e000',
        'user'      => '0000ff',
        'wait'      => 'ffb000',
        'system'    => 'ff0000',
        'softirq'   => 'ff00ff',
        'interrupt' => 'a000a0',
        'steal'     => '000000'
    };
    _custom_sort_arrayref( $type_instances,
        [qw(idle nice user wait system softirq interrupt steal)] );

    for (@$type_instances) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => $inst,
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_cpu

sub meta_graph_df_complex {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
        . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
        . "/$type";
    $opts->{'number_format'} = '%5.1lf%s';
    $opts->{'rrd_opts'} = [ '-b', '1024', '-v', 'Bytes' ];
    my @files = ();
    $opts->{'colors'} = {
        'free'      => '00e000',
        'used'      => 'ff0000',
        'reserved'  => '0000ff'
    };

    _custom_sort_arrayref( $type_instances, [qw(free used reserved)] );

    for (@$type_instances) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }

    confess ("No file found for $title") if ($file eq '');

    push (@$sources,
      {
    name => $inst,
    file => $file
      }
    );
  } # for (@$type_instances)

  return (meta_graph_generic_stack ($opts, $sources));
} # meta_graph_df_complex


sub meta_graph_dns
{
  confess ("Wrong number of arguments") if (@_ != 5);

  my $host = shift;
  my $plugin = shift;
  my $plugin_instance = shift;
  my $type = shift;
  my $type_instances = shift;

  my $opts = {};
  my $sources = [];

  $opts->{'title'} = "$host/$plugin"
  . (defined ($plugin_instance) ? "-$plugin_instance" : '') . "/$type";

  $opts->{'rrd_opts'} = ['-v', 'Queries/s'];

  my @files = ();

  @$type_instances = sort @$type_instances;

  ##$opts->{'colors'} = _get_n_colors ($type_instances);

  for (@$type_instances)
  {
    next if /#/;
    my $inst = $_;
    my $file = '';
    my $title = $opts->{'title'};

    for (@DataDirs)
    {
      if (-e "$_/$title-$inst.rrd")
      {
    $file = "$_/$title-$inst.rrd";
    last;
      }
    }
    confess ("No file found for $title") if ($file eq '');

    push (@$sources,
      {
    name => $inst,
    file => $file
      }
    );
  } # for (@$type_instances)

  return (meta_graph_generic_stack ($opts, $sources));
} # meta_graph_dns

sub meta_graph_memory {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'number_format'} = '%5.1lf%s';
    $opts->{'rrd_opts'} = [ '-b', '1024', '-v', 'Bytes' ];
    my @files = ();
    $opts->{'colors'} = {
        'free'     => '00e000',
        'cached'   => '0000ff',
        'buffered' => 'ffb000',
        'used'     => 'ff0000'
    };
    _custom_sort_arrayref( $type_instances, [qw(free cached buffered used)] );

    for (@$type_instances) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => $inst,
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_cpu

sub meta_graph_if_rx_errors {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'number_format'} = '%5.2lf';
    $opts->{'rrd_opts'} = [ '-v', 'Errors/s' ];
    my @files = ();

    for ( sort @$type_instances ) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => $inst,
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_if_rx_errors

sub meta_graph_mysql_commands {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'number_format'} = '%5.2lf';
    my @files = ();

    for ( sort @$type_instances ) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => $inst,
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_mysql_commands

sub meta_graph_nfs_procedure {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'number_format'} = '%5.1lf%s';
    my @files = ();

    for ( sort @$type_instances ) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => $inst,
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_nfs_procedure

sub meta_graph_pkg {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'rrd_opts'} = [ '-v', 'PKGs' ];
    $opts->{'ds'} = 'values';
    my @files = ();
    $opts->{'colors'} = {
        'skipped'   => 'ffe000',
        'built'     => '00e000',
        'failed'    => 'ff0000',
        'ignored'   => 'ff00ff'
    };
    _custom_sort_arrayref( $type_instances,
        [qw(skipped built failed ignored)] );

    for (@$type_instances) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        next if ( $inst eq 'queued' );
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => $inst,
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_pkg

sub meta_graph_ps_state {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'rrd_opts'} = [ '-v', 'Processes' ];
    my @files = ();
    $opts->{'colors'} = {
        'Running'  => '00e000',
        'Sleeping' => '0000ff',
        'Paging'   => 'ffb000',
        'Zombies'  => 'ff0000',
        'Blocked'  => 'ff00ff',
        'Stopped'  => 'a000a0'
    };
    _custom_sort_arrayref( $type_instances,
        [qw(paging blocked zombies stopped running sleeping)] );

    for (@$type_instances) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => ucfirst($inst),
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_ps_state

sub meta_graph_swap {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'number_format'} = '%5.1lf%s';
    $opts->{'rrd_opts'} = [ '-v', 'Bytes' ];
    my @files = ();
    $opts->{'colors'} = {
        'Free'     => '00e000',
        'Cached'   => '0000ff',
        'Reserved' => 'ffb000',
        'Used'     => 'ff0000'
    };
    _custom_sort_arrayref( $type_instances, [qw(free cached reserved used)] );

    for (@$type_instances) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => ucfirst($inst),
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_swap

sub meta_graph_tcp_connections {
    confess("Wrong number of arguments") if ( @_ != 5 );
    my $host            = shift;
    my $plugin          = shift;
    my $plugin_instance = shift;
    my $type            = shift;
    my $type_instances  = shift;
    my $opts            = {};
    my $sources         = [];
    $opts->{'title'} =
        "$host/$plugin"
      . ( defined($plugin_instance) ? "-$plugin_instance" : '' )
      . "/$type";
    $opts->{'number_format'} = '%6.2lf';
    $opts->{'rrd_opts'} = [ '-v', 'Connections' ];
    my @files = ();
    $opts->{'colors'} = {
        ESTABLISHED => '00e000',
        SYN_SENT    => '00e0ff',
        SYN_RECV    => '00e0a0',
        FIN_WAIT1   => 'f000f0',
        FIN_WAIT2   => 'f000a0',
        TIME_WAIT   => 'ffb000',
        CLOSE       => '0000f0',
        CLOSE_WAIT  => '0000a0',
        LAST_ACK    => '000080',
        LISTEN      => 'ff0000',
        CLOSING     => '000000'
    };
    _custom_sort_arrayref(
        $type_instances,
        [
            reverse
              qw(ESTABLISHED SYN_SENT SYN_RECV FIN_WAIT1 FIN_WAIT2 TIME_WAIT CLOSE
              CLOSE_WAIT LAST_ACK CLOSING LISTEN)
        ]
    );
    for (@$type_instances) {
        my $inst  = $_;
        my $file  = '';
        my $title = $opts->{'title'};
        for (@DataDirs) {
            if ( -e "$_/$title-$inst.rrd" ) {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess("No file found for $title") if ( $file eq '' );
        push(
            @$sources,
            {
                name => $inst,
                file => $file
            }
        );
    }    # for (@$type_instances)
    return ( meta_graph_generic_stack( $opts, $sources ) );
}    # meta_graph_tcp_connections

sub meta_graph_vmpage_number
{
    confess ("Wrong number of arguments") if (@_ != 5);

    my $host = shift;
    my $plugin = shift;
    my $plugin_instance = shift;
    my $type = shift;
    my $type_instances = shift;

    my $opts = {};
    my $sources = [];

    $opts->{'title'} = "$host/$plugin"
      . (defined ($plugin_instance) ? "-$plugin_instance" : '') . "/$type";
    $opts->{'number_format'} = '%6.2lf';

    $opts->{'rrd_opts'} = ['-v', 'Pages'];

    my @files = ();

    $opts->{'colors'} =
    {
        anon_pages       => '00e000',
        bounce           => '00e0ff',
        dirty            => '00e0a0',
        file_pages       => 'f000f0',
        mapped           => 'f000a0',
        page_table_pages => 'ffb000',
        slab             => '0000f0',
        unstable         => '0000a0',
        writeback        => 'ff0000',
    };

    _custom_sort_arrayref ($type_instances,
      [reverse qw(anon_pages bounce dirty file_pages mapped page_table_pages slab unstable writeback)]);

    for (@$type_instances) {
        my $inst = $_;
        my $file = '';
        my $title = $opts->{'title'};

        for (@DataDirs) {
            if (-e "$_/$title-$inst.rrd") {
                $file = "$_/$title-$inst.rrd";
                last;
            }
        }
        confess ("No file found for $title") if ($file eq '');

        push (@$sources,
          {
              name => $inst,
              file => $file
          }
        );
    } # for (@$type_instances)

    return (meta_graph_generic_stack ($opts, $sources));
} # meta_graph_vmpage_number

sub meta_graph_vmpage_action
{
    confess ("Wrong number of arguments") if (@_ != 5);

    my $host = shift;
    my $plugin = shift;
    my $plugin_instance = shift;
    my $type = shift;
    my $type_instances = shift;

    my $opts = {};
    my $sources = [];

    $opts->{'title'} = "$host/$plugin"
      . (defined ($plugin_instance) ? "-$plugin_instance" : '') . "/$type";
    $opts->{'number_format'} = '%6.2lf';

    $opts->{'rrd_opts'} = ['-v', 'Pages'];

    my @files = ();

    $opts->{'colors'} =
    {
        activate    => '00e000',
        deactivate  => '00e0ff',
        free        => '00e0a0',
        alloc       => 'f000f0',
        refill      => 'f000a0',
        scan_direct => 'ffb000',
        scan_kswapd => '0000f0',
        steal       => '0000a0',
    };

    _custom_sort_arrayref ($type_instances,
      [reverse qw(activate deactivate alloc free refill scan_direct scan_kswapd steal)]);

    for (@$type_instances) {
      my $inst = $_;
      my $file = '';
      my $title = $opts->{'title'};

      for (@DataDirs) {
          if (-e "$_/$title-$inst.rrd") {
              $file = "$_/$title-$inst.rrd";
              last;
          }
      }
      confess ("No file found for $title") if ($file eq '');

      push (@$sources,
        {
    name => $inst,
    file => $file
        }
      );
    } # for (@$type_instances)

    return (meta_graph_generic_stack ($opts, $sources));
} # meta_graph_vmpage_action

# vim: shiftwidth=4:softtabstop=4:tabstop=8
