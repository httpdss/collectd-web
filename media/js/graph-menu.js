// Collectd-web - graph-menu.js
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


function print_date(in_date) {
    var out_date = in_date.toString("HH:mm MMM d yyyy");
    return out_date;
}

function get_milliseconds (in_date) {
    var out_date = new Date.UTC(in_date.getFullYear(),
            in_date.getMonth(),
            in_date.getDay(),
            in_date.getHours(),
            in_date.getMinutes(),
            in_date.getSeconds(),
            in_date.getMilliseconds());
    return out_date;
}
function get_exact_date (in_date) {
    var out_date = Date.parseExact(unescape(in_date), "HH:mm MMM d yyyy");
    return out_date;
}

function get_date_distance (in_start, in_end) {
   var start_millis = get_milliseconds(in_start);
   var end_millis = get_milliseconds(in_end);
   var millis = end_millis - start_millis;
   return millis;
}

/**
 * Function to make the graph move on the x axis
 * @param menu_element the button of the menu pressed
 * @param 
 * the graph to the right and negative values to the left
 * @return
 */
function move_graph(menu_element, direction) {
	var gc_img = $(menu_element).closest('li.gc').find('.gc-img');
	var url = $(gc_img).attr('src');
	var params = get_url_params(url);

    var end = Date.parse("now");
    var start = Date.parse("now").add(-1).hours();

	if (params.start != null) { start = get_exact_date(params.start); }
    if (params.end != null) { end = get_exact_date(params.end); }

    var date_distance = Math.round(get_date_distance(start, end) / 2);

    if (direction) { 
        start.add((-1)*date_distance).milliseconds();
        end.add((-1)*date_distance).milliseconds();
    } else {
        start.add(date_distance).milliseconds();
        end.add(date_distance).milliseconds();
    }

    $(gc_img).attr('src', build_url(url, {'start':print_date(start), 
                                          'end':print_date(end)
                                         }));
}

function zoom_graph(menu_element, direction) {
	var gc_img = $(menu_element).closest('li.gc').find('.gc-img');
	var url = $(gc_img).attr('src');
	var params = get_url_params(url);

    var zoom_factor = 0.5;

    var end = Date.parse("now");
    var start = Date.parse("now").add(-1).hours();

	if (params.start != null) { start = get_exact_date(params.start); }
    if (params.end != null) { end = get_exact_date(params.end); }

    var date_distance = Math.round(get_date_distance(start, end) * zoom_factor);

    if (direction) { 
        start.add((-1)*date_distance).milliseconds();
    } else {
        start.add(date_distance).milliseconds();
    }

    $(gc_img).attr('src', build_url(url, {'start':print_date(start), 
                                          'end':print_date(end)
                                         }));
}


$(function() {

	$('li.graph-image .ui-icon-triangle-1-w').live('click', function() {
		move_graph(this, true);
	});

	$('li.graph-image .ui-icon-triangle-1-e').live('click', function() {
		move_graph(this, false);
	});
	
	$('li.graph-image .ui-icon-zoomin').live('click', function() {
		zoom_graph(this, false);
	});

	$('li.graph-image .ui-icon-zoomout').live('click', function() {
		zoom_graph(this, true);
	});

	$('li.graph-image .ui-icon-close').live('click', function() {
		$(this).closest('li.gc').remove();
	});

	$('li.graph-image .ui-icon-star').live('click', function() {
		var section = $(this).parent().parent().next();
		if ($(section).hasClass('selected')) {
			$(section).removeClass('selected');
		} else {
			$(section).addClass('selected');
		}
	});

	$('li.graph-image .ui-icon-disk').live('click', function() {
		var img_tag = $(this).parent().parent().next().next();
		$("#output-dialog a").each(function() {
			$this = $(this);
			var join_url = $(img_tag).attr('src') + $this.attr('href');
			$this.attr('href', join_url);
		});
		$("#output-dialog").dialog( {
			title : 'Select output format:',
			modal : true
		});
	});
   //$("#toolbar-container").jixedbar(); 
});
