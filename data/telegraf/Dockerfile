FROM telegraf:1.35-alpine

USER root
RUN apk add --no-cache bash curl ca-certificates util-linux

COPY data/telegraf/telegraf.conf /etc/telegraf/telegraf.conf
COPY data/probes /probes
RUN chmod +x /probes/*.sh \
  && chown -R telegraf:telegraf /etc/telegraf/telegraf.conf /probes

USER telegraf
