// Collectd-web - base.js
// Copyright (C) 2009-2010  Kenneth Belitzky
//
// This program is free software; you can redistribute it and/or modify it under
// the terms of the GNU General Public License as published by the Free Software
// Foundation; either version 2 of the License, or (at your option) any later
// version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
// details.
//
// You should have received a copy of the GNU General Public License along with
// this program; if not, write to the Free Software Foundation, Inc.,
// 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


/**
 * Global vars
 */
var $selected_host = '';
var $selected_plugin = '';
var $graph_json = null;
var window_top = 0;
var previous_window_top = 0;


// error free logger taken from:
// http://goo.gl/yG9Gb
var Fb = {}; //An empty object literal for holding the function
Fb.log = function(obj, consoleMethod) {
       if (window.console && window.console.firebug && window.console.firebug.replace(/^\s\s*/, '').replace(/\s\s*$/, '') !== '') {
               if (typeof consoleMethod === "string" && typeof console[consoleMethod] === "function") {
                       console[consoleMethod](obj);
               } else {
                       console.log(obj);
               }
       }
};

var server_tz = 0;

/**
 * Returns a current Date object, representing server time.
 */
function server_now() {
    var d = new Date(),
        local_time = d.getTime(),
        local_offset = d.getTimezoneOffset() * 60000,
        utc = local_time + local_offset,
        server = utc + (3600000 * server_tz);
    return new Date(server);
}

/*
 * checks to see if the number is negative
 *
 */
function is_neg(string) {
    var numericExpression = /^-[0-9]+$/;

    if(string.match(numericExpression)) {
        return true;
    } else {
        return false;
    }
}


/**
 * Get the id of the container for the selected element
 *
 * @param {Object}
 *            elem
 */

function get_container(elem) {
    return $(elem).parent().parent().parent().attr('id');
}

var graph_def_values = [];

function get_gmt(offset) {
    off = '';
    if (offset === 0) {
        off = '';
    } else if (offset > 0) {
        off = '+' + offset;
    } else {
        off = offset;
    }
    return offset;
}

function get_url_params(in_url) {
    var params = {};
    if (in_url) {
        var nurl = in_url.replace(/.*\?(.*?)/, "$1");
        variables = nurl.split(";");
        for (i = 0; i < variables.length; i++) {
            separ = variables[i].split("=");
            params[separ[0]] = separ[1];
        }
    }
    Fb.log(params,"info");
    return params;
}


function get_timespan_start (timespan) {
    var out_date = server_now();
    switch (timespan) {
        case "hour":
            out_date.add(-1).hours();
            break;
        case "day":
            out_date.add(-1).days();
            break;
        case "week":
            out_date.add(-1).weeks();
            break;
        case "month":
            out_date.add(-1).months();
            break;
        case "year":
            out_date.add(-1).years();
            break;
        case "decade":
            out_date.add(-10).years();
            break;
    }
    return out_date;
}

/**
 * Build up and url with the given parameters
 * @param original_url string with the original url
 * @param params hash with all parameters to add to the url
 * @return string
 */

function build_url(original_url, new_params) {
    Fb.log(new_params, "warning");
    params = get_url_params(original_url);
    $.extend(params, new_params);
    var url = original_url.split('?')[0] + '?';
    for (key in params) {
        if (params[key] !== '' || params[key] === 0) {
        url += key + '=' + params[key] + ';';
        }
    }
    Fb.log(url,"info");
    return url;
}

function is_dark_mode() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function build_url_with_theme(url, params) {
    if (is_dark_mode()) {
        params.theme = 'dark';
    }
    return build_url(url, params);
}

function hide_toolbar_items () {
    $('.toolbar-item').fadeOut();
}

/**
 * default control container
 *
 * @param {Object}
 *            txt
 */

function control_container(txt) {
    return '<div class="icons ui-state-default ui-corner-all">' + txt + '</div>';
}

/**
 * return html structure for the available plugins menu
 * @param host
 * @param plugins
 * @return
 */

function create_plugin_menu(host, plugins) {
    var tpl = '<div><div class="ui-widget-header ui-corner-top"><h3>Available Plugins</h3></div>';
    tpl += '<div id="plugin-container" class="ui-widget-content ui-corner-bottom  "><ul>';
    for (var p = 0; p < plugins.length; p++) {
        tpl += '<li><a href="cgi-bin/collection.modified.cgi?action=show_plugin;host=' + host +
            ';timespan=day;plugin=' + plugins[p] + '" onclick="window.scrollTo(0, 0)">' + plugins[p] + '</a></li>';
    }
    tpl += '</ul></div>';
    tpl += '</div>';
    return tpl;
}

function get_graph_menu() {
    return $('#graph-menu-partial').html();
}

function update_all_graphs(start, end) {
    $('.gc-img').each(function () {
        var $this = $(this),
            new_url = build_url_with_theme($this.attr('src'), {
            'start': print_date(start),
            'end': print_date(end)
        });
        $this.attr('src', new_url);
    });
}

function get_graph_main_container(host) {
    $('.graph-main-container .hostname').html(host);
    return $('.graph-main-container').html();
}

function show_lazy_graph(elem) {
    $(elem).attr('src', $(elem).attr('title'));
}

function create_graph_list(timespan, graphs) {
    var end_date = server_now();
    var start_date = get_timespan_start(timespan);

    var $tpl = '';
    var final_url = '';
    $tpl += '<li class="ui-widget graph-image ' + timespan + '">';
    $tpl += '<ul class="sortable ui-sortable">';
    for (var g = 0; g < graphs.length; g++) {
        final_url = build_url_with_theme(graphs[g], {'start': print_date(start_date), 'end': print_date(end_date)});
        $tpl += '<li class="gc">';
        $tpl += get_graph_menu();
        if ($('#graph-caching-checkbox').attr('checked')) {
            $tpl += '<img class="gc-img toload" src="media/images/graph-load.png" title="' + final_url + '"/></li>';
        } else {
            $tpl += '<img class="gc-img" src="' + final_url + '"/></li>';
        }
        $tpl += '</li>';
    }
    $tpl += '</ul>';
    $tpl += '</li>';
    $('.graph-imgs-container').append($tpl);
}

function lazy_check() {
    if ($('#graph-caching-checkbox').attr('checked')) {
        $('.toload.gc-img').each(function () {
            window_top = $(window).height() + $(window).scrollTop();
            var elem_top = $(this).offset().top;
            if ((window_top > elem_top) && (elem_top !== 0)) {
                show_lazy_graph(this);
                $(this).removeClass('toload');
            }

        });
    }
}

/**
 * check which container anchor is clicked and load the apropiate container
 *
 * @param {Object}
 *            url
 */
var load_url = function () {
    var url = $(this).attr('href');
    var place = '#plugins';
    if (get_container(this) == 'hosts-container') {
        $('#hosts a').each(function () {
            $(this).removeClass('selected');
        });
        $selected_host = $(this).html();
        $.getJSON('cgi-bin/collection.modified.cgi?action=pluginlist_json&host=' + $selected_host, function (data) {
            $("#plugins").html('');
            $("#plugins").append(create_plugin_menu($selected_host, data));

            $('#plugins ul li a').click(function () {
                $('#plugins').data('selected_plugin', $(this).attr('rel'));
            });
        });
    } else {
        $selected_plugin = $(this).html();
        $(".graph-imgs-container").html('');
        $.getJSON('cgi-bin/collection.modified.cgi?action=graphs_json;plugin=' + $selected_plugin + ';host=' + $selected_host, function (data) {
            $graph_json = data;
            create_graph_list("day", data.day);
            $('#graph-container').html(get_graph_main_container($selected_host));

            lazy_check();
        });
    }


    $('#plugins a').each(function () {
        $(this).removeClass('selected');
    });

    $(this).addClass('selected');

    return false;
};

function ipad_position_fix () {

    if(navigator.platform == 'iPad' || navigator.platform == 'iPhone' || navigator.platform == 'iPod')
    {
        $( window ).scroll( function ( ) {
            $( "#toolbar-container" ).css( "top", ( $( window ).height() + $( document ).scrollTop() - 30 ) +"px" );
        } );
    }
}

$(document).ready(function () {

    $('#menu-tabs').tabs();
    $('button').button();

    $.ajaxSetup({ cache: true });

    $("#loading").ajaxStart(function () { $(this).show(); });

    $("#loading").ajaxStop(function () {
        $(this).hide();
        $('.sortable').sortable();
        $('#graph-view').trigger('change');
    });

    $.getJSON('cgi-bin/collection.modified.cgi?action=hostlist_json', function (data) {
        for (i = 0; i < data.length; i++) {
            $("#hosts ul").append('<li><a href="cgi-bin/collection.modified.cgi?action=show_host;host=' + data[i] + '" onclick="window.scrollTo(0, document.body.scrollHeight)">'
                + data[i] + '</a></li>');
        }
    });

    $('.ttip').hover(function () {
                        var text = $(this).find('div.ttip-content').html();
                        $('#help-box').html(text).fadeIn();
                    },
                     function () {
                        $('#help-box').html('').hide();
                    });

    // set local and server time
    $("#clock").jclock();

    $.getJSON('cgi-bin/time.cgi', function (data) {
        server_tz = parseInt(data.tz, 10);
        $("#clock-server").jclock({
            utc: true,
            utcOffset: server_tz
        });

    });

    $("#clock-server-slider").slider({
        min: -12,
        max: 12,
        step: 0.5,
        change: function (event, ui) {
            $('#clock-server-gmt').html(get_gmt(ui.value));
        }
    });

    $('#clock-server-add').submit(function () {
        var offset = parseInt($('#clock-server-gmt').html(), 10);
        var new_span = $(document.createElement("span"));
        var new_li = $(document.createElement("li"));
        new_span.jclock({
            format: '%H:%M',
            utc: true,
            utcOffset: offset
        });
        $(new_span).appendTo(new_li);
        new_li.append(' ' + $('#clock-server-add-label').val());
        $(new_li).appendTo('#new-clock-container');
        return false;
    });


    $('#show-ruler-checkbox').click(function () {
        if ($(this).attr('checked')) {
            $('#ruler').fadeIn();
        } else {
            $('#ruler').fadeOut();
        }
    });

    $('#ruler').draggable({
        axis: 'x'
    });

    $('#hosts a, #plugins a').live('click', load_url);

    $('#select-all').live('click', function () {
        $('.selectable').addClass('selected');
        return false;
    });

    $('#select-none').live('click', function () {
        $('.selectable').removeClass('selected');
        return false;
    });

    $("#slide-menu-container .ui-widget-header").click(function () {
        $("#slide-menu-container .ui-widget-content").slideToggle("fast");
        $(this).toggleClass("active");
        return false;
    });

    $('.icons, .fg-button').livequery(function () {
        $(this).each(function () {
            $(this).hover(function () {
                $(this).addClass('ui-state-hover');
            }, function () {
                $(this).removeClass('ui-state-hover');
            });
        });
    });

    $("#host-filter").live('keyup', function () {
        var searchText = $(this).val();
        $("#hosts li").hide();
        if (searchText === "") {
            $("#hosts li").show();
        } else {
            $("#hosts li:contains(" + searchText + ")").show();
        }

        $(this).focus();
    });

    $('#hosts a, #plugins a').live('click', function () {
        $(this).addClass("selected");
    });

    if ($('#graph-caching-checkbox').attr('checked')) {
        $(window).scroll(function () {
            lazy_check();
        });
    }

    $('#rrdeditor-submit').click(function () {
        $('#timespan-menu').data('start',$('.timespan-from').val());
        $('#timespan-menu').data('end', $('.timespan-to').val());

        var start_date = Date.parseExact($('.timespan-from').val(), "yyyy-MM-ddTHH:mm");
        var end_date   = Date.parseExact($('.timespan-to').val(),   "yyyy-MM-ddTHH:mm");

        if (!start_date || !end_date) {
            $('#error-msg').data('msg', 'One of the dates is invalid');
            $('#error-msg').dialog("open");
        } else {
            update_all_graphs(start_date, end_date);
        }

        return false;
    });

    $('#error-msg').dialog({
        modal:true,
        autoOpen:false,
        resizable:false,
        draggable:false,
        title: "An error has ocurred",
        open: function(event, ui) {
            $('#error-msg .content').html($('#error-msg').data('msg'));
        },
        buttons:{Ok: function(){$(this).dialog( "close" );}}
    });

    $('.rrdeditor-reset').click(function () {
        //FIXME need to reset values
        update_graphs();

        return false;
    });

    $('#load-graphdefs').click(
    function () {
        $.getJSON('cgi-bin/graphdefs.cgi', function (data) {
            graph_def_values = data.graph_defs;
            for (var def in graph_def_values) {
                $('#graphdef-name').append('<option value="' + def + '">' + def + '</option>');
            }
        });
    });

    $('#graphdef-name').change(function () {
        var gdef = $(this).val();
        var values = graph_def_values[gdef];
        $('#graphdef-content').val(values.join('\n'));
    });

    $('#graph-view').change(function () {
        var selected_view = $(this).val();
        if (selected_view == "grid") {
            $('#graph-imgs-container .sortable').css({
                'list-style-type': 'none'
            });
            $('#graph-container .sortable li').css({
                'float': 'left',
                'width': '200px'
            });

            $('#graph-container .sortable li img').css('width', '200px');

            $('li.gc .gc-menu').css({
                'height': '32px',
                'width': '220px'
            });
        } else {
            // selected_view == 'list'
            $('#graph-container .sortable li').css({
                'float': 'none',
                'width': '100%'
            });

            $('#graph-container .sortable li img').css('width', '');

            $('li.gc .gc-menu').css({
                'height': '32px',
                'width': '220px'
            });
        }
    });


    //action trigger when any toolbar menu option is clicked
    $('.menu-options .ui-icon').click(function() {
        hide_toolbar_items();
        $('.'+$(this).attr('id')).fadeIn();
    });

    $('#toolbar-content .ui-icon-home').click(function() {
        hide_toolbar_items();
        $('.menu-options').fadeIn();
    });

    $('.ts-item').click(function() {
        var timespan = $(this).attr('title');

        var end_date = server_now();
        var start_date = get_timespan_start(timespan);

        update_all_graphs(start_date, end_date);

        if (!$("li.graph-image").hasClass(timespan)) {
            create_graph_list(timespan, $graph_json[timespan]);
        }

        $("li.graph-image").hide();
        $("li.graph-image." + timespan).show();
        lazy_check();
    });

    ipad_position_fix();
});
