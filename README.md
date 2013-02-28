This is a fork of [collectd-web](https://github.com/httpdss/collectd-web) intended mainly for personal use.

The main need for this fork started when I wanted to add support for fpm-status graphs.
Also I deleted some files I do not need.

Copyright of course remains the same. Check `COPYING` and `AUTHORS` for more information.


### Apache Configuration ##

Add these lines to your apache vhost configuration:

```apache
    Alias /collectd-web/collectd-web /path/to/vhost/httdocs/collectd-web
    <Directory /path/to/vhost/httdocs/collectd-web/cgi-bin>
      Options +ExecCGI +FollowSymLinks
      AddHandler cgi-script .cgi .pl
    </Directory>
```

