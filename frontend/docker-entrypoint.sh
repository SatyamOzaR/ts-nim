#!/bin/sh
set -e
# Docker/K8s set HOSTNAME to the container id. Next.js standalone uses it for the HTTP
# bind address — must be 0.0.0.0 or Railway's proxy gets nothing (502).
export HOSTNAME="0.0.0.0"
exec node server.js
