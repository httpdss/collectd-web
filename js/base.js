
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

//var remove_button = '<div class="icons ui-state-default ui-corner-all"><span class="ui-icon ui-icon-close"/></div>'
var remove_button = '<span class="ui-icon ui-icon-close"/>';
/**
 * Get the id of the container for the selected element
 * 
 * @param {Object}
 *            elem
 */
function get_container(elem) {
	return $(elem).parent().parent().parent().attr('id');
}

function get_gmt(offset) {
	off = '';
	if (offset == 0) {
		off = '';
	} else if (offset > 0) {
		off = '+' + offset
	} else {
		off = offset
	}

	return offset 
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
 * check which container anchor is clicked and load the apropiate container
 * 
 * @param {Object}
 *            url
 */
var load_url = function() {
	var url = $(this).attr('href');
	var place = get_container(this) == 'hosts-container' ? '#plugins'
			: '#graph-container';
	$(place).load(url);
	$('#plugins a').each(function(){
		$(this).removeClass('selected');
	});
	if (get_container(this) == 'hosts-container') {
		$('#hosts a').each(function(){
			$(this).removeClass('selected');
		});
	}
	$(this).addClass('selected');
	return false;
}

$(document).ready(function() {
	
	$("#loading").ajaxStart(function() {
		$(this).show();
	});
	
	$("#loading").ajaxStop(function() {
		$(this).hide();
		$('.sortable').sortable();
	});
	
	//$('#hosts').load('cgi-bin/collection.modified.cgi');
	$.getJSON ('cgi-bin/collection.modified.cgi?action=hostlist_json', function(data){
		for (i = 0; i < data.length; i++) {
			$("#hosts ul").append ('<li><a href="cgi-bin/collection.modified.cgi?action=show_host;host='+data[i]+'">' + data[i] + '</a></li>');
		}
	});
	
	$('#menu-tabs').tabs();

	$(".date-field").datepicker();

	$("#clock").jclock();
	
	$('.ttip').hover(function (){
		var text = $(this).attr('rel');
		$('#help-box')
				.html(text)
				.fadeIn();
	}, function(){
		$('#help-box').html('').hide();
	});
	
	$.getJSON('cgi-bin/time.cgi', function(data){
		$("#clock-server").jclock({utc:true, utcOffset:parseInt(data.tz)});
	});
	
	$("#clock-server-slider").slider({  min: -12,
										max: 12,
										step: 0.5,
										change: function (event, ui) {
													$('#clock-server-gmt').html(get_gmt(ui.value));
												}
									});
	
	$('#clock-server-add').submit(function(){
		var offset = parseInt($('#clock-server-gmt').html());
		var new_span = $(document.createElement("span")); 
		var new_li = $(document.createElement("li")); 
		new_span.jclock({format:'%H:%M',utc:true,utcOffset:offset});
		$(new_span).appendTo(new_li);
		new_li.append(' '+$('#clock-server-add-label').val());
		$(new_li).appendTo('#new-clock-container');
		return false;
	});
	
	$('button').button();
	
	$('#show-ruler-checkbox').click(function(){
		if ($(this).attr('checked')) {
			$('#ruler').fadeIn();
		} else {
			$('#ruler').fadeOut();
		}
	});
	
	$('#ruler').draggable( { axis: 'x' } );
	
	$('#hosts a, #plugins a').live('click', load_url);

	$('#select-all').live('click', function(){
		$('.selectable').addClass('selected');
		return false;
	});
	
	$('#select-none').live('click', function(){
		$('.selectable').removeClass('selected');
		return false;
	});
	
	$('li.graph-image .ui-icon-close').live('click', function() {
		$(this).parent().parent().parent().remove();
	});
	
	$("#slide-menu-container .ui-widget-header").click(function() {
		$("#slide-menu-container .ui-widget-content").slideToggle("slow");
		$(this).toggleClass("active");
		return false;
	});
	
	$('.icons, .fg-button').livequery(function() {
		$(this).each(function() {
			$(this).hover(function() {
				$(this).addClass('ui-state-hover');
			}, function() {
				$(this).removeClass('ui-state-hover');
			});
		});
	});
	
	$("#host-filter").live('keyup', function() {
		var searchText = $(this).val();
		$("#hosts li").hide();
		if (searchText == "") {
			$("#hosts li").show();
		} else {
			$("#hosts li:contains(" + searchText + ")").show();
		}
	
		$(this).focus();
	
	});
	
	$('#hosts a, #plugins a').live('click', function() {
		$(this).addClass("selected");
	});
	
	$("#timespan-menu li").live(
			'click',
			function() {
				$("#timespan-menu li").each(function() {
					$(this).removeClass("selected");
				});
				var timespan = $(this).html();
				$("li.graph-image li").hide();
				$("li.graph-image li." + timespan).show();
				$("#timespan-menu li:contains(" + timespan + ")").addClass(
						"selected");
		});
});
