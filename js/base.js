var remove_button = '<div class="icons ui-state-default ui-corner-all"><span class="ui-icon ui-icon-close"/></div>'

$(document).ready(function() {  
        $.AjaxifyDefaults.loading_target = '#loader';

        $('#hosts a').livequery( function(){
            $(this).ajaxify({
                    target:'#plugins',
                });
            });

        $('#plugins a').livequery( function(){
            $(this).ajaxify({
                    target:'#graph-container',
                    animateOut:{opacity:'0'},
                    animateOutSpeed:300,
                    animateIn:{opacity:'1'},
                    animateInSpeed:300,
                });
            });
        $('#hosts').load('/cgi-bin/collection.modified.cgi');

        $('li.graph-image').livequery(function(){
            $(this).each(function(){
                    $(this).prepend(remove_button);
                    $('li.graph-image .ui-icon-close').click(function (){ 
                        $(this).parent().parent().remove();
                    });
                });
            });

        $('.icons').livequery(function(){
            $(this).each(function(){
                $(this).hover(
                        function() { $(this).addClass('ui-state-hover'); },
                        function() { $(this).removeClass('ui-state-hover'); }
                );
            });
        });

        $('.sortable').livequery(function(){
            $(this).each(function(){
                $(this).sortable();
            });
        });


        $('#hosts li, #plugins li').livequery(function(){
            $(this).click(function (){
                    $(this).addClass("selected");
            });
        });
$("#host-filter").livequery(function(){
        $(this).keyup(function () {
            var searchText = $(this).val();
            $("#hosts li").hide();
            $("#hosts li:contains("+searchText+")").show();
        });
});

}); 
