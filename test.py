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
import time
import re
import shutil
import subprocess
from statistics import mean
from enum import IntEnum
from contextlib import nullcontext, ExitStack
from dataclasses import dataclass
from collections.abc import Callable
from xml.sax.saxutils import escape as xmlescape, quoteattr as xmlquoteattr
from pathlib import Path
from functools import partial
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, SimpleHTTPRequestHandler
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Console

class Verbosity(IntEnum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2

class Reporter:
    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL):
        self.console = Console()
        self.verbosity = verbosity

    def _emit(self, message: str, style: str, min_verbosity: Verbosity):
        if self.verbosity >= min_verbosity:
            self.console.print(message, style=style, highlight=False)

    def debug(self, message: str, style: str = ""):
        self._emit(message, style, Verbosity.VERBOSE)

    def info(self, message: str, style: str = "green"):
        self._emit(message, style, Verbosity.NORMAL)

    def warning(self, message: str, style: str = "yellow"):
        self._emit(message, style, Verbosity.NORMAL)

    def error(self, message: str, style: str = "red"):
        self._emit(message, style, Verbosity.QUIET)

    def status(self, message: str, style: str = "cyan"):
        if self.verbosity < Verbosity.VERBOSE:
            return self.console.status(f"[{style}]{message}[/]" , spinner="dots")

        # For high verbosity (when other logs are printed as well), fall back to info(...)
        self.info(message, style=style)
        return nullcontext()

reporter = Reporter()

COMPILER_NAME = "c_compiler"
REFERENCE_COMPILER_NAME = "gcc_reference"
TIMEOUT_RETURNCODE = 124

@dataclass
class Result:
    """Class for keeping track of each test case result"""

    test_case_name: Path
    return_code: int
    error_log: tuple[str, str] | None
    stats: dict[str, int] | None = None

    def get_error_log(self) -> str | None:
        prefix = f"[TIMED OUT] " if self.return_code == TIMEOUT_RETURNCODE else ""
        return f"{prefix}{self.error_log[0]} failed:\n\t{self.error_log[1]}"

    @property
    def passed(self) -> bool:
        return self.return_code == 0

    def __str__(self) -> str:
        if self.error_log is None:
            msg = "Pass"
            color = "[green]"
        else:
            msg = self.get_error_log()
            color = "[red]" if self.return_code != 0 else "[yellow]"

        return f"{self.test_case_name}: {color}{msg}[/]"

class TestFailed(Exception):
    def __init__(
        self,
        component: str,
        test_name: Path,
        return_code: int,
        log_path: Path,
        sanitizer_files: list[Path]
    ):
        self._log_path = log_path

        details = self._get_relevant_log_files(component)

        if component != REFERENCE_COMPILER_NAME:
            details += [f"{self._log_path}.gcc.s"]

            if component != COMPILER_NAME:
                details += self._get_relevant_log_files(COMPILER_NAME)
                details += [f"{self._log_path}.s", f"{self._log_path}.s.printed"]

        self.result = Result(
            test_case_name=test_name,
            return_code=return_code,
            error_log=(component, "\n\t".join(details)),
        )

        super().__init__(self.result.get_error_log())

    def _get_relevant_log_files(self, component: str) -> list[str]:
        return [f"{self._log_path}.{component}.{suffix}" for suffix in ["stderr.log", "stdout.log"]]

class JUnitXMLFile():
    def __init__(self, path: Path):
        self._path = path
        self._fd = None

    def __enter__(self):
        self._fd = open(self._path, "w")
        self._fd.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        self._fd.write(f"<testsuite name={xmlquoteattr('Compiler benchmark')}>\n")
        return self

    def _write(self, msg: str) -> int:
        return self._fd.write(msg)

    def _write_testcase(self, test_case_name: str, body: str = "") -> int:
        name_attr = xmlquoteattr(str(test_case_name))
        return self._write(
            f"<testcase name={name_attr}>\n"
            f"{body}"
            f"</testcase>\n"
        )

    def write_result(self, result: Result) -> int:
        if result.passed:
            body = f"<system-out>{xmlescape(result.error_log)}</system-out>\n" if result.error_log else ""

        else:
            error_text = result.error_log[0]
            body = (
                f"<error type={xmlquoteattr('error')} message={xmlquoteattr(error_text)}>\n"
                f"{xmlescape(error_text)}</error>\n"
            )

        return self._write_testcase(result.test_case_name, body)

    def __exit__(self, *_):
        self._fd.write("</testsuite>\n")
        self._fd.close()

type subprocess_status = tuple[int, str]

def run_subprocess(
    cmd: list[str],
    log_path: str | None = None,
    verbose: bool = True,
    **kwargs
) -> subprocess_status:
    """
    Wrapper for `subprocess.run` with common arguments and error handling.

    Returns a tuple of (return_code: int, error_message: str)
    """
    with ExitStack() as stack:
        # None means that stdout and stderr are handled by parent, i.e., they go to console by default
        stdout = None
        stderr = None

        if not verbose:
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL
        elif log_path:
            stdout = stack.enter_context(open(f"{log_path}.stdout.log", "w"))
            stderr = stack.enter_context(open(f"{log_path}.stderr.log", "w"))

        try:
            subprocess.run(cmd, stdout=stdout, stderr=stderr, check=True, **kwargs)
        except subprocess.CalledProcessError as e:
            return e.returncode, f"{e.cmd} failed with return code {e.returncode}"
        except subprocess.TimeoutExpired as e:
            return TIMEOUT_RETURNCODE, f"{e.cmd} took more than {e.timeout}"

    return 0, ""

def clean(top_dir: Path, **kwargs) -> bool:
    """
    Wrapper for `make clean`.
    Additional arguments are passed to `run_subprocess`.

    Return True if successful, False otherwise
    """
    cmd = ["make", "-C", top_dir, "clean"]

    with reporter.status("Cleaning project..."):
        return_code, error_msg = run_subprocess(cmd=cmd, verbose=False, **kwargs)
    if return_code != 0:
        reporter.error(f"Error when cleaning: {error_msg}")
        return False
    return True

def make(top_dir: Path, build_dir: Path, multithreading: int, **kwargs) -> bool:
    """
    Wrapper for `make -j <multithreading> build/c_compiler`.
    Additional arguments are passed to `run_subprocess`.

    Return True if successful, False otherwise
    """
    verbose = reporter.verbosity >= Verbosity.VERBOSE

    custom_env = os.environ.copy()
    custom_env["DEBUG"] = "1"

    cmd = ["make", "-C", str(top_dir)]
    if multithreading > 1:
        cmd += ["-j", str(multithreading)]
    cmd += [f"{build_dir.name}/{COMPILER_NAME}"]

    with reporter.status("Building with make..."):
        return_code, error_msg = run_subprocess(cmd=cmd, env=custom_env, verbose=verbose, **kwargs)
    if return_code != 0:
        reporter.error(f"Error when running make: {error_msg}")
        return False

    return True

def cmake(top_dir: Path, build_dir: Path, multithreading: int, **kwargs) -> bool:
    """
    Wrapper for `cmake -S <top_dir> -B <build_dir> && cmake --parallel <multithreading> --build <build_dir>`.
    Additional arguments are passed to `run_subprocess`.

    Return True if successful, False otherwise
    """
    verbose = reporter.verbosity >= Verbosity.VERBOSE

    # cmake configure + generate
    # -DCMAKE_BUILD_TYPE=Release is equal to -O3
    cmd = ["cmake", "-S", top_dir, "-B", build_dir, "-DCMAKE_BUILD_TYPE=Release"]

    with reporter.status("Building (configure + generate) with cmake..."):
        return_code, error_msg = run_subprocess(cmd=cmd, verbose=verbose, **kwargs)
    if return_code != 0:
        reporter.error(f"Error when running cmake (configure + generate): {error_msg}")
        return False

    # cmake compile
    cmd = ["cmake", "--build", str(build_dir)]
    if multithreading > 1:
        cmd += ["--parallel", str(multithreading)]

    with reporter.status("Building (compile) with cmake..."):
        return_code, error_msg = run_subprocess(cmd=cmd, verbose=verbose, **kwargs)
    if return_code != 0:
        reporter.error(f"Error when running cmake (compile): {error_msg}")
        return False

    return True

def build(top_dir: Path, use_cmake: bool = False, coverage: bool = False, **kwargs) -> bool:
    """
    Wrapper for building the student compiler. Assumes output folder exists.
    `multithreading` is passed to `make` or `cmake`, the default value is used if absent.
    Additional arguments are passed to `run_subprocess`.

    Return True if successful, False otherwise
    """
    # Prepare the build folder
    build_dir = top_dir / "build"
    Path(build_dir).mkdir(parents=True, exist_ok=True)

    # Build the compiler using cmake or make
    if use_cmake and not coverage:
        return cmake(top_dir, build_dir=build_dir, **kwargs)

    if use_cmake and coverage:
        reporter.warning(f"Coverage is not supported with CMake. Switching to make.")
    return make(top_dir, build_dir=build_dir, **kwargs)

def coverage(top_dir: Path, **kwargs) -> bool:
    """
    Wrapper for `make coverage`.
    Additional arguments are passed to `run_subprocess`.

    Return True if successful, False otherwise
    """
    custom_env = os.environ.copy()
    custom_env["DEBUG"] = "1"

    cmd = ["make", "-C", top_dir, "coverage"]

    with reporter.status("Running make coverage..."):
        return_code, error_msg = run_subprocess(cmd=cmd, verbose=False, env=custom_env, **kwargs)
    if return_code != 0:
        reporter.error(f"Error when running make coverage: {error_msg}")
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
    try:
        with reporter.status(f"Serving coverage on http://{host}:{port}/ (Ctrl+C to exit)"):
            httpd.serve_forever()
    except KeyboardInterrupt:
        reporter.info("Server has been stopped!", style="red")

def get_compiler_stats(log_path: str, elapsed_time: int) -> dict[str, int]:
    """
    Measure compiler's performance using compile time, asm size and static instructions count
    """
    stats = {
        "compile_time": elapsed_time,
        "asm_size": Path(f"{log_path}.s").stat().st_size,
    }

    objdump_log = f"{log_path}.objdump"
    return_code, error_msg = run_subprocess(
        cmd=["riscv32-unknown-elf-objdump", "-d", f"{log_path}.o"],
        log_path=objdump_log
    )
    if return_code != 0:
        reporter.error(f"Error when running objdump: {error_msg}")
        return stats

    instruction_re = re.compile(r"^\s*[0-9a-f]+:\s+(?:[0-9a-f]{4}|[0-9a-f]{8})\s+")

    with Path(f"{objdump_log}.stdout.log").open("r", encoding="utf-8") as f:
        stats["static_instructions"] = sum(
            1
            for line in f
            if instruction_re.match(line)
        )

    return stats

def run_test(
    compiler: Callable[[Path, Path, int], subprocess_status],
    output_dir: Path,
    driver: Path,
    gather_stats: bool,
    **kwargs
) -> Result:
    """
    Run an instance of a test case whose driver is given by <driver>.
    The output of all the steps are put in <output_dir>.
    Additional arguments are passed to `compiler` and `run_subprocess`.

    Return Result object
    """
    gcc = "riscv32-unknown-elf-gcc"
    # GCC is not targetting rv32imfd because it is compatible with rv32gc which is the more widespread 32bits target
    gcc_arch = "-march=rv32gc"
    gcc_abi = "-mabi=ilp32d"

    # Replaces example_driver.c -> example.c
    new_name = driver.stem.replace("_driver", "") + ".c"
    to_assemble = driver.parent.joinpath(new_name).resolve()
    cwd = Path.cwd()
    test_name = to_assemble.relative_to(cwd) if to_assemble.is_relative_to(cwd) else to_assemble

    # Construct the path where logs would be stored, without the suffix
    # e.g. .../build/output/_example/example/example
    log_path = output_dir.joinpath(test_name.parent, to_assemble.stem, to_assemble.stem)

    # Recreate the directory
    shutil.rmtree(log_path.parent, ignore_errors=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    sanitizer_files = list(log_path.parent.glob(".*san.log.*"))

    def fail(component: str, return_code: int):
        raise TestFailed(
            component=component,
            test_name=test_name,
            return_code=return_code,
            log_path=log_path,
            sanitizer_files=sanitizer_files
        )

    def run_component(component: str, cmd: list[str]):
        return_code, _ = run_subprocess(
            cmd=cmd,
            log_path=f"{log_path}.{component}",
            **kwargs
        )
        if return_code != 0:
            fail(component, return_code)

    try:
        # GCC Reference Output
        run_component(
            component=REFERENCE_COMPILER_NAME,
            cmd=[gcc, "-std=c90", "-pedantic", "-ansi", "-O0", gcc_arch, gcc_abi, "-S", to_assemble, "-o", f"{log_path}.gcc.s"]
        )

        # Compile
        start_time = time.perf_counter()
        return_code, _ = compiler(to_assemble, log_path, **kwargs)
        elapsed_time = time.perf_counter() - start_time
        if return_code != 0:
            fail(COMPILER_NAME, return_code)

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

    compiler_stats = get_compiler_stats(log_path=log_path, elapsed_time=elapsed_time) if gather_stats else None

    msg = f"Sanitizer warnings: {" ".join(sanitizer_files)}" if len(sanitizer_files) != 0 else None
    return Result(test_case_name=test_name, return_code=0, error_log=msg, stats=compiler_stats)

def run_tests(
    tests_dir: Path,
    xml_file: JUnitXMLFile,
    multithreading: int,
    gather_stats: bool,
    **kwargs
) -> tuple[int, int]:
    """
    Runs tests is <tests_dir> against compiler provided by <compiler> and puts output inside <output_dir>.
    Arguments `compiler` and `output_dir` are mandatory and are passed to `run_test`.
    Additional arguments are passed to `compiler` and `run_subprocess`.

    Returns a tuple of (passing: int, total: int) tests
    """
    drivers = list(tests_dir.rglob("*_driver.c"))
    drivers = sorted(drivers, key=lambda p: (p.parent.name, p.name))

    passed = failed = 0
    compiler_stats = [] if gather_stats else None

    with Progress(
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        BarColumn(bar_width=None),
        TextColumn(
            "[green]passed={task.fields[passed]}[/], "
            "[red]failed={task.fields[failed]}[/], "
            "{task.fields[rate]:.2f} test/s"
        ),
        console=reporter.console,
        transient=True,
        disable=not sys.stdout.isatty(),
    ) as progress, ThreadPoolExecutor(max_workers=multithreading) as executor:
        task_id = progress.add_task(
            "tests",
            total=len(drivers),
            passed=0,
            failed=0,
            rate=0.0,
        )

        futures = [
            executor.submit(run_test, driver=driver, gather_stats=gather_stats, **kwargs)
            for driver in drivers
        ]

        for future in as_completed(futures):
            result = future.result()
            xml_file.write_result(result)

            if result.passed:
                passed += 1
                if gather_stats:
                    compiler_stats.append(result.stats)
            else:
                failed += 1

            elapsed = progress.tasks[task_id].elapsed or 0.0
            rate = (passed + failed) / elapsed if elapsed > 0 else 0.0

            progress.update(
                task_id,
                advance=1,
                passed=passed,
                failed=failed,
                rate=rate,
            )

            reporter.debug(f"{result}\n")

    assert len(drivers) == passed + failed, f"Mismatch between total tests and processed results"

    reporter.info(f"[bold]Passed {passed}/{passed + failed} found test cases[/]")

    if compiler_stats:
        assert len(compiler_stats) == passed, "Some compiler stats could not be collected"

        avg_compile_time_ms = 1000.0 * mean(s["compile_time"] for s in compiler_stats)
        avg_asm_size_bytes = mean(s["asm_size"] for s in compiler_stats)
        avg_static_instructions = mean(s["static_instructions"] for s in compiler_stats)

        reporter.info(
            f"[bold]Measured averages:[/] "
            f"compile time = [bold]{avg_compile_time_ms:.3f} ms[/], "
            f"asm size = [bold]{avg_asm_size_bytes:.1f} B[/], "
            f"static instructions = [bold]{avg_static_instructions:.1f}[/]"
        )

    return (passed, passed + failed)

def student_compiler(
    compiler_path: Path,
    to_assemble: Path,
    log_path: Path,
    **kwargs
) -> subprocess_status:
    """
    Wrapper for `build/c_compiler -S <input_test> -o <output_stem>.s`.
    Additional arguments are passed to `run_subprocess`.

    Return None if successful, a Result otherwise
    """
    # Modifying environment to combat errors on memory leak
    custom_env = os.environ.copy()
    custom_env["ASAN_OPTIONS"] = f"log_path={log_path}.asan.log"
    custom_env["UBSAN_OPTIONS"] = f"log_path={log_path}.ubsan.log"

    # Compile
    cmd = [compiler_path, "-S", to_assemble, "-o", f"{log_path}.s"]
    return run_subprocess(cmd=cmd, env=custom_env, log_path=f"{log_path}.{COMPILER_NAME}", **kwargs)

def symlink_reference_compiler(to_assemble: Path, log_path: Path, **kwargs) -> subprocess_status:
    """
    Symlinks the result of riscv-gcc as its own result.
    It isn't really a compiler but can be passed as a compiler function to use the result of
    riscv-gcc as the output of the compiler, thus testing the ability of riscv-gcc to pass tests.

    Never fails.
    """
    Path(f"{log_path}.s").symlink_to(f"{log_path}.gcc.s")
    return 0, ""

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
        "--gather_stats",
        action="store_true",
        default=False,
        help="Gather compiler related statistics like compile time, asm file size, "
        "static instructions count, dynamic instructions count."
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

if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent
    build_dir = root_dir / "build"
    output_dir = build_dir / "output"

    args = parse_args(tests_dir=root_dir / "tests")

    reporter.verbosity = Verbosity.NORMAL if args.silent else Verbosity.VERBOSE

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
            multithreading=args.multithreading
        )
        if not build_success:
            raise RuntimeError("Error when building")

    # Run the tests and save the results into JUnit XML file
    with JUnitXMLFile(build_dir / "junit_results.xml") as xml_file:
        passing, total = run_tests(
            tests_dir=Path(args.dir),
            xml_file=xml_file,
            multithreading=args.multithreading,
            gather_stats=args.gather_stats,
            compiler=symlink_reference_compiler if args.validate_tests \
                else partial(student_compiler, build_dir / COMPILER_NAME),
            output_dir=output_dir
        )

    # Skip unavailable coverage and exit immediately for test validation
    if args.validate_tests:
        if passing != total:
            raise RuntimeError(f"{total - passing} tests failed during test validation")

    # Find coverage if required. Note, that the coverage server will be blocking
    elif args.coverage:
        coverage_success = coverage(top_dir=root_dir)
        if not coverage_success:
            raise RuntimeError("Error when running make coverage")
        serve_coverage_forever(root_dir, "0.0.0.0", 8000)
