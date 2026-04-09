# Dockerfile for the collectd-web Python devcontainer
# Perl CGI packages removed - backend ported to Python (see collectd_web/)
FROM mcr.microsoft.com/devcontainers/python:3

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    collectd \
    rrdtool \
    librrd-dev \
    fonts-recommended \
    dpkg-dev \
    debhelper \
    devscripts \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
