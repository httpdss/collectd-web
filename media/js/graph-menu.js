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


function get_url_params(url) {
	var params = {};
	url = url.replace(/.*\?(.*?)/,"$1");
	variables = url.split (";");
	for (i = 0; i < variables.length; i++) {
		separ = variables[i].split("=");
		params[separ[0]] = separ[1];
	}
	return params;
}

/**
 * Build up and url with the given parameters
 * @param original_url string with the original url
 * @param params hash with all parameters to add to the url
 * @return string
 */
function build_url(original_url, params) {
	
}

/**
 * Function to make the graph move on the x axis
 * @param menu_element the button of the menu pressed
 * @param seconds number of seconds to move. positive values move
 * the graph to the right and negative values to the left
 * @return
 */
function move_graph(menu_element, seconds) {
	var gc_img = $(menu_element).parent().parent().parent().find('.gc-img');
	var url = $(gc_img).attr('src');
	var params = get_url_params(url);
	var start = 0;
	var end = 0;
	
	if (params.start != null) { start = params.start; }
	if (params.end != null) { end = params.end; }
	
	start = start + seconds;
	end = end + seconds;
	
	$(gc_img).attr('src', build_url())
}


$(function() {

	$('li.graph-image .ui-icon-triangle-1-w').live('click', function() {
		move_graph(this, 5);
	});

	$('li.graph-image .ui-icon-triangle-1-e').live('click', function() {
		move_graph(this, -5);
	});
	
	$('li.graph-image .ui-icon-zoomin').live('click', function() {
		alert('Under construction');
	});

	$('li.graph-image .ui-icon-zoomout').live('click', function() {
		alert('Under construction');
	});

	$('li.graph-image .ui-icon-close').live('click', function() {
		$(this).parent().parent().parent().remove();
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
});