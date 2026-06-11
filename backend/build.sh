#!/usr/bin/env bash
# Render custom build command (Root Directory = backend):
#   bash build.sh
set -euo pipefail
pip install --upgrade pip
pip install --default-timeout=120 --retries 5 -r requirements.txt
