/**
 * jStore IE Storage Engine
 * Copyright (c) 2009 Eric Garside (http://eric.garside.name)
 */
(function(b){var a=b.jStore.Availability.ie=function(){return !!window.ActiveXObject};this.jStoreIE=StorageEngine.extend({init:function(d,c){this._super(d,c);this.type="IE";this.limit=64*1024},connect:function(){this.db=b('<div style="display:none;behavior:url(\'#default#userData\')" id="jstore-'+this.project+'"></div>').appendTo(document.body).get(0);this.delegate.trigger("engine-ready")},isAvailable:a,get:function(c){this.interruptAccess();this.db.load(this.project);return b.jStore.safeResurrect(this.db.getAttribute(c))},set:function(c,d){this.interruptAccess();this.db.setAttribute(c,b.jStore.safeStore(d));this.db.save(this.project);return d},rem:function(c){this.interruptAccess();var d=this.get(c);this.db.removeAttribute(c);this.db.save(this.project);return d}});b.jStore.Engines.ie=jStoreIE;b.jStore.EngineOrder[4]="ie"})(jQuery);
