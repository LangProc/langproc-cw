#!/bin/bash

# If Python does not work, run scripts/ to test

if ! command -v python3 &> /dev/null; then
    echo "Python is not installed. Installing Python..."
    sudo apt-get update
    sudo apt-get install python3 -y
fi

. scripts/test.py