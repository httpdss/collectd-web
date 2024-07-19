# 📊 Collectd-web

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)

The main objective of this project is to develop an easy-to-use and customizable web interface for Collectd (Resource monitoring software). After two days of research, it was clear that Collectd lacked a real frontend. The one bundled with the backend was primarily made for testing purposes, leaving much of the usability and strength of statistics aside.

## 🚀 Features

- User-friendly and customizable web interface for Collectd
- Easy installation and setup
- Standalone web server for quick deployment

## 🛠 Installation

### Prerequisites

You must have a path containing each host's files in a separate sub-directory, named according to the host.

For example:

```sh
/etc/collectd/collectd-web/localhost/
```

In this case, your `datadir` will be `/etc/collectd/collectd-web/`. Create `/etc/collectd/collection.conf` with the content:

```sh
datadir: "/etc/collectd/collectd-web/"
```

### For Debian-based Linux Distributions

Install the following dependencies:

```bash
apt-get install librrds-perl libjson-perl libhtml-parser-perl
```

## 🌐 Using the Webserver

Give Collectd-web a try! Execute the standalone web server and you are done:

```bash
python runserver.py
```

## 🔗 Links

- [Collectd-web Homepage](http://github.com/httpdss/collectd-web)

## 📄 License

Collectd-web is licensed under Apache 2.0. Please see the [LICENSE](LICENSE) file for more information.

## 📝 Contributing

We welcome contributions! Please see the [CONTRIBUTING.md](.github/CONTRIBUTING.md) file for more information on how to get involved.
