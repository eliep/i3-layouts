#!/usr/bin/env bash

flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

xvfb-run --auto-servernum --server-num=2 --server-args="-screen 0 1280x800x24" ./test/test.sh