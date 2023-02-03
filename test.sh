#!/bin/bash

# Author : James Nock (@Jpnock)
# Year   : 2023

set -uo pipefail
shopt -s globstar

make bin/c_compiler

mkdir -p bin
mkdir -p bin/output

TOTAL=0
PASSING=0

J_UNIT_OUTPUT_FILE="./bin/junit_results.xml"
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' > "${J_UNIT_OUTPUT_FILE}"
printf '%s\n' '<testsuite name="Integration test">' >> "${J_UNIT_OUTPUT_FILE}"

fail_testcase() {
    echo -e "\t> ${1}"
    printf '%s\n' "<error type=\"error\" message=\"${1}\">${1}</error>" >> "${J_UNIT_OUTPUT_FILE}"
    printf '%s\n' "</testcase>" >> "${J_UNIT_OUTPUT_FILE}"
}

for DRIVER in compiler_tests/**/*_driver.c; do
    (( TOTAL++ ))

    TO_ASSEMBLE="${DRIVER%_driver.c}.c"
    LOG_PATH="${TO_ASSEMBLE//\//_}"
    LOG_PATH="./bin/output/${LOG_PATH%.c}"

    echo "${TO_ASSEMBLE}"
    printf '%s\n' "<testcase name=\"${TO_ASSEMBLE}\">" >> "${J_UNIT_OUTPUT_FILE}"

    OUT="${LOG_PATH}"
    rm -f "${OUT}.s"
    rm -f "${OUT}.o"
    rm -f "${OUT}"
    ./bin/c_compiler -S "${TO_ASSEMBLE}" -o "${OUT}.s" 2> "${LOG_PATH}.compiler.stderr.log" > "${LOG_PATH}.compiler.stdout.log"
    if [ $? -ne 0 ]; then
        fail_testcase "Fail: see ${LOG_PATH}.compiler.stderr.log and ${LOG_PATH}.compiler.stdout.log"
        continue
    fi

    riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -o "${OUT}.o" -c "${OUT}.s" 2> "${LOG_PATH}.assembler.stderr.log" > "${LOG_PATH}.assembler.stdout.log"
    if [ $? -ne 0 ]; then
        fail_testcase "Fail: see ${LOG_PATH}.assembler.stderr.log and ${LOG_PATH}.assembler.stdout.log"
        continue
    fi

    riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -static -o "${OUT}" "${OUT}.o" "${DRIVER}" 2> "${LOG_PATH}.linker.stderr.log" > "${LOG_PATH}.linker.stdout.log"
    if [ $? -ne 0 ]; then
        fail_testcase "Fail: see ${LOG_PATH}.linker.stderr.log and ${LOG_PATH}.linker.stdout.log"
        continue
    fi

    spike pk "${OUT}" > "${LOG_PATH}.simulation.log"
    if [ $? -eq 0 ]; then
        echo -e "\t> Pass"
        (( PASSING++ ))

        printf '%s\n' "</testcase>" >> "${J_UNIT_OUTPUT_FILE}"
    else
        fail_testcase "Fail: simulation did not exit with exit-code 0"
    fi
done

printf "\nPassing %d/%d tests\n" "${PASSING}" "${TOTAL}"
printf '%s\n' '</testsuite>' >> "${J_UNIT_OUTPUT_FILE}"
