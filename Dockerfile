FROM python:2
MAINTAINER Reimund Klain <reimund.klain@condevtec.de>

EXPOSE 5000
WORKDIR /app

RUN apt-get update && \
	apt-get upgrade -y &&  \
	apt-get install -y librrds-perl libjson-perl libhtml-parser-perl libcgi-pm-perl && \
	apt-get clean ; rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD media /app/
ADD iphone /app/
ADD cgi-bin /app/
ADD runserver.py /app/
ADD collection.conf /etc/collectd/collection.conf

CMD python runserver.py 0.0.0.0 5000