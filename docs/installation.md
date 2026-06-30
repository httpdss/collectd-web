# Installation, Deployment, and Troubleshooting

This guide covers the most common collectd-web deployment paths:

- Debian/Ubuntu package install
- Standalone server usage
- Nginx reverse proxy
- Apache CGI setup
- Common startup, graph, and permissions issues

## Prerequisites

collectd-web expects:

- collectd to be generating RRD data
- a host-specific data directory layout
- Python 3 with `python3-dotenv` available for the standalone server

The standalone server listens on `127.0.0.1:8888` by default. You can override that with the `HOST` and `PORT` environment variables or by passing arguments to `runserver.py`.

## Debian / Ubuntu package install

If you have a built `.deb` package, install it with:

```bash
sudo dpkg -i collectd-web_*.deb
sudo apt-get -f install
```

The Debian package installs files under:

- `/usr/share/collectd-web/`
- `/usr/share/collectd-web/runserver.py`
- `/usr/share/collectd-web/cgi-bin/`

The packaged service runs the standalone server from `/usr/share/collectd-web/runserver.py`.

To start it after installation:

```bash
sudo service collectd-web start
```

If you use systemd directly, the service file is configured to execute:

```bash
/usr/bin/python3 /usr/share/collectd-web/runserver.py
```

## Standalone server

For local testing or a non-packaged install, run:

```bash
python3 runserver.py
```

You can also bind explicitly:

```bash
python3 runserver.py 127.0.0.1 8888
```

Or override via environment:

```bash
HOST=0.0.0.0 PORT=8888 python3 runserver.py
```

The default URL is:

```text
http://127.0.0.1:8888/
```

## Data directory layout

collectd-web expects per-host data directories. A common layout is:

```text
/etc/collectd/collectd-web/
└── localhost/
```

Your configuration should point `datadir` at the parent directory:

```text
datadir: "/etc/collectd/collectd-web/"
```

If your collectd RRD files live elsewhere, update `datadir` to match that path.

## Nginx reverse proxy

The package includes a sample Nginx config at `debian/collectd-web.nginx.conf`:

```nginx
server {
    listen 80;
    server_name localhost;

    root /usr/share/collectd-web/;
    autoindex off;

    location ~ \.cgi$ {
        fastcgi_pass unix:/var/run/fcgiwrap.socket;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }
}
```

Typical assumptions:

- `fcgiwrap` is installed and running
- the web root is `/usr/share/collectd-web/`
- the CGI scripts under `cgi-bin/` are executable

If graphs do not render, confirm that Nginx can reach the FastCGI socket and that the CGI script path resolves correctly.

## Apache setup

For Apache, enable CGI execution for the collectd-web directory and allow the CGI scripts to run:

```apache
Alias /collectd-web/ /path/to/collectd-web/

<Directory /path/to/collectd-web/cgi-bin>
  Options +ExecCGI +FollowSymLinks
  AddHandler cgi-script .cgi .pl
</Directory>
```

Adjust `/path/to/collectd-web/` to match where the files are installed on your system.

## Troubleshooting

### Missing graphs

- Confirm the `datadir` points to the directory that contains your host RRD files.
- Check that collectd is writing data for the selected host.
- Verify the user running collectd-web can read the RRD files.

### Permissions problems

- Make sure the web server or standalone process can read the `datadir` tree.
- Check the ownership and mode on the RRD directories.
- If you are using a package install, confirm the service runs as the expected user.

### Missing dependencies

- For the Debian package, run `sudo apt-get -f install` after `dpkg -i`.
- For standalone usage, install `python3-dotenv` and any Python modules required by your environment.
- For CGI deployments, make sure `fcgiwrap`, Nginx, or Apache CGI support is installed and enabled.

### Service startup issues

- Inspect the service logs with `journalctl -u collectd-web`.
- Confirm that `/usr/share/collectd-web/runserver.py` exists after package install.
- Verify `HOST` and `PORT` are valid and not already in use.

