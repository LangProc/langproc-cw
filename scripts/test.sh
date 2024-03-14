#!/bin/bash

# Author : James Nock (@Jpnock)
# Year   : 2023

set -uo pipefail
shopt -s globstar

if [ "${DONT_CLEAN:-}" != "1" ]; then
    make clean
fi

set -e
make bin/c_compiler
set +e

mkdir -p bin
mkdir -p bin/output

TOTAL=0
PASSING=0

J_UNIT_OUTPUT_FILE="./bin/junit_results.xml"
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' > "${J_UNIT_OUTPUT_FILE}"
printf '%s\n' '<testsuite name="Integration test">' >> "${J_UNIT_OUTPUT_FILE}"

fail_testcase() {
    echo -e "\t> ${1}"
    printf '\n'

    printf '%s\n' "<error type=\"error\" message=\"${1}\">${1}</error>" >> "${J_UNIT_OUTPUT_FILE}"
    printf '%s\n' "</testcase>" >> "${J_UNIT_OUTPUT_FILE}"
}

SPECIFIC_FOLDER="${1:-**}"

for DRIVER in compiler_tests/${SPECIFIC_FOLDER}/*_driver.c; do
    (( TOTAL++ ))

    TO_ASSEMBLE="${DRIVER%_driver.c}.c"
    LOG_PATH="${TO_ASSEMBLE#compiler_tests/}"
    LOG_PATH="./bin/output/${LOG_PATH%.c}"
    BASE_NAME="$(basename "${LOG_PATH}")"
    LOG_FILE_BASE="${LOG_PATH}/${BASE_NAME}"
    rm -rf "${LOG_PATH}"
    mkdir -p "${LOG_PATH}"

    echo "${TO_ASSEMBLE}"
    printf '%s\n' "<testcase name=\"${TO_ASSEMBLE}\">" >> "${J_UNIT_OUTPUT_FILE}"

    OUT="${LOG_FILE_BASE}"
    ASAN_OPTIONS=exitcode=0 timeout --foreground 15s ./bin/c_compiler -S "${TO_ASSEMBLE}" -o "${OUT}.s" 2> "${LOG_FILE_BASE}.compiler.stderr.log" > "${LOG_FILE_BASE}.compiler.stdout.log"
    if [ $? -ne 0 ]; then
        fail_testcase "Failed to compile testcase: \n\t ${LOG_FILE_BASE}.compiler.stderr.log \n\t ${LOG_FILE_BASE}.compiler.stdout.log \n\t ${OUT}.s \n\t ${OUT}.s.printed"
        continue
    fi

    timeout --foreground 15s riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -o "${OUT}.o" -c "${OUT}.s" 2> "${LOG_FILE_BASE}.assembler.stderr.log" > "${LOG_FILE_BASE}.assembler.stdout.log"
    if [ $? -ne 0 ]; then
        fail_testcase "Failed to assemble: \n\t ${LOG_FILE_BASE}.compiler.stderr.log \n\t ${LOG_FILE_BASE}.compiler.stdout.log \n\t ${LOG_FILE_BASE}.assembler.stderr.log \n\t ${LOG_FILE_BASE}.assembler.stdout.log \n\t ${OUT}.s \n\t ${OUT}.s.printed"
        continue
    fi

    timeout --foreground 15s riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -static -o "${OUT}" "${OUT}.o" "${DRIVER}" 2> "${LOG_FILE_BASE}.linker.stderr.log" > "${LOG_FILE_BASE}.linker.stdout.log"
    if [ $? -ne 0 ]; then
        fail_testcase "Failed to link driver: \n\t ${LOG_FILE_BASE}.compiler.stderr.log \n\t ${LOG_FILE_BASE}.compiler.stdout.log \n\t ${LOG_FILE_BASE}.linker.stderr.log \n\t ${LOG_FILE_BASE}.linker.stdout.log \n\t ${OUT}.s \n\t ${OUT}.s.printed"
        continue
    fi

    timeout --foreground 15s spike pk "${OUT}" > "${LOG_FILE_BASE}.simulation.log"
    if [ $? -eq 0 ]; then
        echo -e "\t> Pass"
        (( PASSING++ ))
        printf '\n'

        printf '%s\n' "</testcase>" >> "${J_UNIT_OUTPUT_FILE}"
    else
        fail_testcase "Failed to simulate: simulation did not exit with code 0: \n\t ${LOG_FILE_BASE}.compiler.stderr.log \n\t ${LOG_FILE_BASE}.compiler.stdout.log \n\t ${LOG_FILE_BASE}.simulation.log \n\t ${OUT}.s \n\t ${OUT}.s.printed"
    fi
done

if [ "${COVERAGE:-}" == "1" ]; then
    make coverage
fi

printf "\nPassing %d/%d tests\n" "${PASSING}" "${TOTAL}"
printf '%s\n' '</testsuite>' >> "${J_UNIT_OUTPUT_FILE}"
