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
	
	$('#hosts').load('/cgi-bin/collection.modified.cgi');
	
	$('#menu-tabs').tabs();

	$(".date-field").datepicker();

	$("#clock").jclock();
	
	$("#clock-server").jclock();
	$("#clock-server-slider").slider();
	
	$('button').button();
	
	$('#hosts a, #plugins a').live('click', load_url);
	
	$('li.graph-image .ui-icon-close').live('click', function() {
		$(this).parent().parent().remove();
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
		var searchText = $(this).attr('text');
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