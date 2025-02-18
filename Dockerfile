# from debian
FROM debian:stable-slim

# Install collectd
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    collectd \
    librrds-perl \
    libjson-perl \
    libhtml-parser-perl \
    libcgi-pm-perl \
    libipc-run-perl \
    nginx

RUN mkdir -p /app

WORKDIR /app

# Copy collectd config
COPY config/collectd.conf /etc/collectd/collectd.conf

# Copy folders
COPY cgi-bin /app/cgi-bin
COPY iphone /app/iphone
COPY media /app/media

# Copy nginx config for collectd-web
COPY config/collectd-web.nginx.conf /etc/nginx/sites-enabled/collectd-web.nginx.conf
COPY config/collectd.conf /etc/collectd/collectd.conf
