#!/bin/bash
# Run it in the terminal with the logs visible (for debugging).
cd "$(dirname "$0")"
PYTHONPATH=. exec ./.venv/bin/python -m claudevoice.app
