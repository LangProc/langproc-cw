#!/usr/bin/env python3

"""
A wrapper script to run all the compiler tests. This script will call the
Makefile, run the tests and store the outputs in build/output.

Usage: ./test.py [-h] [-m] [-s] [--version] [--clean] [--optimise] [--generate_report] [--validate_tests] [dir]

Example usage for all tests: ./test.py

Example usage for tests in a directory: ./test.py tests/_example

This will print out a progress bar and only run the example tests.
The output would be placed into build/output/_example/example/.

For more information, run ./test.py --help
"""

__version__ = "1.0.0"
__author__ = "William Huynh, Filip Wojcicki, James Nock, Quentin Corradi"


import shlex
import subprocess
import xml.sax.saxutils as xml
from os import environ, cpu_count
from sys import stdout, exit
from shutil import rmtree
from pathlib import Path
from argparse import ArgumentParser, Namespace
from enum import IntEnum, Enum
from typing import NamedTuple
from functools import partial
from contextlib import nullcontext, ExitStack
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.markup import escape as rich_escape
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn

BUILD_DIR_NAME = "build"
OUTPUT_DIR_NAME = "output"

class TestStep(NamedTuple):
    suffix: str
    action: str

class Component(Enum):
    REFERENCE_COMPILER = TestStep(suffix="gcc_reference", action="Generating reference assembly")
    COMPILER = TestStep(suffix="c_compiler", action="Compiling")
    ASSEMBLER = TestStep(suffix="assembler", action="Assembling")
    LINKER = TestStep(suffix="linker", action="Linking")
    SIMULATION = TestStep(suffix="simulation", action="Simulating")

class Verbosity(IntEnum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3

class Reporter:
    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL):
        self.console = Console()
        self.verbosity = verbosity

    def _emit(self, message: str, style: str, min_verbosity: Verbosity):
        if self.verbosity >= min_verbosity:
            self.console.print(message, style=style, highlight=False)

    def debug(self, message: str, style: str = ""):
        self._emit(message, style, Verbosity.DEBUG)

    def info(self, message: str, style: str = "cyan"):
        self._emit(message, style, Verbosity.NORMAL)

    def warning(self, message: str, style: str = "yellow"):
        self._emit(message, style, Verbosity.NORMAL)

    def error(self, message: str, style: str = "red"):
        self._emit(message, style, Verbosity.QUIET)

    def status(self, message: str, style: str = "cyan"):
        message = f"{message}..."
        if self.verbosity < Verbosity.VERBOSE:
            styled_message = message if style == "" else f"[{style}]{message}[/]"
            return self.console.status(styled_message, spinner="dots")

        # For high verbosity (when other logs are printed as well), fall back to info(...)
        self.info(message, style=style)
        return nullcontext()

reporter = Reporter()

def get_relative_path(path: Path) -> str:
    cwd = Path().resolve()
    return str(path.relative_to(cwd)) if path.is_relative_to(cwd) else str(path)

class ProcessOutput:
    """
    An error message with a list of relevant files
    """
    def __init__(self, short_message: str | None = None, files: list[Path] | None = None):
        self._short_message = short_message
        self._files = files or []

    @property
    def succeded(self) -> bool:
        return self._short_message is None

    @property
    def failed(self) -> bool:
        return self._short_message is not None

    def add_file(self, file: Path):
        self._files.append(file)

    def add_files(self, files: Iterator[Path]):
        self._files.extend(files)

    def get_short_message(self) -> str | None:
        return self._short_message

    def prefix_short_message(self, prefix: str):
        self._short_message = prefix if self._short_message is None \
            else f"{prefix} {self._short_message}"

    def get_message_with_file_list(self) -> str | None:
        if self.succeded:
            return None

        log_parts = [self._short_message, ", see:\n"]
        for file in self._files:
            log_parts.append("\t")
            log_parts.append(get_relative_path(file))
            log_parts.append("\n")
        return ''.join(log_parts)

    def get_message_with_file_content(self) -> str | None:
        if self.succeded:
            return None

        log_parts = [self._short_message, ".\n"]
        for file in self._files:
            log_parts.append(get_relative_path(file))
            log_parts.append(":\n")
            log_parts.append(file.read_text())
            log_parts.append("\n")
        return ''.join(log_parts)

class JUnitXMLFile():
    def __init__(self, path: Path):
        self._path = path
        self._fd = None

    def __enter__(self):
        self._fd = open(self._path, "w")
        self._fd.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        self._fd.write(f"<testsuite name={xml.quoteattr('Compiler benchmark')}>\n")
        return self

    def _write(self, msg: str):
        self._fd.write(msg)

    def _write_testcase(self, test_file: Path, body: str = ""):
        self._write(
            f"<testcase name={xml.quoteattr(str(test_file))}>\n"
            f"{body}</testcase>\n"
        )

    def write_result(self, test_file: Path, result: ProcessOutput):
        self._write_testcase(test_file, "" if result.succeded else \
            f"<error type={xml.quoteattr('error')} message={xml.quoteattr(result.get_short_message())}>\n"
            f"{xml.escape(result.get_message_with_file_content())}</error>\n"
        )

    def __exit__(self, *_):
        self._fd.write("</testsuite>\n")
        self._fd.close()

def stem_add_suffix(stem: Path, suffix: str) -> Path:
    return stem.with_name(f"{stem.name}.{suffix}")

def run_subprocess(
    cmd: list[str],
    action: str,
    log_stem: Path | None = None,
    verbose: bool = True,
    **kwargs
) -> ProcessOutput:
    """
    Wrapper for `subprocess.run` with common arguments and error handling.

    Returns a ProcessOutput
    """
    with ExitStack() as stack:
        if not verbose:
            files = []
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL
        elif log_stem is not None:
            files = [stem_add_suffix(log_stem, "stdout.log"), stem_add_suffix(log_stem, "stderr.log")]
            stdout = stack.enter_context(files[0].open(mode="w"))
            stderr = stack.enter_context(files[1].open(mode="w"))
        else: # Verbose and no log: print to terminal
            files = []
            stdout = None
            stderr = None

        try:
            subprocess.run(cmd, stdout=stdout, stderr=stderr, check=True, **kwargs)
            return ProcessOutput()
        except subprocess.SubprocessError as e:
            # Cleans command line by shortening paths and removing ccache (compiler output caching)
            cmdlist = e.cmd if e.cmd[0] != "cache" else e.cmd[1:]
            cmd = shlex.join(get_relative_path(x) if isinstance(x, Path) else x for x in cmdlist)
            return ProcessOutput(short_message=f"Error when {action.lower()}.\nCommand `{cmd}` failed", files=files)

def clean(top_dir: Path, **kwargs) -> bool:
    """
    Wrapper for `make clean`.
    Additional arguments are passed to `run_subprocess`.

    Returns True if successful, False otherwise
    """
    action = "Cleaning project"
    cmd = ["make", "-C", top_dir, "clean"]
    with reporter.status(action):
        status = run_subprocess(action=action, cmd=cmd, verbose=False, **kwargs)
    if status.failed:
        reporter.error(status.get_short_message())
    return status.succeded

def build(top_dir: Path, multithreading: int, optimise: bool = False, **kwargs) -> bool:
    """
    Wrapper for `make -j <multithreading> (N)DEBUG=1 build/c_compiler`.
    Additional arguments are passed to `run_subprocess`.

    Returns True if successful, False otherwise
    """
    action = "Building compiler"
    Path(top_dir / BUILD_DIR_NAME).mkdir(parents=True, exist_ok=True)
    verbose = reporter.verbosity >= Verbosity.VERBOSE

    cmd = [
        "make",
        f"{'N' if optimise else ''}DEBUG=1",
        "-j", str(multithreading),
        "-C", top_dir,
        f"{BUILD_DIR_NAME}/{Component.COMPILER.value.suffix}"
    ]
    with reporter.status(action):
        status = run_subprocess(cmd=cmd, action=action, verbose=verbose, **kwargs)
    if status.failed:
        reporter.error(status.get_short_message())
    return status.succeded

def coverage(top_dir: Path, **kwargs) -> bool:
    """
    Wrapper for `make coverage`.
    Additional arguments are passed to `run_subprocess`.

    Returns True if successful, False otherwise
    """
    action = "Processing coverage data"
    cmd = ["make", "DEBUG=1", "-C", top_dir, "coverage"]
    verbose = reporter.verbosity >= Verbosity.DEBUG

    with reporter.status(action):
        status = run_subprocess(cmd=cmd, action=action, verbose=verbose, **kwargs)
    if status.failed:
        reporter.error(status.get_short_message())
    return status.succeded

def run_component(
    component: Component,
    cmd: list[str],
    log_stem: Path,
    **kwargs
) -> ProcessOutput:
    """
    Runs one step of testing the compiler against a single test file, then links additional output files.

    Returns a ProcessOutput
    """
    status = run_subprocess(
        cmd=cmd,
        action=component.value.action,
        log_stem=stem_add_suffix(log_stem, component.value.suffix),
        **kwargs
    )
    # All passes after student compiler (so just not reference compiler) should add files to refer to
    # I tried to link them in the order students should inspect them
    # If the compiler succeded and a futher component failed, it is likely caused by the compiler
    # so we should link the compiler outputs, in particular the produced assembly (treated specially, see below)
    if status.failed and component is not Component.REFERENCE_COMPILER:
        # If the compiler output is present add it with the reference to compare to;
        # if the compiler failed we don't expect it but link it if present,
        # otherwise it's probably the reason of the failure, so it's worth mentioning first in the error message
        compiler_assembly = stem_add_suffix(log_stem, "s")
        if component is Component.COMPILER:
            if compiler_assembly.is_file():
                status.add_file(compiler_assembly)
            # Don't link it if it failed, don't need to duplicate link std(out/err)
        else:
            compiler_stem = stem_add_suffix(log_stem, Component.COMPILER.value.suffix)
            status.add_files([
                stem_add_suffix(compiler_stem, "stdout.log"),
                stem_add_suffix(compiler_stem, "stderr.log")
            ])
            if compiler_assembly.is_file():
                status.add_file(compiler_assembly)
            else:
                status.prefix_short_message("[compiler output missing]")

        # the .s.printed is not required but likely produced so we optionally link it
        printed_assembly = stem_add_suffix(compiler_assembly, "printed")
        if printed_assembly.is_file():
            status.add_file(printed_assembly)
        # No point in comparing assembly with gcc if the student compiler did not generate it
        if compiler_assembly.is_file():
            status.add_file(stem_add_suffix(log_stem, "gcc.s"))
        for file in log_stem.parent.glob(".*san.log.*"):
            status.add_file(file)
    return status

def test_from_driver(driver_file: Path) -> Path:
    return driver_file.with_stem(driver_file.stem.removesuffix("_driver"))

def run_test(
    compiler: Callable[[Path, Path, int], ProcessOutput],
    output_dir: Path,
    driver_file: Path,
    **kwargs
) -> ProcessOutput:
    """
    Run an instance of a test case whose driver is given by `driver_file`.
    The output of all the steps are put in `output_dir`.
    Additional arguments are passed to `compiler` and `run_subprocess`.

    Returns the ProcessOutput of the failing step,
        a failing ProcessOutput if every step succeeds but there are sanitizer warnings,
        or a succeding ProcessOuput
    """
    # Replaces example_driver.c -> example.c
    test_file = test_from_driver(driver_file)
    if not test_file.is_file():
        raise FileNotFoundError(
            f"Test driver `{get_relative_path(driver_file)}` doesn't have"
            f"an associated test file ({get_relative_path(test_file)})"
        )

    # Construct the stem to use for output files, so the path without the suffix
    # e.g. .../build/output/_example/example/example
    output_stem = output_dir.joinpath(test_file.parent.name, test_file.stem, test_file.stem)

    # Recreate the directory
    rmtree(output_stem.parent, ignore_errors=True)
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    # GCC is not targetting rv32imfd (base target of the course) because:
    # rv32imfd is compatible with rv32gc and the C extension is a part of extended goals
    isa = "rv32gc"
    gcc_cmd = ["ccache", "riscv32-unknown-elf-gcc", f"-march={isa}", "-mabi=ilp32d"]

    # GCC Reference Output
    status = run_component(
        component=Component.REFERENCE_COMPILER,
        cmd=gcc_cmd + ["-std=c90", "-pedantic", "-ansi", "-O0", "-S", test_file, "-o", stem_add_suffix(output_stem, "gcc.s")],
        log_stem=output_stem
    )
    if status.failed:
        return status

    # Compile
    status = compiler(test_file, output_stem, **kwargs)
    if status.failed:
        return status

    # Assemble
    status = run_component(
        component=Component.ASSEMBLER,
        cmd=gcc_cmd + ["-c", stem_add_suffix(output_stem, "s"), "-o", stem_add_suffix(output_stem, "o")],
        log_stem=output_stem
    )
    if status.failed:
        return status

    # Link
    status = run_component(
        component=Component.LINKER,
        cmd=gcc_cmd + ["-static", stem_add_suffix(output_stem, "o"), driver_file, "-o", output_stem],
        log_stem=output_stem
    )
    if status.failed:
        return status

    # Simulate
    status = run_component(
        component=Component.SIMULATION,
        cmd=["spike", f"--isa={isa}", "pk", output_stem],
        log_stem=output_stem
    )
    if status.failed:
        return status

    sanitizer_files = list(output_stem.parent.glob(".*san.log.*"))
    if len(sanitizer_files) != 0:
        return ProcessOutput(short_message="Sanitizer warnings.", files=sanitizer_files)

    return ProcessOutput()

def run_tests(
    tests_dir: Path,
    report: JUnitXMLFile | None,
    multithreading: int,
    **kwargs
) -> tuple[int, int]:
    """
    Runs tests is <tests_dir> against compiler provided by <compiler> and puts output inside <output_dir>.
    Arguments `compiler` and `output_dir` are mandatory and are passed to `run_test`.
    Additional arguments are passed to `compiler` and `run_subprocess`.

    Returns a tuple of (passing: int, total: int) tests
    """
    drivers = sorted(tests_dir.rglob("*_driver.c"), key=lambda p: p.parts[-2:])
    passed = failed = 0

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
        disable=not stdout.isatty(),
    ) as progress, ThreadPoolExecutor(max_workers=multithreading) as executor:
        task_id = progress.add_task(
            "tests",
            total=len(drivers),
            passed=0,
            failed=0,
            rate=0.0,
        )

        job_to_driver = {
            executor.submit(run_test, driver_file=driver, **kwargs): driver
            for driver in drivers
        }
        for job in as_completed(job_to_driver):
            driver = job_to_driver[job]
            test_file = get_relative_path(test_from_driver(driver))
            status = job.result()
            if report is not None:
                report.write_result(test_file=test_file, result=status)

            if status.succeded:
                passed += 1
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

            if status.failed:
                reporter.info(rich_escape(f"{test_file}: {status.get_message_with_file_list()}"), style="red")

    assert len(drivers) == passed + failed, \
        f"Mismatch in number of tests with status ({passed} passed, {failed} failed, {len(drivers)} found)"
    return passed, passed + failed

def student_compiler(compiler_path: Path, input_file: Path, log_stem: Path, **kwargs) -> ProcessOutput:
    """
    Wrapper for `build/c_compiler -S <input_file> -o <log_stem>.s`.
    Additional arguments are passed to `run_subprocess`.

    Returns a ProcessOutput
    """
    # Modifying environment to combat errors on memory leak
    custom_env = environ.copy()
    custom_env["ASAN_OPTIONS"] = f"log_path={log_stem}.asan.log"
    custom_env["UBSAN_OPTIONS"] = f"log_path={log_stem}.ubsan.log"

    # Compile
    cmd = [compiler_path, "-S", input_file, "-o", stem_add_suffix(log_stem, "s")]
    return run_component(component=Component.COMPILER, cmd=cmd, env=custom_env, log_stem=log_stem, **kwargs)

def symlink_reference_compiler(_input_file: Path, log_stem: Path, **kwargs) -> ProcessOutput:
    """
    Symlinks the result of riscv-gcc as its own result.
    It isn't really a compiler but can be passed as a compiler function to use the result of
    riscv-gcc as the output of the compiler, thus testing the ability of riscv-gcc to pass tests.

    Never fails.
    """
    stem_add_suffix(log_stem, "s").symlink_to(stem_add_suffix(log_stem, "gcc.s"))
    return ProcessOutput()

def parse_args(tests_dir: Path) -> Namespace:
    """
    Wrapper for argument parsing.
    """
    parser = ArgumentParser()
    parser.add_argument(
        "dir",
        nargs="?",
        default=tests_dir,
        type=Path,
        help="(Optional) paths to the compiler test folders. Use this to select certain tests. "
        "Leave blank to run all tests."
    )
    parser.add_argument(
        "-m", "--multithreading",
        nargs="?",
        const=cpu_count() or 8,
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
        "--clean",
        action="store_true",
        default=False,
        help="Clean the repository before testing. This will make it slower "
        "but it can solve some compilation issues when source files are deleted."
    )
    parser.add_argument(
        "--optimise",
        action="store_true",
        default=False,
        help="Optimise the compiler for speed, at the cost building time and debugging."
    )
    parser.add_argument(
        "--generate_report",
        action="store_true",
        default=False,
        help="Generate a JUnit report to use as a test summary for CI/CD."
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
    build_dir = root_dir / BUILD_DIR_NAME
    output_dir = build_dir / OUTPUT_DIR_NAME

    args = parse_args(tests_dir=root_dir / "tests")

    reporter.verbosity = Verbosity.NORMAL if args.silent else Verbosity.VERBOSE

    # Clean the repo if required
    if args.clean:
        clean_success = clean(top_dir=root_dir)
        if not clean_success:
            raise RuntimeError("Error when running make clean")

    # Prepare the output folder
    rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # There is no need for building the student compiler when testing with riscv-gcc
    if not args.validate_tests:
        build_success = build(
            top_dir=root_dir,
            multithreading=args.multithreading,
            optimise=args.optimise
        )
        if not build_success:
            raise RuntimeError("Error when building")

    # Run the tests and save the results into JUnit XML file
    with ExitStack() as stack:
        report = stack.enter_context(JUnitXMLFile(build_dir / "junit_results.xml")) \
            if args.generate_report else None
        passing, total = run_tests(
            tests_dir=args.dir,
            report=report,
            multithreading=args.multithreading,
            compiler=symlink_reference_compiler if args.validate_tests \
                else partial(student_compiler, build_dir / Component.COMPILER.value.suffix),
            output_dir=output_dir
        )

    # Skip unavailable coverage and exit immediately for test validation
    if args.validate_tests:
        if passing != total:
            raise RuntimeError(f"{total - passing} tests failed during test validation")
        exit()

    # No coverage for optimised builds
    if not args.optimise:
        coverage_success = coverage(top_dir=root_dir)
        if not coverage_success:
            raise RuntimeError("Error when running make coverage")

        external_root = Path(environ["LOCALPWD"]) if "LOCALPWD" in environ else root_dir
        coverage_index = external_root.joinpath("coverage/index.html")
        reporter.info(
            f"Check detailed coverage at [link=file://{coverage_index}]coverage/index.html[/] "
            "(open in a web browser or in vscode using Ctrl+P >workbench.action.browser.open)\n"
        )

    reporter.info(f"[bold]Passed {passing}/{total} found test cases[/]")
