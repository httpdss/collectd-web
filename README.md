# Collectd-web: A User-Friendly Interface for Collectd

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)

Collectd-web provides a sleek, intuitive, and customizable web interface for Collectd – the robust resource monitoring tool. Originally, Collectd’s bundled frontend was designed only for testing, leaving its full potential untapped. Collectd-web bridges that gap by offering an efficient, user-centered experience for monitoring system statistics.

## 📊 Table of Contents

- [🚀 Features](#-features)
- [🛠 Installation](#-installation)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Debian-based Installation](#debian-based-installation)
- [🌐 Usage](#-usage)
- [🔗 Links](#-links)
- [📄 License](#-license)
- [💰 Funding](#-funding)
- [📝 Contributing](#-contributing)

## 🚀 Features

- **Intuitive Dashboard:** Easily visualize system statistics with a responsive design.
- **Customizable Interface:** Adjust the display to highlight the data that matters to you.
- **Quick Deployment:** Launch the built-in, standalone web server with minimal setup.
- **Efficient Monitoring:** Optimized for performance and usability in monitoring diverse systems.

![Collectd-web UI](docs/ui.png)

## 🛠 Installation

### Prerequisites

Before installing Collectd-web, please ensure:

- **Directory Structure:**
  Organize your files so that each host’s data resides in its own sub-directory named after the host. For example:

  ```sh
  /etc/collectd/collectd-web/localhost/
  ```

- **Python 3.6+ Requirement:**
  The standalone web server requires Python version 3.6 or higher.

### Configuration

After setting up your directories, create a configuration file to define your data directory. For example, create `/etc/collectd/collection.conf` with the following content:

```sh
datadir: "/etc/collectd/collectd-web/"
```

### Debian-based Installation

If you are using a Debian-based distribution, install the necessary dependencies:

```bash
sudo apt update
sudo apt install librrds-perl libjson-perl libhtml-parser-perl libcgi-pm-perl fonts-recommended python3-dotenv
```

## 🌐 Usage

To start the Collectd-web standalone server, simply run:

```bash
python runserver.py
```

### Apache Configuration

Add these lines to your apache vhost configuration:

```apache
    Alias /collectd-web/collectd-web /path/to/vhost/httdocs/collectd-web
    <Directory /path/to/vhost/httdocs/collectd-web/cgi-bin>
      Options +ExecCGI +FollowSymLinks
      AddHandler cgi-script .cgi .pl
    </Directory>
```

Once running, open your web browser and navigate to the provided address (typically `http://localhost:8888`) to begin monitoring your systems.

## 🔗 Links

- **Project Homepage:** [Collectd-web on GitHub](http://github.com/httpdss/collectd-web)
- **Code of Conduct:** Please review our [Code of Conduct](code_of_conduct.md) for community guidelines.

## 📄 License

Collectd-web is licensed under the [Apache 2.0 License](LICENSE). For full license details, please refer to the LICENSE file.

## 💰 Funding

If you find Collectd-web useful, please consider supporting its development. Donations can be made via [PayPal](https://www.paypal.me/httpdss). Your support is greatly appreciated!

## 📝 Contributing

We welcome contributions from the community. For details on how to get involved, please see our [CONTRIBUTING.md](.github/CONTRIBUTING.md).
