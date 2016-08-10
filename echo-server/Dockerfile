FROM ubuntu:latest

MAINTAINER Andrew Pope <andrew@pope.nz>

RUN apt-get update && apt-get install -y python3 \
 && rm -rf /var/lib/apt/lists/*

COPY bin/echo-server.py /usr/local/bin/

EXPOSE 7

CMD python3 /usr/local/bin/echo-server.py
