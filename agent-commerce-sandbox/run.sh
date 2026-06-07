#!/usr/bin/env bash
# Wrapper to run agent-commerce-sandbox with web3 available
cd "$(dirname "$0")"
PYTHONPATH="/usr/lib/python3/dist-packages:/home/ubuntu/.local/lib/python3.12/site-packages:$PYTHONPATH" \
  python3 "$@"
