#!/usr/bin/env python3

"""
A wrapper script to run all the compiler tests. This script will call the
Makefile, run the tests and store the outputs in bin/output.

This script will also generate a JUnit XML file, which can be used to integrate
with CI/CD pipelines.

Usage: test.py [-h] [-m] [-v] [--version] [dir]

Example usage: scripts/test.py compiler_tests/_example

This will print out a progress bar and only run the example tests.
The output would be placed into bin/output/_example/example/.

For more information, run scripts/test.py -h
"""


__version__ = "0.1.0"
__author__ = "William Huynh (@saturn691)"


import argparse
import os
import shutil
import subprocess
import queue
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# "File" will suggest the absolute path to the file, including the extension.
SCRIPT_LOCATION = Path(__file__).resolve().parent
PROJECT_LOCATION = SCRIPT_LOCATION.joinpath("..").resolve()
OUTPUT_FOLDER = PROJECT_LOCATION.joinpath("bin/output").resolve()
J_UNIT_OUTPUT_FILE = PROJECT_LOCATION.joinpath(
    "bin/junit_results.xml").resolve()
COMPILER_TEST_FOLDER = PROJECT_LOCATION.joinpath("compiler_tests").resolve()
COMPILER_FILE = PROJECT_LOCATION.joinpath("bin/c_compiler").resolve()


class ProgressBar:
    """
    Creates a CLI progress bar that can update itself, provided nothing gets
    in the way.

    Parameters:
    - total_tests: the length of the progress bar.
    """

    def __init__(self, total_tests):
        self.total_tests = total_tests
        self.passed = 0
        self.failed = 0

        _, max_line_length = os.popen("stty size", "r").read().split()
        self.max_line_length = min(
            int(max_line_length) - len("Running Tests []"),
            80 - len("Running Tests []")
        )

        # Initialize the lines for the progress bar and stats
        print("Running Tests [" + " " * self.max_line_length + "]")
        print("Pass: 0 | Fail: 0 | Remaining: {}".format(total_tests))
        print("See logs for more details (use -v for verbose output).")

        # Initialize the progress bar
        self.update()

    def update(self):
        remaining_tests = self.total_tests - (self.passed + self.failed)
        progress_bar = ""

        if self.total_tests == 0:
            prop_passed = 0
            prop_failed = 0
        else:
            prop_passed = round(
                self.passed / self.total_tests * self.max_line_length)
            prop_failed = round(
                self.failed / self.total_tests * self.max_line_length
            )

        # Ensure at least one # for passed and failed, if they exist
        prop_passed = max(prop_passed, 1) if self.passed > 0 else 0
        prop_failed = max(prop_failed, 1) if self.failed > 0 else 0

        remaining = self.max_line_length - prop_passed - prop_failed

        progress_bar += '\033[92m#\033[0m' * prop_passed    # Green
        progress_bar += '\033[91m#\033[0m' * prop_failed    # Red
        progress_bar += ' ' * remaining                     # Empty space

        # Move the cursor up 3 lines, to the beginning of the progress bar
        print("\033[3A\r", end='')

        print("Running Tests [{}]".format(progress_bar))
        # Space is left there intentionally to flush out the command line
        print("Pass: {:2} | Fail: {:2} | Remaining: {:2} ".format(
            self.passed, self.failed, remaining_tests))
        print("See logs for more details (use -v for verbose output).")

    def test_passed(self):
        self.passed += 1
        self.update()

    def test_failed(self):
        self.failed += 1
        self.update()


def fail_testcase(
    init_message: tuple[str, str],
    message: str,
    log_queue: queue.Queue
):
    """
    Updates the log queue with the JUnit and the stdout fail message.
    """
    init_print_message, init_xml_message = init_message
    print_message = f"\t> {message}"
    xml_message = (
        f'<error type="error" message="{message}">{message}</error>\n'
        '</testcase>\n'
    )
    log_queue.put((init_print_message + print_message,
                   init_xml_message + xml_message))


def run_test(driver: Path, log_queue: queue.Queue) -> int:
    """
    Run an instance of a test case.

    Returns:
    1 if passed, 0 otherwise. This is to increment the pass counter.
    """

    # Replaces example_driver.c -> example.c
    new_name = driver.stem.replace('_driver', '') + '.c'
    to_assemble = driver.parent.joinpath(new_name).resolve()

    # Determine the relative path to the file wrt. COMPILER_TEST_FOLDER.
    relative_path = to_assemble.relative_to(COMPILER_TEST_FOLDER)

    # Construct the path where logs would be stored, without the suffix
    # e.g. .../bin/output/_example/example/example
    log_path = Path(OUTPUT_FOLDER).joinpath(
        relative_path.parent, to_assemble.stem, to_assemble.stem
    )

    # Ensure the directory exists.
    log_path.parent.mkdir(parents=True, exist_ok=True)

    init_message = (str(to_assemble) + "\n",
                    f'<testcase name="{to_assemble}">\n')

    for suffix in [".s", ".o", ""]:
        log_path.with_suffix(suffix).unlink(missing_ok=True)

    # Compile
    compiler_result = subprocess.run(
        [
            COMPILER_FILE,
            "-S", str(to_assemble),
            "-o", f"{log_path}.s",
        ],
        stderr=open(f"{log_path}.compiler.stderr.log", "w"),
        stdout=open(f"{log_path}.compiler.stdout.log", "w")
    )

    if compiler_result.returncode != 0:
        fail_testcase(
            init_message,
            f"Fail: see {log_path}.compiler.stderr.log "
            f"and {log_path}.compiler.stdout.log",
            log_queue
        )
        return 0

    # GCC Reference Output
    gcc_result = subprocess.run(
        [
            "riscv64-unknown-elf-gcc",
            "-std=c90",
            "-pedantic",
            "-ansi",
            "-O0",
            "-march=rv32imfd",
            "-mabi=ilp32d",
            "-o", f"{log_path}.gcc.s",
            "-S", str(to_assemble)
        ]
    )

    # Assemble
    assembler_result = subprocess.run(
        [
            "riscv64-unknown-elf-gcc",
            "-march=rv32imfd", "-mabi=ilp32d",
            "-o", f"{log_path}.o",
            "-c", f"{log_path}.s"
        ],
        stderr=open(f"{log_path}.assembler.stderr.log", "w"),
        stdout=open(f"{log_path}.assembler.stdout.log", "w")
    )

    if assembler_result.returncode != 0:
        fail_testcase(
            init_message,
            f"Fail: see {log_path}.assembler.stderr.log "
            f"and {log_path}.assembler.stdout.log",
            log_queue
        )
        return 0

    # Link
    linker_result = subprocess.run(
        [
            "riscv64-unknown-elf-gcc",
            "-march=rv32imfd", "-mabi=ilp32d", "-static",
            "-o", f"{log_path}",
            f"{log_path}.o", str(driver)
        ],
        stderr=open(f"{log_path}.linker.stderr.log", "w"),
        stdout=open(f"{log_path}.linker.stdout.log", "w")
    )

    if linker_result.returncode != 0:
        fail_testcase(
            init_message,
            f"Fail: see {log_path}.linker.stderr.log "
            f"and {log_path}.linker.stdout.log",
            log_queue
        )
        return 0

    # Simulate
    try:
        simulation_result = subprocess.run(
            ["spike", "pk", log_path],
            stdout=open(f"{log_path}.simulation.log", "w"),
            timeout=3
        )
    except subprocess.TimeoutExpired:
        print("The subprocess timed out.")
        simulation_result = subprocess.CompletedProcess(args=[], returncode=1)

    if simulation_result.returncode != 0:
        fail_testcase(
            init_message,
            f"Fail: simulation did not exit with exitcode 0",
            log_queue
        )
        return 0
    else:
        init_print_message, init_xml_message = init_message
        log_queue.put((init_print_message + "\t> Pass",
                       init_xml_message + "</testcase>\n"))

    return 1


def empty_log_queue(
    log_queue: queue.Queue,
    verbose: bool = False,
    progress_bar: ProgressBar = None
):
    while not log_queue.empty():
        print_msg, xml_message = log_queue.get()

        if verbose:
            print(print_msg)
        else:
            if "Pass" in print_msg:
                progress_bar.test_passed()
            elif "Fail" in print_msg:
                progress_bar.test_failed()

        with open(J_UNIT_OUTPUT_FILE, "a") as xml_file:
            xml_file.write(xml_message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dir",
        nargs="?",
        default=COMPILER_TEST_FOLDER,
        type=Path,
        help="(Optional) paths to the compiler test folders. Use this to select "
        "certain tests. Leave blank to run all tests."
    )

    parser.add_argument(
        "-m", "--multithreading",
        action="store_true",
        default=False,
        help="Use multiple threads to run tests. This will make it faster, "
        "but order is not guaranteed. Should only be used for speed."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose output into the terminal. Note that all logs will "
        "be stored automatically into log files regardless of this option."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"BetterTesting {__version__}"
    )
    args = parser.parse_args()

    try:
        shutil.rmtree(OUTPUT_FOLDER)
    except Exception as e:
        print(f"Error: {e}")

    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    subprocess.run(["make", "-C", PROJECT_LOCATION, "bin/c_compiler"])

    with open(J_UNIT_OUTPUT_FILE, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<testsuite name="Integration test">\n')

    drivers = list(Path(args.dir).rglob("*_driver.c"))
    drivers = sorted(drivers, key=lambda p: (p.parent.name, p.name))
    log_queue = queue.Queue()
    results = []
    progress_bar = ProgressBar(len(drivers))

    if args.multithreading:
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(run_test, driver, log_queue)
                       for driver in drivers]

            for future in as_completed(futures):
                results.append(future.result())
                empty_log_queue(log_queue, args.verbose, progress_bar)

    else:
        for driver in drivers:
            result = run_test(driver, log_queue)
            results.append(result)
            empty_log_queue(log_queue, args.verbose, progress_bar)

    passing = sum(results)
    total = len(drivers)

    with open(J_UNIT_OUTPUT_FILE, "a") as f:
        f.write('</testsuite>\n')

    print("\n>> Test Summary: {} Passed, {} Failed".format(
        passing, total-passing))


if __name__ == "__main__":
    try:
        main()
    finally:
        # This solves dodgy terminal behaviour on multithreading
        os.system("stty echo")
