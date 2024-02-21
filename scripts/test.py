#!/usr/bin/env python3

"""
A wrapper script to run all the compiler tests. This script will call the
Makefile, run the tests and store the outputs in bin/output.

This script will also generate a JUnit XML file, which can be used to integrate
with CI/CD pipelines.

Usage: test.py [-h] [-m] [-s] [--version] [--no_clean | --coverage] [dir]

Example usage: scripts/test.py compiler_tests/_example

This will print out a progress bar and only run the example tests.
The output would be placed into bin/output/_example/example/.

For more information, run scripts/test.py --help
"""


__version__ = "0.1.0"
__author__ = "William Huynh (@saturn691)"


import os
import argparse
import shutil
import subprocess
import re
import queue
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from colorama import Fore, init, just_fix_windows_console
just_fix_windows_console() # Make Windows behave as standard terminals
init(autoreset=True) # No need to reset style to default after each style changing call


# "File" will suggest the absolute path to the file, including the extension.
SCRIPT_LOCATION = Path(__file__).resolve().parent
PROJECT_LOCATION = SCRIPT_LOCATION.joinpath("..").resolve()
OUTPUT_FOLDER = PROJECT_LOCATION.joinpath("bin/output").resolve()
J_UNIT_OUTPUT_FILE = PROJECT_LOCATION.joinpath("bin/junit_results.xml").resolve()
COMPILER_TEST_FOLDER = PROJECT_LOCATION.joinpath("compiler_tests").resolve()
COMPILER_FILE = PROJECT_LOCATION.joinpath("bin/c_compiler").resolve()
COVERAGE_FOLDER = PROJECT_LOCATION.joinpath("coverage").resolve()

BUILD_TIMEOUT = 60 # seconds
RUN_TIMEOUT = 15 # seconds

class ProgressBar:
    """
    Creates a CLI progress bar that can update itself, provided nothing gets
    in the way.

    Parameters:
    - total_tests: the length of the progress bar.
    """

    def __init__(self, total_tests: int, silent: bool = False):
        self.total_tests = total_tests
        self.passed = 0
        self.failed = 0
        self.silent = silent

        _, max_line_length = os.popen("stty size", "r").read().split()
        self.max_line_length = min(
            int(max_line_length) - len("Running Tests []"),
            80 - len("Running Tests []")
        )

        # Initialize the lines for the progress bar and stats
        print("Running Tests [" + " " * self.max_line_length + "]")
        print(
            Fore.GREEN +  "Pass: 0 | " +
            Fore.RED   +  "Fail: 0 | " +
            Fore.RESET + f"Remaining: {total_tests:2}"
        )
        if not self.silent:
            print("See logs for more details (use -s to disable verbose output).")

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

        progress_bar += Fore.GREEN + '#' * prop_passed    # Green
        progress_bar += Fore.RED   + '#' * prop_failed    # Red
        progress_bar += Fore.RESET + ' ' * remaining      # Empty space

        # Move the cursor up 2 or 3 lines, to the beginning of the progress bar
        lines_to_move_cursor = 2 if self.silent else 3
        print(f"\033[{lines_to_move_cursor}A\r", end='')

        print("Running Tests [{}]".format(progress_bar))

        # Space is left there intentionally to flush out the command line
        print(
            Fore.GREEN + f"Pass: {self.passed:2} | " +
            Fore.RED   + f"Fail: {self.failed:2} | " +
            Fore.RESET + f"Remaining: {remaining_tests:2}"
        )
        if not self.silent:
            print("See logs for more details (use -s to disable verbose output).")

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


def run_subprocess(
    cmd: List[str],
    timeout: int,
    env: Optional[dict] = None,
    log_queue: Optional[queue.Queue] = None,
    init_message: Optional[str] = None,
    path: Optional[str] = None,
    silent: bool = False,
) -> int:
    """
    Simple wrapper for subprocess.run(...) with common arguments and error handling
    """
    if silent:
        assert not log_queue, "You can only silent subprocesses that do not redirect stdout/stderr"
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
    else:
        # None means that stdout and stderr are handled by parent, i.e., they go to console by default
        stdout = None
        stderr = None

    try:
        if not log_queue:
            subprocess.run(
                cmd,
                env=env,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                check=True
            )
        else:
            subprocess.run(
                cmd,
                env=env,
                stderr=open(f"{path}.stderr.log", "w"),
                stdout=open(f"{path}.stdout.log", "w"),
                timeout=timeout,
                check=True
            )
    except subprocess.CalledProcessError as e:
        if not log_queue:
            print(f"{e.cmd} failed with return code {e.returncode}")
        else:
            assert (init_message and path)
            fail_testcase(
                init_message,
                Fore.RED + f"Fail: see {path}.stderr.log and {path}.stdout.log",
                log_queue
            )
        return e.returncode
    except subprocess.TimeoutExpired as e:
        print(f"{e.cmd} took more than {e.timeout}")
        return 5

    return 0


def run_test(driver: Path, log_queue: queue.Queue) -> int:
    """
    Run an instance of a test case.

    Returns:
    0 if passed, non-0 otherwise. This is to increment the pass counter.
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

    to_assemble_str = str(to_assemble)
    init_message = (to_assemble_str + "\n",
                    f'<testcase name="{to_assemble_str}">\n')

    for suffix in [".s", ".o", ""]:
        log_path.with_suffix(suffix).unlink(missing_ok=True)

    # Modifying environment to combat errors on memory leak
    custom_env = os.environ.copy()
    custom_env["ASAN_OPTIONS"] = "exitcode=0"

    # Compile
    return_code = run_subprocess(
        cmd=[COMPILER_FILE, "-S", to_assemble_str, "-o", f"{log_path}.s"],
        timeout=RUN_TIMEOUT,
        env=custom_env,
        log_queue=log_queue,
        init_message=init_message,
        path=f"{log_path}.compiler",
    )
    if return_code != 0:
        return return_code

    # GCC Reference Output
    return_code = run_subprocess(
        cmd=[
                "riscv64-unknown-elf-gcc",
                "-std=c90",
                "-pedantic",
                "-ansi",
                "-O0",
                "-march=rv32imfd",
                "-mabi=ilp32d",
                "-o", f"{log_path}.gcc.s",
                "-S", to_assemble_str
            ],
        timeout=RUN_TIMEOUT,
    )
    if return_code != 0:
        return return_code

    # Assemble
    return_code = run_subprocess(
        cmd=[
                "riscv64-unknown-elf-gcc",
                "-march=rv32imfd", "-mabi=ilp32d",
                "-o", f"{log_path}.o",
                "-c", f"{log_path}.s"
            ],
        timeout=RUN_TIMEOUT,
        log_queue=log_queue,
        init_message=init_message,
        path=f"{log_path}.assembler",
    )
    if return_code != 0:
        return return_code

    # Link
    return_code = run_subprocess(
        cmd=[
                "riscv64-unknown-elf-gcc",
                "-march=rv32imfd", "-mabi=ilp32d", "-static",
                "-o", f"{log_path}",
                f"{log_path}.o", str(driver)
            ],
        timeout=RUN_TIMEOUT,
        log_queue=log_queue,
        init_message=init_message,
        path=f"{log_path}.linker",
    )
    if return_code != 0:
        return return_code

    # Simulate
    return_code = run_subprocess(
        cmd=["spike", "pk", log_path],
        timeout=RUN_TIMEOUT,
        log_queue=log_queue,
        init_message=init_message,
        path=f"{log_path}.simulation",
    )
    if return_code != 0:
        return return_code

    init_print_message, init_xml_message = init_message
    log_queue.put((
        f"{init_print_message}\t> " + Fore.GREEN + "Pass",
        f"{init_xml_message}</testcase>\n"
    ))

    return 0


def empty_log_queue(
    log_queue: queue.Queue,
    verbose: bool = False,
    progress_bar: ProgressBar = None
):
    """
    Empty log queue while logs are sent to XML file and terminal/progress bar
    """
    while not log_queue.empty():
        print_msg, xml_message = log_queue.get()
        processed_msg = re.sub(r"(/workspaces/).+?/([compiler_tests|bin])", r"\1\2", print_msg)

        if verbose:
            print(print_msg)
        else:
            if "Pass" in processed_msg:
                progress_bar.test_passed()
            elif "Fail" in processed_msg:
                progress_bar.test_failed()

        with open(J_UNIT_OUTPUT_FILE, "a") as xml_file:
            xml_file.write(xml_message)



def main() -> int:
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
        "-s", "--short",
        action="store_true",
        default=False,
        help="Disable verbose output into the terminal. Note that all logs will "
        "be stored automatically into log files regardless of this option."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"BetterTesting {__version__}"
    )
    # Coverage cannot be perfomed without rebuilding the compiler
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--no_clean",
        action="store_true",
        default=False,
        help="Do no clean the repository before testing. This will make it "
        "faster but it can be safer to clean if you have any compilation issues."
    )
    group.add_argument(
        "--coverage",
        action="store_true",
        default=False,
        help="Run with coverage if you want to know which part of your code is "
        "executed when running your compiler. See docs/coverage.md"
    )
    args = parser.parse_args()

    try:
        shutil.rmtree(OUTPUT_FOLDER)
    except Exception as e:
        print(f"Error: {e}")

    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    # Clean the repo
    if not args.no_clean:
        return_code = run_subprocess(
            cmd=["make", "-C", PROJECT_LOCATION, "clean"],
            timeout=BUILD_TIMEOUT,
            silent=args.short,
        )
        if return_code != 0:
            return return_code

    # Run coverage if needed
    if args.coverage:
        shutil.rmtree(COVERAGE_FOLDER, ignore_errors=True)
        cmd = ["make", "-C", PROJECT_LOCATION, "with_coverage"]

    # Otherwise run the main make command for building and testing
    else:
        cmd = ["make", "-C", PROJECT_LOCATION, "bin/c_compiler"]

    return_code = run_subprocess(
        cmd=cmd,
        timeout=BUILD_TIMEOUT,
        silent=args.short,
    )
    if return_code != 0:
        return return_code

    with open(J_UNIT_OUTPUT_FILE, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<testsuite name="Integration test">\n')

    drivers = list(Path(args.dir).rglob("*_driver.c"))
    drivers = sorted(drivers, key=lambda p: (p.parent.name, p.name))
    log_queue = queue.Queue()
    results = []

    try:
        progress_bar = ProgressBar(len(drivers), silent=args.short)
    except ValueError as e: # Error comes from TTY when running in Github Actions
        assert not args.short,\
            "Progress bar cannot be initialised, so program has to be verbose"
        progress_bar = None

    if args.multithreading:
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(run_test, driver, log_queue)
                       for driver in drivers]

            for future in as_completed(futures):
                results.append(future.result())
                empty_log_queue(log_queue, not args.short, progress_bar)

    else:
        for driver in drivers:
            result = run_test(driver, log_queue)
            results.append(result)
            empty_log_queue(log_queue, not args.short, progress_bar)

    passing = sum([1 if result == 0 else 0 for result in results])
    total = len(drivers)

    with open(J_UNIT_OUTPUT_FILE, "a") as f:
        f.write('</testsuite>\n')

    if not args.short:
        print(
            "\n>> Test Summary: " +
            Fore.GREEN + f"{passing} Passed, " + Fore.RED + f"{total-passing} Failed"
        )

    # Run coverage if needed
    if args.coverage:
        return_code = run_subprocess(
            cmd=["make", "-C", PROJECT_LOCATION, "coverage"],
            timeout=BUILD_TIMEOUT,
            silent=args.short,
        )
        if return_code != 0:
            return return_code

    return 0


if __name__ == "__main__":
    try:
        main()
    finally:
        # This solves dodgy terminal behaviour on multithreading
        os.system("stty echo")
