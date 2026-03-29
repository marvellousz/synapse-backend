#!/usr/bin/env bash
# Leapcell / Docker slim: prisma-client-py installs Node for the Prisma CLI; Node needs libatomic1.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends libatomic1
pip install -r requirements.txt
prisma generate
