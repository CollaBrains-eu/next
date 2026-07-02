FROM debian:bookworm-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    slapd ldap-utils \
    && rm -rf /var/lib/apt/lists/*
RUN rm -rf /etc/ldap/slapd.d/* /var/lib/ldap/*
COPY slapd.conf.template /etc/ldap/slapd.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 389
ENTRYPOINT ["/entrypoint.sh"]
