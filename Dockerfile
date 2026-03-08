# syntax=docker/dockerfile:1
FROM postgres:18

# Install build dependencies and git
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        postgresql-server-dev-18 \
        ca-certificates \
        libreadline-dev \
        zlib1g-dev \
        flex \
        bison \
    && rm -rf /var/lib/apt/lists/*

# Install pgvector
RUN git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make && make install \
    && cd / && rm -rf /tmp/pgvector

# Install Apache AGE (latest stable)
RUN git clone --branch PG18 https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && make PG_CONFIG=/usr/lib/postgresql/18/bin/pg_config && make install PG_CONFIG=/usr/lib/postgresql/18/bin/pg_config \
    && cd / && rm -rf /tmp/age

# Enable extensions on init
COPY init-mindstate.sql /docker-entrypoint-initdb.d/
