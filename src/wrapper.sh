#!/bin/bash
echo "Compiling to RISC-V..."
cat $2 | ./bin/compiler 2> /dev/null 1> $4
