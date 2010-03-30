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
	
	$("#clock-server").jclock();
	$("#clock-server-slider").slider();
	
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
