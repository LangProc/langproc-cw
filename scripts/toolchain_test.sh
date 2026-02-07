#!/bin/bash

# Author : James Nock (@Jpnock)
# Year   : 2023

set -euo pipefail

make build/c_compiler
rm -f build/riscv_example.s
./build/c_compiler -S "tests/_example/example.c" -o "build/riscv_example.s"
riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -o "build/riscv_example" "build/riscv_example.s" "tests/_example/example_driver.c"

set +e
spike pk "build/riscv_example"
if [ $? -eq 0 ]; then
    echo "Test successful"
else
    echo "The simulator did not run correctly :("
fi
set -e

rm -f build/riscv_example
