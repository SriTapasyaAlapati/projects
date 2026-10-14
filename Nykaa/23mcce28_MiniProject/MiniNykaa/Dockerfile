# MiniNykaa - shared Dockerfile for every service.
#
# The image is the same for all ten containers (catalog x3, order x3, gateway x2, lb,
# web); only the startup command differs, and that is
# set per-service by docker-compose.yml's "command:". This mirrors how the
# same application image is often reused across a microservices fleet, with
# orchestration deciding each container's role.
#
# The app has zero third-party dependencies (standard library only), so the
# image just needs a Python runtime and the source tree.

FROM python:3.12-slim

WORKDIR /app

# No requirements.txt on purpose - MiniNykaa intentionally uses only
# Python's standard library (socket, threading, json, struct, hashlib,
# http.server, uuid) so there is nothing to pip install.
COPY . .

# Every node's default port lives in common/config.py; EXPOSE here is
# documentation for `docker ps` / `docker inspect`, not an actual limit -
# docker-compose publishes the ones that matter (the website).
EXPOSE 5000 5101 5102 6001 6002 6003 7001 7002 7003 8080 8081

# No ENTRYPOINT/CMD: each service in docker-compose.yml supplies its own
# `command:` (e.g. ["python", "catalog_service/catalog_server.py", "catalog-1"]).
