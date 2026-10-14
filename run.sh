#!/bin/bash
# Terminalde loglari gorerek calistirmak icin (hata ayiklama).
cd "$(dirname "$0")"
PYTHONPATH=. exec ./.venv/bin/python -m claudevoice.app
