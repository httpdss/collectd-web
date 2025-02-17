/*
 * jStore HTML5 Specification Storage Engine
 * Copyright (c) 2009 Eric Garside (http://eric.garside.name)
 */
(function(b){var a=b.jStore.Availability.html5=function(){return !!window.openDatabase};this.jStoreHtml5=StorageEngine.extend({init:function(d,c){this._super(d,c);this.type="HTML5";this.limit=1024*200},connect:function(){var c=this.db=openDatabase("jstore-"+this.project,"1.0",this.project,this.limit);if(!c){throw"JSTORE_ENGINE_HTML5_NODB"}c.transaction(function(d){d.executeSql("CREATE TABLE IF NOT EXISTS jstore (k TEXT UNIQUE NOT NULL PRIMARY KEY, v TEXT NOT NULL)")});this.updateCache()},updateCache:function(){var c=this;this.db.transaction(function(d){d.executeSql("SELECT k,v FROM jstore",[],function(f,e){var h=e.rows,g=0,j;for(;g<h.length;++g){j=h.item(g);c.data[j.k]=b.jStore.safeResurrect(j.v)}c.delegate.trigger("engine-ready")})})},isAvailable:a,set:function(c,d){this.interruptAccess();this.db.transaction(function(e){e.executeSql("INSERT OR REPLACE INTO jstore(k, v) VALUES (?, ?)",[c,b.jStore.safeStore(d)])});return this._super(c,d)},rem:function(c){this.interruptAccess();this.db.transaction(function(d){d.executeSql("DELETE FROM jstore WHERE k = ?",[c])});return this._super(c)}});b.jStore.Engines.html5=jStoreHtml5;b.jStore.EngineOrder[0]="html5"})(jQuery);
