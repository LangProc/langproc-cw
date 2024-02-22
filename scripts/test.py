#!/usr/bin/env python3

"""
A wrapper script to run all the compiler tests. This script will call the
Makefile, run the tests and store the outputs in bin/output.

This script will also generate a JUnit XML file, which can be used to integrate
with CI/CD pipelines.

Usage: test.py [-h] [-m] [-s] [--version] [--no_clean] [--coverage] [dir]

Example usage: scripts/test.py compiler_tests/_example

This will print out a progress bar and only run the example tests.
The output would be placed into bin/output/_example/example/.

For more information, run scripts/test.py --help
"""


__version__ = "0.2.0"
__author__ = "William Huynh (@saturn691), Filip Wojcicki, James Nock"


import os
import sys
import argparse
import shutil
import subprocess
from dataclasses import dataclass
from xml.sax.saxutils import escape as xmlescape, quoteattr as xmlquoteattr
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from http.server import HTTPServer, SimpleHTTPRequestHandler


RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"

if not sys.stdout.isatty():
    # Don't output colours when we're not in a TTY
    RED, GREEN, RESET = "", "", ""

# "File" will suggest the absolute path to the file, including the extension.
SCRIPT_LOCATION = Path(__file__).resolve().parent
PROJECT_LOCATION = SCRIPT_LOCATION.joinpath("..").resolve()
OUTPUT_FOLDER = PROJECT_LOCATION.joinpath("bin/output").resolve()
J_UNIT_OUTPUT_FILE = PROJECT_LOCATION.joinpath("bin/junit_results.xml").resolve()
COMPILER_TEST_FOLDER = PROJECT_LOCATION.joinpath("compiler_tests").resolve()
COMPILER_FILE = PROJECT_LOCATION.joinpath("bin/c_compiler").resolve()
COVERAGE_FOLDER = PROJECT_LOCATION.joinpath("coverage").resolve()

BUILD_TIMEOUT_SECONDS = 60
RUN_TIMEOUT_SECONDS = 15
TIMEOUT_RETURNCODE = 124

@dataclass
class Result:
    """Class for keeping track of each test case result"""
    test_case_name: str
    passed: bool
    return_code: int
    timeout: bool
    error_log: Optional[str]

    def to_xml(self) -> str:
        if self.passed:
            return (
                f'<testcase name="{self.test_case_name}">\n'
                f'</testcase>\n'
            )

        timeout = "[TIMED OUT] " if self.timeout else ""
        attribute = xmlquoteattr(timeout + self.error_log)
        xml_tag_body = xmlescape(timeout + self.error_log)
        return (
            f'<testcase name="{self.test_case_name}">\n'
            f'<error type="error" message={attribute}>\n{xml_tag_body}</error>\n'
            f'</testcase>\n'
        )

    def to_log(self) -> str:
        timeout = "[TIMED OUT] " if self.timeout else ""
        if self.passed:
            return f'{self.test_case_name}\n\t> {GREEN}Pass{RESET}\n'
        return f'{self.test_case_name}\n{RED}{timeout + self.error_log}{RESET}\n'

class JUnitXMLFile():
    def __init__(self, path: Path):
        self.path = path
        self.fd = None

    def __enter__(self):
        self.fd = open(self.path, "w")
        self.fd.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.fd.write('<testsuite name="Integration test">\n')
        return self

    def write(self, __s: str) -> int:
        return self.fd.write(__s)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.fd.write('</testsuite>\n')
        self.fd.close()

class ProgressBar:
    """
    Creates a CLI progress bar that can update itself, provided nothing gets
    in the way.

    Parameters:
    - total_tests: the length of the progress bar.
    """

    def __init__(self, total_tests: int):
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
        print(
            GREEN +  "Pass: 0 | " +
            RED   +  "Fail: 0 | " +
            RESET + f"Remaining: {total_tests:2}"
        )

        # Initialize the progress bar
        self.update()

    def update(self):
        remaining_tests = self.total_tests - (self.passed + self.failed)
        progress_bar = ""

        if self.total_tests == 0:
            prop_passed = 0
            prop_failed = 0
        else:
            prop_passed = round(self.passed / self.total_tests * self.max_line_length)
            prop_failed = round(self.failed / self.total_tests * self.max_line_length)

        # Ensure at least one # for passed and failed, if they exist
        prop_passed = max(prop_passed, 1) if self.passed > 0 else 0
        prop_failed = max(prop_failed, 1) if self.failed > 0 else 0

        remaining = self.max_line_length - prop_passed - prop_failed

        progress_bar += GREEN + '#' * prop_passed    # Green
        progress_bar += RED   + '#' * prop_failed    # Red
        progress_bar += RESET + ' ' * remaining      # Empty space

        # Move the cursor up 2 lines to the beginning of the progress bar
        lines_to_move_cursor = 2
        print(f"\033[{lines_to_move_cursor}A\r", end='')

        print("Running Tests [{}]".format(progress_bar))

        # Space is left there intentionally to flush out the command line
        print(
            GREEN + f"Pass: {self.passed:2} | " +
            RED   + f"Fail: {self.failed:2} | " +
            RESET + f"Remaining: {remaining_tests:2}"
        )

    def update_with_value(self, passed: bool):
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self.update()

def run_test(driver: Path) -> Result:
    """
    Run an instance of a test case.

    Parameters:
    - driver: driver path.

    Returns Result object
    """

    # Replaces example_driver.c -> example.c
    new_name = driver.stem.replace('_driver', '') + '.c'
    to_assemble = driver.parent.joinpath(new_name).resolve()
    test_name = to_assemble.relative_to(PROJECT_LOCATION)

    # Determine the relative path to the file wrt. COMPILER_TEST_FOLDER.
    relative_path = to_assemble.relative_to(COMPILER_TEST_FOLDER)

    # Construct the path where logs would be stored, without the suffix
    # e.g. .../bin/output/_example/example/example
    log_path = Path(OUTPUT_FOLDER).joinpath(relative_path.parent, to_assemble.stem, to_assemble.stem)

    # Recreate the directory
    shutil.rmtree(log_path.parent, ignore_errors=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Modifying environment to combat errors on memory leak
    custom_env = os.environ.copy()
    custom_env["ASAN_OPTIONS"] = "exitcode=0"

    def relevant_files(component):
        return f"{log_path}.{component}.stderr.log \n\t {log_path}.{component}.stdout.log"
    compiler_log_file_str=f"{relevant_files('compiler')} \n\t {log_path}.s \n\t {log_path}.s.printed"

    # Compile
    return_code, _, timed_out = run_subprocess(
        cmd=[COMPILER_FILE, "-S", to_assemble, "-o", f"{log_path}.s"],
        timeout=RUN_TIMEOUT_SECONDS,
        env=custom_env,
        log_path=f"{log_path}.compiler",
    )
    if return_code != 0:
        msg = f"\t> Failed to compile testcase: \n\t {compiler_log_file_str}"
        return Result(test_case_name=test_name, return_code=return_code, passed=False, timeout=timed_out, error_log=msg)

    # GCC Reference Output
    return_code, _, timed_out = run_subprocess(
        cmd=[
                "riscv64-unknown-elf-gcc", "-std=c90", "-pedantic", "-ansi", "-O0", "-march=rv32imfd", "-mabi=ilp32d",
                "-o", f"{log_path}.gcc.s", "-S", to_assemble
            ],
        timeout=RUN_TIMEOUT_SECONDS,
        log_path=f"{log_path}.reference",
    )
    if return_code != 0:
        msg = f"\t> Failed to generate reference: \n\t {compiler_log_file_str} \n\t {relevant_files('reference')}"
        return Result(test_case_name=test_name, return_code=return_code, passed=False, timeout=timed_out, error_log=msg)

    # Assemble
    return_code, _, timed_out = run_subprocess(
        cmd=[
                "riscv64-unknown-elf-gcc", "-march=rv32imfd", "-mabi=ilp32d",
                "-o", f"{log_path}.o", "-c", f"{log_path}.s"
            ],
        timeout=RUN_TIMEOUT_SECONDS,
        log_path=f"{log_path}.assembler",
    )
    if return_code != 0:
        msg = f"\t> Failed to assemble: \n\t {compiler_log_file_str} \n\t {relevant_files('assembler')}"
        return Result(test_case_name=test_name, return_code=return_code, passed=False, timeout=timed_out, error_log=msg)

    # Link
    return_code, _, timed_out = run_subprocess(
        cmd=[
                "riscv64-unknown-elf-gcc", "-march=rv32imfd", "-mabi=ilp32d", "-static",
                "-o", f"{log_path}", f"{log_path}.o", str(driver)
            ],
        timeout=RUN_TIMEOUT_SECONDS,
        log_path=f"{log_path}.linker",
    )
    if return_code != 0:
        msg = f"\t> Failed to link driver: \n\t {compiler_log_file_str} \n\t {relevant_files('linker')}"
        return Result(test_case_name=test_name, return_code=return_code, passed=False, timeout=timed_out, error_log=msg)

    # Simulate
    return_code, _, timed_out = run_subprocess(
        cmd=["spike", "pk", log_path],
        timeout=RUN_TIMEOUT_SECONDS,
        log_path=f"{log_path}.simulation",
    )
    if return_code != 0:
        msg = f"\t> Failed to simulate: \n\t {compiler_log_file_str} \n\t {relevant_files('simulation')}"
        return Result(test_case_name=test_name, return_code=return_code, passed=False, timeout=timed_out, error_log=msg)

    return Result(test_case_name=test_name, return_code=return_code, passed=True, timeout=False, error_log="")

def run_subprocess(
    cmd: List[str],
    timeout: int,
    env: Optional[dict] = None,
    log_path: Optional[str] = None,
    silent: bool = False,
) -> tuple[int, str, bool]:
    """
    Wrapper for subprocess.run(...) with common arguments and error handling.

    Returns tuple of (return_code: int, error_message: str, timed_out: bool)
    """
    # None means that stdout and stderr are handled by parent, i.e., they go to console by default
    stdout = None
    stderr = None

    if silent:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
    elif log_path:
        stdout = open(f"{log_path}.stdout.log", "w")
        stderr = open(f"{log_path}.stderr.log", "w")

    try:
        subprocess.run(cmd, env=env, stdout=stdout, stderr=stderr, timeout=timeout, check=True)
    except subprocess.CalledProcessError as e:
        return e.returncode, f"{e.cmd} failed with return code {e.returncode}", False
    except subprocess.TimeoutExpired as e:
        return TIMEOUT_RETURNCODE, f"{e.cmd} took more than {e.timeout}", True
    return 0, "", False

def clean() -> bool:
    """
    Wrapper for make clean.

    Return True if successful, False otherwise
    """
    print(GREEN + "Cleaning project..." + RESET)
    return_code, error_msg, _ = run_subprocess(
        cmd=["make", "-C", PROJECT_LOCATION, "clean"],
        timeout=BUILD_TIMEOUT_SECONDS,
        silent=True,
    )

    if return_code != 0:
        print(RED + "Error when cleaning:", error_msg + RESET)
        return False
    return True

def make(silent: bool) -> bool:
    """
    Wrapper for make bin/c_compiler.

    Return True if successful, False otherwise
    """
    print(GREEN + "Running make..." + RESET)
    return_code, error_msg, _ = run_subprocess(
        cmd=["make", "-C", PROJECT_LOCATION, "bin/c_compiler"], timeout=BUILD_TIMEOUT_SECONDS, silent=silent
    )
    if return_code != 0:
        print(RED + "Error when making:", error_msg + RESET)
        return False

    return True

def coverage() -> bool:
    """
    Wrapper for make coverage.

    Return True if successful, False otherwise
    """
    print(GREEN + "Running make coverage..." + RESET)
    return_code, error_msg, _ = run_subprocess(
        cmd=["make", "-C", PROJECT_LOCATION, "coverage"], timeout=BUILD_TIMEOUT_SECONDS, silent=True
    )
    if return_code != 0:
        print(RED + "Error when making coverage:", error_msg + RESET)
        return False
    return True

def serve_coverage_forever(host: str, port: int):
    """
    Starts a HTTP server which serves the coverage folder forever until Ctrl+C
    is pressed.
    """
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, directory=None, **kwargs):
            super().__init__(*args, directory=COVERAGE_FOLDER, **kwargs)

        def log_message(self, format, *args):
            pass

    httpd = HTTPServer((host, port), Handler)
    print(GREEN + "Serving coverage on" + RESET + f" http://{host}:{port}/ ... (Ctrl+C to exit)")
    httpd.serve_forever()

def process_result(
    result: Result,
    xml_file: JUnitXMLFile,
    verbose: bool = False,
    progress_bar: ProgressBar = None,
):
    """
    Processes results and updates progress bar if necessary.
    """
    xml_file.write(result.to_xml())

    if verbose:
        print(result.to_log())
        return

    if progress_bar:
        progress_bar.update_with_value(result.passed)

    return

def run_tests(args, xml_file: JUnitXMLFile):
    """
    Runs tests against compiler.
    """
    drivers = list(Path(args.dir).rglob("*_driver.c"))
    drivers = sorted(drivers, key=lambda p: (p.parent.name, p.name))
    results = []

    progress_bar = None
    if args.short and sys.stdout.isatty():
        progress_bar = ProgressBar(len(drivers))
    else:
        # Force verbose mode when not a terminal
        args.short = False

    if args.multithreading:
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(run_test, driver) for driver in drivers]
            for future in as_completed(futures):
                result = future.result()
                results.append(result.passed)
                process_result(result, xml_file, not args.short, progress_bar)

    else:
        for driver in drivers:
            result = run_test(driver)
            results.append(result.passed)
            process_result(result, xml_file, not args.short, progress_bar)

    passing = sum(results)
    total = len(drivers)

    if args.short:
        return

    print("\n>> Test Summary: " + GREEN + f"{passing} Passed, " + RED + f"{total-passing} Failed" + RESET)

def parse_args():
    """
    Wrapper for argument parsing.
    """
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
    parser.add_argument(
        "--no-clean",
        '--no_clean',
        action="store_true",
        default=False,
        help="Don't clean the repository before testing. This will make it "
        "faster but it can be safer to clean if you have any compilation issues."
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        default=False,
        help="Run with coverage if you want to know which part of your code is "
        "executed when running your compiler. See docs/coverage.md"
    )
    return parser.parse_args()

def main():
    args = parse_args()

    shutil.rmtree(OUTPUT_FOLDER, ignore_errors=True)
    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    if not args.no_clean and not clean():
        # Clean the repo if required and exit if this fails.
        exit(2)

    if not make(silent=args.short):
        exit(3)

    with JUnitXMLFile(J_UNIT_OUTPUT_FILE) as xml_file:
        run_tests(args, xml_file)

    if args.coverage:
        if not coverage():
            exit(4)
        serve_coverage_forever('0.0.0.0', 8000)

if __name__ == "__main__":
    try:
        main()
    finally:
        print(RESET, end="")
        if sys.stdout.isatty():
            # This solves dodgy terminal behaviour on multithreading
            os.system("stty echo")
