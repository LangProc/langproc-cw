#!/bin/bash

if ! python3 --version > /dev/null 2>&1; then
    . scripts/test.sh
else
    ./scripts/test.py $@
fi
