#!/bin/bash

# Author : James Nock (@Jpnock)
# Year   : 2023

set -euo pipefail

make bin/c_compiler
rm -f bin/riscv_example.s
./bin/c_compiler -S "compiler_tests/_example/example.c" -o "bin/riscv_example.s"
riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -o "bin/riscv_example" "bin/riscv_example.s" "compiler_tests/_example/example_driver.c"

set +e
spike pk "bin/riscv_example"
if [ $? -eq 0 ]; then
    echo "Test successful"
else
    echo "The simulator did not run correctly :("
fi
set -e

rm -f bin/riscv_example
