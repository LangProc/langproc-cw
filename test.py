#!/usr/bin/env python3

"""
A wrapper script to run all the compiler tests. This script will call the
Makefile, run the tests and store the outputs in build/output.

This script will also generate a JUnit XML file, which can be used to integrate
with CI/CD pipelines.

Usage: ./test.py [-h] [-m] [-s] [--version] [--no_clean] [--coverage] [--use_cmake] [--validate_tests] [dir]

Example usage for all tests: ./test.py

Example usage for tests in a directory: ./test.py tests/_example

This will print out a progress bar and only run the example tests.
The output would be placed into build/output/_example/example/.

For more information, run ./test.py --help
"""


__version__ = "1.0.0"
__author__ = "William Huynh, Filip Wojcicki, James Nock, Quentin Corradi"


import os
import sys
import argparse
import shutil
import subprocess
from glob import glob
from dataclasses import dataclass
from xml.sax.saxutils import escape as xmlescape, quoteattr as xmlquoteattr
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from http.server import HTTPServer, SimpleHTTPRequestHandler


RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

if not sys.stdout.isatty():
    # Don't output colours when we're not in a TTY
    RED, GREEN, YELLOW, RESET = "", "", "", ""

# "File" will suggest the absolute path to the file, including the extension.
PROJECT_LOCATION = Path(__file__).resolve().parent
BUILD_FOLDER = PROJECT_LOCATION.joinpath("build").resolve()
OUTPUT_FOLDER = PROJECT_LOCATION.joinpath("build/output").resolve()
J_UNIT_OUTPUT_FILE = PROJECT_LOCATION.joinpath("build/junit_results.xml").resolve()
TEST_FOLDER = PROJECT_LOCATION.joinpath("tests").resolve()
COMPILER_FILE = PROJECT_LOCATION.joinpath("build/c_compiler").resolve()
COVERAGE_FOLDER = PROJECT_LOCATION.joinpath("coverage").resolve()

BUILD_TIMEOUT_SECONDS = 60
RUN_TIMEOUT_SECONDS = 15
TIMEOUT_RETURNCODE = 124

GCC = "riscv32-unknown-elf-gcc"
# GCC is not targetting rv32imfd because it is compatible with rv32gc which is the more widespread 32bits target
GCC_ARCH = "-march=rv32gc"
GCC_ABI = "-mabi=ilp32d"

@dataclass
class Result:
    """Class for keeping track of each test case result"""
    test_case_name: str
    return_code: int
    timeout: bool
    error_log: Optional[str]

    def passed(self) -> bool:
        return self.return_code == 0

    def to_xml(self) -> str:
        if self.passed():
            system_out = f"<system-out>{self.error_log}</system-out>\n" if self.error_log else ""
            return (
                f"<testcase name=\"{self.test_case_name}\">\n"
                f"{system_out}"
                f"</testcase>\n"
            )

        timeout = "[TIMED OUT] " if self.timeout else ""
        attribute = xmlquoteattr(timeout + self.error_log)
        xml_tag_body = xmlescape(timeout + self.error_log)
        return (
            f"<testcase name=\"{self.test_case_name}\">\n"
            f"<error type=\"error\" message={attribute}>\n{xml_tag_body}</error>\n"
            f"</testcase>\n"
        )

    def to_log(self) -> str:
        timeout = "[TIMED OUT] " if self.timeout else ""
        if self.return_code != 0:
            return f"{self.test_case_name}\n{RED}{timeout + self.error_log}{RESET}\n"
        if self.error_log is None:
            return f"{self.test_case_name}\n\t> {GREEN}Pass{RESET}\n"
        return f"{self.test_case_name}\n\t> {YELLOW}{self.error_log}{RESET}\n"

class JUnitXMLFile():
    def __init__(self, path: Path):
        self.path = path
        self.fd = None

    def __enter__(self):
        self.fd = open(self.path, "w")
        self.fd.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        self.fd.write("<testsuite name=\"Integration test\">\n")
        return self

    def write(self, __s: str) -> int:
        return self.fd.write(__s)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.fd.write("</testsuite>\n")
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
        print(f"{GREEN}Pass: 0 | {RED}Fail: 0 | {RESET}Remaining: {total_tests:2}")

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

        progress_bar = f"{GREEN}{'#' * prop_passed}{RED}{'#' * prop_failed}{RESET}{' ' * remaining}"

        # Move the cursor up 2 lines to the beginning of the progress bar
        lines_to_move_cursor = 2
        print(f"\033[{lines_to_move_cursor}A\r", end="")

        print("Running Tests [{}]".format(progress_bar))

        print(f"{GREEN}Pass: {self.passed:2} | {RED}Fail: {self.failed:2} | {RESET}Remaining: {remaining_tests:2}")

    def update_with_value(self, passed: bool):
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self.update()

def run_subprocess(
    cmd: List[str],
    timeout: int,
    env: Optional[dict] = None,
    log_path: Optional[str] = None,
    verbose: bool = True,
) -> tuple[int, str, bool]:
    """
    Wrapper for subprocess.run(...) with common arguments and error handling.

    Returns tuple of (return_code: int, error_message: str, timed_out: bool)
    """
    # None means that stdout and stderr are handled by parent, i.e., they go to console by default
    stdout = None
    stderr = None

    if not verbose:
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
    print(f"{GREEN}Cleaning project...{RESET}")
    return_code, error_msg, _ = run_subprocess(
        cmd=["make", "-C", PROJECT_LOCATION, "clean"],
        timeout=BUILD_TIMEOUT_SECONDS,
        verbose=False,
    )

    if return_code != 0:
        print(f"{RED}Error when cleaning: {error_msg}{RESET}")
        return False
    return True

def make(verbose: bool, log_path: Optional[str] = None) -> bool:
    """
    Wrapper for make build/c_compiler.

    Return True if successful, False otherwise
    """
    print(f"{GREEN}Running make...{RESET}")
    custom_env = os.environ.copy()
    custom_env["DEBUG"] = "1"
    return_code, error_msg, _ = run_subprocess(
        cmd=["make", "-C", PROJECT_LOCATION, "build/c_compiler"], timeout=BUILD_TIMEOUT_SECONDS, verbose=verbose, env=custom_env, log_path=log_path
    )
    if return_code != 0:
        print(f"{RED}Error when running make: {error_msg}{RESET}")
        return False

    return True

def cmake(verbose: bool) -> bool:
    """
    Wrapper for cmake --build build

    Return True if successful, False otherwise
    """
    print(f"{GREEN}Running cmake...{RESET}")

    # cmake configure + generate
    # -DCMAKE_BUILD_TYPE=Release is equal to -O3
    return_code, error_msg, _ = run_subprocess(
        cmd=["cmake", "-S", PROJECT_LOCATION, "-B", BUILD_FOLDER, "-DCMAKE_BUILD_TYPE=Release"],
        timeout=BUILD_TIMEOUT_SECONDS,
        verbose=verbose
    )
    if return_code != 0:
        print(f"{RED}Error when running cmake (configure + generate): {error_msg}{RESET}")
        return False

    # cmake compile
    return_code, error_msg, _ = run_subprocess(
        cmd=["cmake", "--build", BUILD_FOLDER], timeout=BUILD_TIMEOUT_SECONDS, verbose=verbose
    )
    if return_code != 0:
        print(f"{RED}Error when running cmake (compile): {error_msg}{RESET}")
        return False

    return True

def build(use_cmake: bool = False, coverage: bool = False, verbose: bool = True):
    """
    Wrapper for building the student compiler. Assumes output folder exists.
    """
    # Prepare the build folder
    Path(BUILD_FOLDER).mkdir(parents=True, exist_ok=True)

    # Build the compiler using cmake or make
    if use_cmake and not coverage:
        build_success = cmake(verbose=verbose)
    else:
        if use_cmake and coverage:
            print(f"{RED}Coverage is not supported with CMake. Switching to make.{RESET}")
        build_success = make(verbose=verbose)

    return build_success

def coverage() -> bool:
    """
    Wrapper for make coverage.

    Return True if successful, False otherwise
    """
    print(f"{GREEN}Running make coverage...{RESET}")
    custom_env = os.environ.copy()
    custom_env["DEBUG"] = "1"
    return_code, error_msg, _ = run_subprocess(
        cmd=["make", "-C", PROJECT_LOCATION, "coverage"], timeout=BUILD_TIMEOUT_SECONDS, verbose=False, env=custom_env
    )
    if return_code != 0:
        print(f"{RED}Error when running make coverage: {error_msg}{RESET}")
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
    print(f"{GREEN}Serving coverage on{RESET} http://{host}:{port}/ ... (Ctrl+C to exit)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"{RED}\nServer has been stopped!{RESET}")

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
        progress_bar.update_with_value(result.passed())

    return

def run_test(directory: Path, driver: Path, validate_tests: bool = False) -> Result:
    """
    Run an instance of a test case.

    Parameters:
    - driver: driver path.

    Returns Result object
    """
    
    # Replaces example_driver.c -> example.c
    new_name = driver.stem.replace("_driver", "") + ".c"
    to_assemble = driver.parent.joinpath(new_name).resolve()
    test_name = to_assemble.relative_to(PROJECT_LOCATION)

    # Determine the relative path to the file wrt. TEST_FOLDER.
    relative_path = to_assemble.relative_to(directory)

    # Construct the path where logs would be stored, without the suffix
    # e.g. .../build/output/_example/example/example
    log_path = Path(OUTPUT_FOLDER).joinpath(relative_path.parent, to_assemble.stem, to_assemble.stem)

    # Recreate the directory
    shutil.rmtree(log_path.parent, ignore_errors=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def relevant_files(component):
        return f"\n\t {log_path}.{component}.stderr.log \n\t {log_path}.{component}.stdout.log"

    # Modifying environment to combat errors on memory leak
    custom_env = os.environ.copy()
    custom_env["ASAN_OPTIONS"] = f"log_path={log_path}.asan.log"
    custom_env["UBSAN_OPTIONS"] = f"log_path={log_path}.ubsan.log"

    # Compile the test case into assembly using the custom compiler or GCC for self validation
    if validate_tests:
        compile_cmd = [GCC, "-std=c90", "-pedantic", "-ansi", "-O0", GCC_ARCH, GCC_ABI, "-S", to_assemble, "-o", f"{log_path}.s"]
    else:
        compile_cmd = [COMPILER_FILE, "-S", to_assemble, "-o", f"{log_path}.s"]

    # Compile
    return_code, _, timed_out = run_subprocess(
        cmd=compile_cmd,
        timeout=RUN_TIMEOUT_SECONDS,
        env=custom_env,
        log_path=f"{log_path}.compiler",
    )
    sanitizer_file_list = glob(f"{log_path}.*san.log.*")
    compiler_log_file_str = f"{relevant_files('compiler')} \n\t {log_path}.s \n\t {log_path}.s.printed" \
        + "".join("\n\t " + p for p in sanitizer_file_list)
    if return_code != 0:
        msg = f"\t> Failed to compile testcase: {compiler_log_file_str}"
        return Result(test_case_name=test_name, return_code=return_code, timeout=timed_out, error_log=msg)

    # GCC Reference Output
    return_code, _, timed_out = run_subprocess(
        cmd=[GCC, "-std=c90", "-pedantic", "-ansi", "-O0", GCC_ARCH, GCC_ABI, "-S", to_assemble, "-o", f"{log_path}.gcc.s"],
        timeout=RUN_TIMEOUT_SECONDS,
        log_path=f"{log_path}.reference",
    )
    if return_code != 0:
        msg = f"\t> Failed to generate reference: {compiler_log_file_str} {relevant_files('reference')}"
        return Result(test_case_name=test_name, return_code=return_code, timeout=timed_out, error_log=msg)

    # Assemble
    return_code, _, timed_out = run_subprocess(
        cmd=[GCC, GCC_ARCH, GCC_ABI, "-c", f"{log_path}.s", "-o", f"{log_path}.o"],
        timeout=RUN_TIMEOUT_SECONDS,
        log_path=f"{log_path}.assembler",
    )
    if return_code != 0:
        msg = f"\t> Failed to assemble: {compiler_log_file_str} {relevant_files('assembler')}"
        return Result(test_case_name=test_name, return_code=return_code, timeout=timed_out, error_log=msg)

    # Link
    return_code, _, timed_out = run_subprocess(
        cmd=[GCC, GCC_ARCH, GCC_ABI, "-static", f"{log_path}.o", str(driver), "-o", f"{log_path}"],
        timeout=RUN_TIMEOUT_SECONDS,
        log_path=f"{log_path}.linker",
    )
    if return_code != 0:
        msg = f"\t> Failed to link driver: {compiler_log_file_str} {relevant_files('linker')}"
        return Result(test_case_name=test_name, return_code=return_code, timeout=timed_out, error_log=msg)

    # Simulate
    return_code, _, timed_out = run_subprocess(
        cmd=["spike", "--isa=rv32gc", "pk", log_path],
        timeout=RUN_TIMEOUT_SECONDS,
        log_path=f"{log_path}.simulation",
    )
    if return_code != 0:
        msg = f"\t> Failed to simulate: {compiler_log_file_str} {relevant_files('simulation')}"
        return Result(test_case_name=test_name, return_code=return_code, timeout=timed_out, error_log=msg)

    msg = "Sanitizer warnings: " + " ".join(sanitizer_file_list) if len(sanitizer_file_list) != 0 else None
    return Result(test_case_name=test_name, return_code=return_code, timeout=False, error_log=msg)

def run_tests(directory: Path, xml_file: JUnitXMLFile, multithreading: bool, verbose: bool, validate_tests: bool = False) -> bool:
    """
    Runs tests against compiler.
    """
    drivers = list(directory.rglob("*_driver.c"))
    drivers = sorted(drivers, key=lambda p: (p.parent.name, p.name))
    results = []

    progress_bar = None
    if not verbose and sys.stdout.isatty():
        progress_bar = ProgressBar(len(drivers))
    else:
        # Force verbose mode when not a terminal
        verbose = True

    if multithreading:
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(run_test, directory, driver, validate_tests=validate_tests) for driver in drivers]
            for future in as_completed(futures):
                result = future.result()
                results.append(result.passed())
                process_result(result, xml_file, verbose, progress_bar)

    else:
        for driver in drivers:
            result = run_test(directory, driver, validate_tests=validate_tests)
            results.append(result.passed())
            process_result(result, xml_file, verbose, progress_bar)

    passing = sum(results)
    total = len(drivers)

    if verbose:
        print(f"\n>> Test Summary: {GREEN}{passing} Passed, {RED}{total-passing} Failed{RESET}")

    return passing == total

def parse_args():
    """
    Wrapper for argument parsing.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dir",
        nargs="?",
        default=TEST_FOLDER,
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
        "-s", "--silent",
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
        "--no_clean",
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
    parser.add_argument(
        "--use_cmake",
        action="store_true",
        default=False,
        help="Use CMake to build the project instead of make. This will result "
        "in faster builds and tests, however, CMake is not part of the course, "
        "and you may run into issues."
    )
    parser.add_argument(
        "--validate_tests",
        action="store_true",
        default=False,
        help="Use GCC to validate tests instead of testing the custom compiler. "
        "This is used for CI/CD pipeline, not for normal student usage. "
        "YOUR COMPILER WILL NOT BE USED NOR BUILT WITH THIS OPTION."
    )
    return parser.parse_args()

def main():
    args = parse_args()

    # Clean the repo if required
    if not args.no_clean:
        clean_success = clean()
        if not clean_success:
            sys.exit(2)

    # Prepare the output folder
    shutil.rmtree(OUTPUT_FOLDER, ignore_errors=True)
    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    # There is no need for building the student compiler when testing with riscv-gcc
    if not args.validate_tests:
        build_success = build(use_cmake=args.use_cmake, coverage=args.coverage, verbose=not args.silent)
        if not build_success:
            exit(3)

    # Run the tests and save the results into JUnit XML file
    with JUnitXMLFile(J_UNIT_OUTPUT_FILE) as xml_file:
        all_test_success = run_tests(directory=Path(args.dir), xml_file=xml_file, multithreading=args.multithreading, verbose=not args.silent, validate_tests=args.validate_tests)

    # Skip unavailable coverage and exit immediately for test validation
    if args.validate_tests:
        exit(0 if all_test_success else 5)

    # Find coverage if required. Note, that the coverage server will be blocking
    if args.coverage:
        coverage_success = coverage()
        if not coverage_success:
            sys.exit(4)
        serve_coverage_forever("0.0.0.0", 8000)

if __name__ == "__main__":
    try:
        main()
    finally:
        print(RESET, end="")
        if sys.stdout.isatty():
            # This solves dodgy terminal behaviour on multithreading
            os.system("stty echo")
