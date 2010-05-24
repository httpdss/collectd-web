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
 * return html structure for the available plugins menu
 * @param host
 * @param plugins
 * @return
 */
function create_plugin_menu(host, plugins) {
    var tpl = '<div><div class="ui-widget-header ui-corner-top"><h3>Available Plugins</h3></div>';
    tpl += '<div id="plugin-container" class="ui-widget-content ui-corner-bottom  "><ul>';
    for ( var p = 0; p < plugins.length; p++) {
        tpl += '<li><a href="cgi-bin/collection.modified.cgi?action=show_plugin;host='+host+';timespan=day;plugin='+plugins[p]+'">'+plugins[p]+'</a></li>';
    }
    tpl += '</ul></div>';
    tpl += '</div>';
    return tpl;
}

function get_graph_menu() {
	return $('#graph-menu-partial').html();
}

function get_graph_main_container(host) {
	$('.graph-main-container .hostname').html(host)
	return $('.graph-main-container').html()
}

function show_lazy_graph(elem){
	$(elem).attr('src',$(elem).attr('title'))
}

function create_graph_list(timespan, graphs) {
    var $tpl = '';
    $tpl += '<li class="ui-widget graph-image '+timespan+'">';
    $tpl += '<ul class="sortable ui-sortable">';
    for ( var g = 0; g < graphs.length; g++) {
        $tpl += '<li class="gc">';
        $tpl += get_graph_menu();
        if ($('#graph-caching-checkbox').attr('checked')) {
            $tpl += '<img class="gc-img toload" src="media/images/graph-load.png" title="' + graphs[g] + '"/></li>';
        } else {
            $tpl += '<img class="gc-img" src="' + graphs[g] + '"/></li>';
        }
        $tpl += '</li>';
    }
    $tpl += '</ul>';
    $tpl += '</li>';
    $('.graph-imgs-container').append($tpl);
}

function lazy_check() {
    if ($('#graph-caching-checkbox').attr('checked')) {
        $('.toload.gc-img').each(function() {
                window_top = $(window).height() + $(window).scrollTop();
                var elem_top = $(this).offset().top;
                console.info(elem_top);
                if((window_top > elem_top) && (elem_top != 0)) {
                    show_lazy_graph(this);
                    $(this).removeClass('toload')
                    console.info($(this).attr('src'));
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
var load_url = function() {
	var url = $(this).attr('href');
	var place = '#plugins';
	if (get_container(this) == 'hosts-container') {
		$('#hosts a').each(function() {
			$(this).removeClass('selected');
		});
		$selected_host = $(this).html();
		$.getJSON('cgi-bin/collection.modified.cgi?action=pluginlist_json&host=' + $selected_host, function(data){
			$("#plugins").html('');
            $("#plugins").append(create_plugin_menu($selected_host, data));
            
            $('#plugins ul li a').click(function(){
                $('#plugins').data('selected_plugin', $(this).attr('rel'));
            });
        });
	} else {
		$selected_plugin = $(this).html();
		$(".graph-imgs-container").html('');
		$.getJSON('cgi-bin/collection.modified.cgi?action=graphs_json;plugin=' + $selected_plugin + ';host=' + $selected_host, 
				function(data){
					$graph_json = data
					create_graph_list("hour", data.hour);
					$('#graph-container').html(get_graph_main_container($selected_host));
					lazy_check();
				});	
	}
	
	
	$('#plugins a').each(function() {
		$(this).removeClass('selected');
	});

	$(this).addClass('selected');

	return false;
}

$(document).ready(function() {
	
	$.ajaxSetup({cache:true});

	$("#loading").ajaxStart(function() {
		$(this).show();
	});

	$("#loading").ajaxStop(function() {
		$(this).hide();
		$('.sortable').sortable();
		$('#graph-view').trigger('change');
	});
	
		$.getJSON('cgi-bin/collection.modified.cgi?action=hostlist_json',
				function(data) {
					for (i = 0; i < data.length; i++) {
						$("#hosts ul").append(
								'<li><a href="cgi-bin/collection.modified.cgi?action=show_host;host='
										+ data[i] + '">' + data[i]
										+ '</a></li>');
					}
				});

		$('#menu-tabs').tabs();

		$(".date-field").datepicker();

		$("#clock").jclock();

		$('.ttip').hover(function() {
			var text = $(this).find('div.ttip-content').html();
			$('#help-box').html(text).fadeIn();
		}, function() {
			$('#help-box').html('').hide();
		});

		$.getJSON('cgi-bin/time.cgi', function(data) {
			$("#clock-server").jclock( {
				utc : true,
				utcOffset : parseInt(data.tz)
			});
		});

		$("#clock-server-slider").slider( {
			min : -12,
			max : 12,
			step : 0.5,
			change : function(event, ui) {
				$('#clock-server-gmt').html(get_gmt(ui.value));
			}
		});

		$('#clock-server-add').submit(function() {
			var offset = parseInt($('#clock-server-gmt').html());
			var new_span = $(document.createElement("span"));
			var new_li = $(document.createElement("li"));
			new_span.jclock( {
				format : '%H:%M',
				utc : true,
				utcOffset : offset
			});
			$(new_span).appendTo(new_li);
			new_li.append(' ' + $('#clock-server-add-label').val());
			$(new_li).appendTo('#new-clock-container');
			return false;
		});

		$('button').button();

		$('#show-ruler-checkbox').click(function() {
			if ($(this).attr('checked')) {
				$('#ruler').fadeIn();
			} else {
				$('#ruler').fadeOut();
			}
		});

		$('#ruler').draggable( {
			axis : 'x'
		});

		$('#hosts a, #plugins a').live('click', load_url);

		$('#select-all').live('click', function() {
			$('.selectable').addClass('selected');
			return false;
		});

		$('#select-none').live('click', function() {
			$('.selectable').removeClass('selected');
			return false;
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

		$("#slide-menu-container .ui-widget-header").click(function() {
			$("#slide-menu-container .ui-widget-content").slideToggle("fast");
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
		
		if ($('#graph-caching-checkbox').attr('checked')) {
		
			$(window).scroll(function () {
				lazy_check();
	        });
		}

		$("#timespan-menu li").live(
				'click',
				function() {
					$("#timespan-menu li").each(function() {
						$(this).removeClass("selected");
					});
					var timespan = $(this).html();
					if (!$("li.graph-image").hasClass(timespan)) {
						create_graph_list(timespan, $graph_json[timespan]);
					}
					$("li.graph-image").hide();
					$("li.graph-image." + timespan).show();
					$("#timespan-menu li:contains(" + timespan + ")").addClass("selected");
					lazy_check();
				});
		$('#load-graphdefs').click(
				function() {
					$.getJSON('cgi-bin/graphdefs.cgi', function(data) {
						graph_def_values = data.graph_defs
						for ( var def in graph_def_values) {
							$('#graphdef-name').append(
									'<option value="' + def + '">' + def
											+ '</option>');
						}
					});
				});

		$('#graphdef-name').change(function() {
			var gdef = $(this).val();
			var values = graph_def_values[gdef];
			$('#graphdef-content').val(values.join('\n'));
		});
		$('#graph-view').change(function() {
			var selected_view = $(this).val();
			if (selected_view == "grid") {
				$('#graph-imgs-container .sortable').css( {
					'list-style-type' : 'none'
				});
				$('#graph-container .sortable li').css( {
					'float' : 'left',
					'width' : '200px'
				});

				$('#graph-container .sortable li img').css('width', '200px');

				$('li.gc .gc-menu').css( {
					'height' : '60px',
					'width' : '120px'
				});
			} else {
				// selected_view == 'list'
				$('#graph-container .sortable li').css( {
					'float' : 'none',
					'width' : '100%'
				});

				$('#graph-container .sortable li img').css('width', '');

				$('li.gc .gc-menu').css( {
					'height' : '120px',
					'width' : '60px'
				});
			}
		});
	});
