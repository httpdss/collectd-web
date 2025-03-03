# Dockerfile for the python devcontainer
FROM mcr.microsoft.com/devcontainers/python:3

# Install collectd
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    collectd \
    librrds-perl \
    libjson-perl \
    libhtml-parser-perl \
    libcgi-pm-perl \
    libipc-run-perl \
    fonts-recommended \
    python3-dotenv \
    dpkg-dev \
    debhelper \
    devscripts \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
