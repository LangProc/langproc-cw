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
import threading
from collections.abc import Callable
from xml.sax.saxutils import escape as xmlescape, quoteattr as xmlquoteattr
from pathlib import Path
from functools import partial
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, SimpleHTTPRequestHandler


RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

COMPILER_NAME = "c_compiler"

if not sys.stdout.isatty():
    # Don't output colours when we're not in a TTY
    RED, GREEN, YELLOW, RESET = "", "", "", ""

class Result:
    """Class for keeping track of each test case result"""

    def __init__(self, test_case_name: str, return_code: int, timeout: bool, error_log: str | None):
        self._test_case_name = test_case_name
        self._return_code = return_code
        self._timeout = timeout
        self._error_log = error_log
        self._timeout = "[TIMED OUT] " if self._timeout else ""

    def passed(self) -> bool:
        return self._return_code == 0

    def to_xml(self) -> str:
        if self.passed():
            system_out = f"<system-out>{self._error_log}</system-out>\n" if self._error_log else ""
            return (
                f"<testcase name=\"{self._test_case_name}\">\n"
                f"{system_out}"
                f"</testcase>\n"
            )

        attribute = xmlquoteattr(self._timeout + self._error_log)
        xml_tag_body = xmlescape(self._timeout + self._error_log)
        return (
            f"<testcase name=\"{self._test_case_name}\">\n"
            f"<error type=\"error\" message={attribute}>\n{xml_tag_body}</error>\n"
            f"</testcase>\n"
        )

    def to_log(self) -> str:
        if self._return_code != 0:
            msg = f"{RED}{self._timeout + self._error_log}"
        elif self._error_log is None:
            msg = f"{GREEN}Pass"
        else:
            msg = f"{YELLOW}{self._error_log}"

        return f"{self._test_case_name}\n\t{msg}{RESET}\n"

class TestFailed(Exception):
    def __init__(self, result: Result):
        self.result = result
        super().__init__(str(result._error_log))

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
        self._lock = threading.Lock()

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

        frame = (
            "\033[2A"                                                                     # Move up 2 lines
            "\r\033[2K" + f"Running Tests [{progress_bar}]\n"                             # Clear + rewrite line 1
            "\r\033[2K" + f"{GREEN}Pass: {self.passed:2} | {RED}Fail: {self.failed:2} | "
            f"{RESET}Remaining: {remaining_tests:2}\n"                                    # Clear + rewrite line 2
        )

        # Write + flush on a single frame instead of 3 separate print(...) prevents a flickering visual glitch
        sys.stdout.write(frame)
        sys.stdout.flush()

    def update_with_value(self, passed: bool):
        if passed:
            self.passed += 1
        else:
            self.failed += 1

        # Lock prevents race conditions when multithreading is enabled
        with self._lock:
            self.update()

type subprocess_status = tuple[int, str, bool]

def run_subprocess(
    cmd: list[str],
    timeout: int,
    env: dict | None = None,
    log_path: str | None = None,
    verbose: bool = True,
) -> subprocess_status:
    """
    Wrapper for subprocess.run(...) with common arguments and error handling.

    Returns a tuple of (return_code: int, error_message: str, timed_out: bool)
    """
    timeout_returncode = 124

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
        return timeout_returncode, f"{e.cmd} took more than {e.timeout}", True
    return 0, "", False

def clean(top_dir: Path, timeout: int = 15) -> bool:
    """
    Wrapper for make clean.

    Return True if successful, False otherwise
    """
    print(f"{GREEN}Cleaning project...{RESET}")
    return_code, error_msg, _ = run_subprocess(
        cmd=["make", "-C", top_dir, "clean"],
        timeout=timeout,
        verbose=False,
    )

    if return_code != 0:
        print(f"{RED}Error when cleaning: {error_msg}{RESET}")
        return False
    return True

def make(top_dir: Path, build_dir: Path, multithreading: int, verbose: bool, log_path: str | None = None, timeout: int = 60) -> bool:
    """
    Wrapper for make build/c_compiler.

    Return True if successful, False otherwise
    """
    print(f"{GREEN}Running make...{RESET}")
    custom_env = os.environ.copy()
    custom_env["DEBUG"] = "1"

    cmd = ["make", "-C", str(top_dir)]
    if multithreading > 1:
        cmd += ["-j", str(multithreading)]
    cmd += [f"{build_dir.name}/{COMPILER_NAME}"]

    return_code, error_msg, _ = run_subprocess(
        cmd=cmd, timeout=timeout, verbose=verbose, env=custom_env, log_path=log_path
    )
    if return_code != 0:
        print(f"{RED}Error when running make: {error_msg}{RESET}")
        return False

    return True

def cmake(top_dir: Path, build_dir: Path, multithreading: int, verbose: bool, timeout: int = 60) -> bool:
    """
    Wrapper for cmake --build build

    Return True if successful, False otherwise
    """
    print(f"{GREEN}Running cmake...{RESET}")

    # cmake configure + generate
    # -DCMAKE_BUILD_TYPE=Release is equal to -O3
    return_code, error_msg, _ = run_subprocess(
        cmd=["cmake", "-S", top_dir, "-B", build_dir, "-DCMAKE_BUILD_TYPE=Release"],
        timeout=timeout,
        verbose=verbose
    )
    if return_code != 0:
        print(f"{RED}Error when running cmake (configure + generate): {error_msg}{RESET}")
        return False

    # cmake compile
    cmd = ["cmake", "--build", str(build_dir)]
    if multithreading > 1:
        cmd += ["--parallel", str(multithreading)]

    return_code, error_msg, _ = run_subprocess(
        cmd=cmd, timeout=timeout, verbose=verbose
    )
    if return_code != 0:
        print(f"{RED}Error when running cmake (compile): {error_msg}{RESET}")
        return False

    return True

def build(
    top_dir: Path,
    use_cmake: bool = False,
    coverage: bool = False,
    multithreading: int = 1,
    verbose: bool = True,
    timeout: int = 60
):
    """
    Wrapper for building the student compiler. Assumes output folder exists.

    Return True if successful, False otherwise
    """
    # Prepare the build folder
    build_dir = top_dir / "build"
    Path(build_dir).mkdir(parents=True, exist_ok=True)

    # Build the compiler using cmake or make
    if use_cmake and not coverage:
        build_success = cmake(top_dir, build_dir=build_dir, multithreading=multithreading, verbose=verbose, timeout=timeout)
    else:
        if use_cmake and coverage:
            print(f"{RED}Coverage is not supported with CMake. Switching to make.{RESET}")
        build_success = make(top_dir, build_dir=build_dir, multithreading=multithreading, verbose=verbose, timeout=timeout)

    return build_success

def coverage(top_dir: Path, timeout: int = 60) -> bool:
    """
    Wrapper for make coverage.

    Return True if successful, False otherwise
    """
    print(f"{GREEN}Running make coverage...{RESET}")
    custom_env = os.environ.copy()
    custom_env["DEBUG"] = "1"
    return_code, error_msg, _ = run_subprocess(
        cmd=["make", "-C", top_dir, "coverage"], timeout=timeout, verbose=False, env=custom_env
    )
    if return_code != 0:
        print(f"{RED}Error when running make coverage: {error_msg}{RESET}")
        return False
    return True

def serve_coverage_forever(root: Path, host: str, port: int):
    """
    Starts a HTTP server which serves the coverage folder forever until Ctrl+C
    is pressed.
    """
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, directory=None, **kwargs):
            super().__init__(*args, directory=root / "coverage", **kwargs)

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

    elif progress_bar:
        progress_bar.update_with_value(result.passed())

def run_test(
    compiler: Callable[[Path, Path, int], subprocess_status],
    output_dir: Path,
    tests_dir: Path,
    driver: Path,
    timeout: int = 30
) -> Result:
    """
    Run an instance of a test case.

    Parameters:
    - driver: driver path.

    Returns Result object
    """
    gcc = "riscv32-unknown-elf-gcc"
    # GCC is not targetting rv32imfd because it is compatible with rv32gc which is the more widespread 32bits target
    gcc_arch = "-march=rv32gc"
    gcc_abi = "-mabi=ilp32d"

    # Replaces example_driver.c -> example.c
    new_name = driver.stem.replace("_driver", "") + ".c"
    to_assemble = driver.parent.joinpath(new_name).resolve()
    test_name = to_assemble.relative_to(tests_dir)

    # Construct the path where logs would be stored, without the suffix
    # e.g. .../build/output/_example/example/example
    log_path = output_dir.joinpath(test_name.parent, to_assemble.stem, to_assemble.stem)

    # Recreate the directory
    shutil.rmtree(log_path.parent, ignore_errors=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def get_relevant_files(component: str):
        return "\n".join(f"\t{log_path}.{component}.{suffix}" for suffix in ["stderr.log", "stdout.log"])

    sanitizer_file_list = list(log_path.parent.glob(".*san.log.*"))
    compiler_log_file_str = "\n".join([
        get_relevant_files("compiler"),
        f"\t{log_path}.s",
        f"\t{log_path}.s.printed",
        *(f"\t{p}" for p in sanitizer_file_list),
    ])

    def get_msg(component: str):
        msg = f"{component.capitalize()} failed:\n{compiler_log_file_str}"
        if component != "compiler":
            msg += f"\n{get_relevant_files(component)}"
        return msg

    def fail(component: str, return_code: int, timed_out: bool):
        raise TestFailed(Result(
            test_case_name=test_name,
            return_code=return_code,
            timeout=timed_out,
            error_log=get_msg(component),
        ))

    def run_component(component: str, cmd: list[str]):
        return_code, _, timed_out = run_subprocess(
            cmd=cmd,
            timeout=timeout,
            log_path=f"{log_path}.{component}",
        )
        if return_code != 0:
            fail(component, return_code, timed_out)

    try:
        # GCC Reference Output
        run_component(
            component="reference",
            cmd=[gcc, "-std=c90", "-pedantic", "-ansi", "-O0", gcc_arch, gcc_abi, "-S", to_assemble, "-o", f"{log_path}.gcc.s"]
        )

        # Compile
        return_code, _, timed_out = compiler(to_assemble, log_path, timeout)
        if return_code != 0:
            fail("compiler", return_code, timed_out)

        # Assemble
        run_component(
            component="assembler",
            cmd=[gcc, gcc_arch, gcc_abi, "-c", f"{log_path}.s", "-o", f"{log_path}.o"]
        )

        # Link
        run_component(
            component="linker",
            cmd=[gcc, gcc_arch, gcc_abi, "-static", f"{log_path}.o", str(driver), "-o", f"{log_path}"]
        )

        # Simulate
        run_component(
            component="simulation",
            cmd=["spike", "--isa=rv32gc", "pk", log_path]
        )

    except TestFailed as e:
        return e.result

    msg = f"Sanitizer warnings: {" ".join(sanitizer_file_list)}" if len(sanitizer_file_list) != 0 else None
    return Result(test_case_name=test_name, return_code=0, timeout=False, error_log=msg)

def run_tests(
    compiler: Callable[[Path, Path, int], subprocess_status],
    output_dir: Path,
    tests_dir: Path,
    xml_file: JUnitXMLFile,
    multithreading: int,
    verbose: bool,
    timeout: int = 30
) -> tuple[int, int]:
    """
    Runs tests against compiler.

    Returns a tuple of (passing: int, total: int) tests
    """
    drivers = list(tests_dir.rglob("*_driver.c"))
    drivers = sorted(drivers, key=lambda p: (p.parent.name, p.name))
    results = []

    progress_bar = None
    if not verbose and sys.stdout.isatty():
        progress_bar = ProgressBar(len(drivers))
    else:
        # Force verbose mode when not a terminal
        verbose = True

    if multithreading > 1:
        with ThreadPoolExecutor(max_workers=multithreading) as executor:
            futures = [executor.submit(
                run_test,
                compiler=compiler,
                output_dir=output_dir,
                tests_dir=tests_dir,
                driver=driver,
                timeout=timeout
            ) for driver in drivers]

            for future in as_completed(futures):
                result = future.result()
                results.append(result.passed())
                process_result(result, xml_file, verbose, progress_bar)

    else:
        for driver in drivers:
            result = run_test(
                compiler=compiler,
                output_dir=output_dir,
                tests_dir=tests_dir,
                driver=driver,
                timeout=timeout
            )
            results.append(result.passed())
            process_result(result, xml_file, verbose, progress_bar)

    passing = sum(results)
    total = len(drivers)

    if verbose:
        print(f"\n>> Test Summary: {GREEN}{passing} Passed, {RED}{total-passing} Failed{RESET}")

    return passing, total

def student_compiler(compiler_path: Path, to_assemble: Path, log_path: Path, timeout: int) -> subprocess_status:
    """
    Wrapper for `build/c_compiler -S <input_test> -o <output_stem>.s`.

    Return None if successful, a Result otherwise
    """
    # Modifying environment to combat errors on memory leak
    custom_env = os.environ.copy()
    custom_env["ASAN_OPTIONS"] = f"log_path={log_path}.asan.log"
    custom_env["UBSAN_OPTIONS"] = f"log_path={log_path}.ubsan.log"

    # Compile
    return run_subprocess(
        cmd=[compiler_path, "-S", to_assemble, "-o", f"{log_path}.s"],
        timeout=timeout,
        env=custom_env,
        log_path=f"{log_path}.compiler",
    )

def symlink_reference_compiler(to_assemble: Path, log_path: Path, timeout: int) -> subprocess_status:
    Path(f"{log_path}.s").symlink_to(f"{log_path}.gcc.s")
    return 0, "", False

def parse_args(tests_dir: Path) -> argparse.Namespace:
    """
    Wrapper for argument parsing.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dir",
        nargs="?",
        default=tests_dir,
        type=Path,
        help="(Optional) paths to the compiler test folders. Use this to select "
        "certain tests. Leave blank to run all tests."
    )
    CPUs = os.cpu_count()
    parser.add_argument(
        "-m", "--multithreading",
        nargs="?",
        const=8 if CPUs is None else CPUs,
        default=1,
        type=int,
        metavar="N",
        help="Build compiler and run tests using multiple threads. "
        "Use -m to use the default thread count, or -m N to use exactly N threads. "
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
    root_dir = Path(__file__).resolve().parent
    build_dir = root_dir / "build"
    output_dir = build_dir / "output"

    args = parse_args(tests_dir=root_dir / "tests")

    # Clean the repo if required
    if not args.no_clean:
        clean_success = clean(top_dir=root_dir)
        if not clean_success:
            raise RuntimeError("Error when running make clean")

    # Prepare the output folder
    shutil.rmtree(output_dir, ignore_errors=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # There is no need for building the student compiler when testing with riscv-gcc
    if not args.validate_tests:
        build_success = build(
            top_dir=root_dir,
            use_cmake=args.use_cmake,
            coverage=args.coverage,
            multithreading=args.multithreading,
            verbose=not args.silent
        )
        if not build_success:
            raise RuntimeError("Error when building")

    # Run the tests and save the results into JUnit XML file
    with JUnitXMLFile(build_dir / "junit_results.xml") as xml_file:
        passing, total = run_tests(
            compiler=symlink_reference_compiler if args.validate_tests \
                else partial(student_compiler, build_dir / COMPILER_NAME),
            output_dir=output_dir,
            tests_dir=Path(args.dir),
            xml_file=xml_file,
            multithreading=args.multithreading,
            verbose=not args.silent
        )

    # Skip unavailable coverage and exit immediately for test validation
    if args.validate_tests:
        if passing != total:
            raise RuntimeError(f"{total - passing} tests failed during test validation")
        return

    # Find coverage if required. Note, that the coverage server will be blocking
    if args.coverage:
        coverage_success = coverage(top_dir=root_dir)
        if not coverage_success:
            raise RuntimeError("Error when running make coverage")
        serve_coverage_forever("0.0.0.0", 8000)

if __name__ == "__main__":
    try:
        main()
    finally:
        print(RESET, end="")
        if sys.stdout.isatty():
            # This solves dodgy terminal behaviour on multithreading
            os.system("stty echo")
