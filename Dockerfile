FROM debian:10

ENV LANG=C.UTF-8
ENV TZ=Europe/Minsk
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN DEBIAN_FRONTEND=noninteractive apt-get update &&  apt-get install --yes --no-install-recommends librrds-perl libjson-perl libhtml-parser-perl libcgi-pm-perl perl-modules-5.28 python3-minimal python3-httpbin
RUN mkdir  /etc/collectd
ADD ./docker/collection.conf /etc/collectd/collection.conf
#RUN git clone --depth 1 https://github.com/m-pavel/collectd-web.git /usr/local/collectd/
COPY . /usr/local/collectd/

WORKDIR /usr/local/collectd/

EXPOSE 80
CMD ["./runserver.py", "0.0.0.0", "80"]

