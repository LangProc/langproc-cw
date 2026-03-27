#!/usr/bin/env python3

"""
A wrapper script to run all the compiler tests. This script will call the
Makefile, run the tests and store the outputs in build/output.

Usage: ./test.py [-h] [-j] [-s] [--version] [--clean] [--optimise] [--generate_report] [--validate_tests] [dir]

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
from signal import Signals, valid_signals, strsignal
from shutil import rmtree, move
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
    name: str
    action: str

class Component(Enum):
    REFERENCE = TestStep(name="gcc_reference", action="Generating reference assembly")
    COMPILER = TestStep(name="c_compiler", action="Compiling")
    ASSEMBLER = TestStep(name="assembler", action="Assembling")
    LINKER = TestStep(name="linker", action="Linking")
    SIMULATION = TestStep(name="simulation", action="Simulating")

class Verbosity(IntEnum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3

class BuildStep(NamedTuple):
    name: str
    action: str
    verbosity: Verbosity

class MakeRule(Enum):
    CLEAN = BuildStep(name="clean", action="Cleaning project", verbosity=Verbosity.DEBUG)
    COMPILER = BuildStep(
        name=f"{BUILD_DIR_NAME}/{Component.COMPILER.value.name}",
        action="Building compiler",
        verbosity=Verbosity.NORMAL
    )
    COVERAGE = BuildStep(
        name="coverage",
        action="Processing coverage data",
        verbosity=Verbosity.DEBUG
    )

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

    def status(self, message: str, style: str = "cyan", verbosity: Verbosity = Verbosity.VERBOSE):
        message = f"{message}..."
        if verbosity < self.verbosity:
            styled_message = message if style == "" else f"[{style}]{message}[/]"
            return self.console.status(styled_message, spinner="dots")

        # For high verbosity (when other logs are printed as well), fall back to info(...)
        self.info(message, style=style)
        return nullcontext()

reporter = Reporter()

def error_kind_from_code(code: int) -> str:
    """Describes an exit code."""
    if code < 0 and -code in valid_singals():
        return f"Process ended by {strsignal(-code).lower() or 'unknown signal'} {Signals(-code)}"
    if code == 124:
        return "Timeout"
    if code != 0:
        return "Error"
    return "Success"

def build_step(
    step: BuildStep,
    root_dir: Path,
    jobs: int = 1,
    optimise: bool = False,
    **kwargs
) -> bool:
    """
    Wrapper for `make <step.name>`.

    Returns True if successful, False otherwise.
    """
    quiet = step.verbosity > reporter.verbosity
    cmd = [
        "make",
        f"-j{jobs}",
        "-s" if quiet else "-Oline",
        "-C", root_dir,
        f"{'N' if optimise else ''}DEBUG=1",
        step.name
    ]
    stdout, stderr = (subprocess.DEVNULL, subprocess.DEVNULL) if quiet else (None, None)

    with reporter.status(step.action, verbosity=step.verbosity):
        code = subprocess.run(cmd, stdout=stdout, stderr=stderr, **kwargs).returncode

    if code == 0:
        return True

    # Clean version of the command for students to quickly retry the failing step
    cmd = shlex.join(["make"] + cmd[-2:])
    reporter.error(f"{error_kind_from_code(code)} when {step.action.lower()} with `{cmd}`.")

    return False

def get_relative_path(path: Path) -> str:
    """Converts an absolute path to a relative path for printing."""
    cwd = Path().resolve()
    return str(path.relative_to(cwd)) if path.is_relative_to(cwd) else str(path)

class TestError:
    """An error message with a list of relevant files."""
    def __init__(self, short_message: str, files: list[Path]):
        self._short_message = short_message
        self._files = files

    def get_short_message(self) -> str:
        return self._short_message

    def get_message_with_file_list(self) -> str:
        log_parts = [self._short_message, ", see:\n"]
        for file in self._files:
            log_parts.append("\t")
            log_parts.append(get_relative_path(file))
            log_parts.append("\n")
        return ''.join(log_parts)

    def get_message_with_file_content(self) -> str:
        log_parts = [self._short_message, ".\n"]
        for file in self._files:
            log_parts.append(get_relative_path(file))
            log_parts.append(":\n")
            log_parts.append(file.read_text())
            log_parts.append("\n")
        return ''.join(log_parts)

def stem_add_suffix(stem: Path, suffix: str) -> Path:
    """Adds a dot then `suffix` to a Path."""
    return stem.with_name(f"{stem.name}.{suffix}")

def run_component(
    component: Component,
    cmd: list[str | Path],
    log_stem: Path,
    **kwargs
) -> TestError | None:
    """
    Runs one step of testing the compiler against a single test file, then links additional output files.

    Returns None if successful, a TestError otherwise.
    """
    new_log_stem = stem_add_suffix(log_stem, component.value.name)
    files = [stem_add_suffix(new_log_stem, "stdout.log"), stem_add_suffix(new_log_stem, "stderr.log")]
    with files[0].open(mode="w") as stdout, files[1].open(mode="w") as stderr:
        code = subprocess.run(cmd, stdout=stdout, stderr=stderr, **kwargs).returncode

    if code == 0:
        return None

    error_kind = error_kind_from_code(code)
    # All passes after student compiler (so just not reference compiler) should add files to refer to
    # I tried to link them in the order students should inspect them
    # If the compiler succeded and a futher component failed, it is likely caused by the compiler
    # so we should link the compiler outputs, in particular the produced assembly (see below)
    if component is not Component.REFERENCE:
        # If the compiler output is present add it with the reference to compare to;
        # if the compiler failed we don't expect it but link it if present,
        # otherwise it's probably the reason of the failure,
        # so it's worth mentioning first in the error message
        compiler_assembly = stem_add_suffix(log_stem, "s")
        if component is Component.COMPILER:
            if compiler_assembly.is_file():
                files.append(compiler_assembly)
            # Don't link it if it failed, don't need to duplicate link std(out/err)
        else:
            compiler_stem = stem_add_suffix(log_stem, Component.COMPILER.value.name)
            files.extend([
                stem_add_suffix(compiler_stem, "stdout.log"),
                stem_add_suffix(compiler_stem, "stderr.log")
            ])
            if compiler_assembly.is_file():
                files.append(compiler_assembly)
            else:
                error_kind = "Compiler output missing"

        # the .s.printed is not required but likely produced so we optionally link it
        printed_assembly = stem_add_suffix(compiler_assembly, "printed")
        if printed_assembly.is_file():
            files.append(printed_assembly)
        # No point in comparing assembly with gcc if the student compiler did not generate it
        if compiler_assembly.is_file():
            files.append(stem_add_suffix(log_stem, "gcc.s"))
        files.extend(log_stem.parent.glob(".*san.log.*"))

    # Clean version of the command for students to quickly retry the failing step:
    # shortening paths and removing ccache (compiler output caching)
    cmdstr = shlex.join(
        (get_relative_path(x) if isinstance(x, Path) else x)
        for x in cmd[(0 if cmd[0] != "ccache" else 1):]
    )
    return TestError(
        short_message=f"{error_kind} when {component.value.action.lower()} with `{cmdstr}`",
        files=files
    )

def test_from_driver(driver_file: Path) -> Path:
    """Removes the _driver part of driver file names (example_driver.c -> example.c)."""
    return driver_file.with_stem(driver_file.stem.removesuffix("_driver"))

def run_test(
    compiler: Callable[[Path, Path, int], TestError | None],
    output_dir: Path,
    driver_file: Path,
    **kwargs
) -> TestError | None:
    """
    Run an instance of a test case whose driver is given by `driver_file`.
    The output of all the steps are put in `output_dir`.
    Additional arguments are passed to `compiler` and `run_subprocess`.

    Returns None if successfull, otherwise the TestError of the failing step,
        or a failing TestError if every step succeeds but there are sanitizer warnings.
    """
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
    error = run_component(
        component=Component.REFERENCE,
        cmd=gcc_cmd \
            + ["-std=c90", "-pedantic", "-ansi", "-O0"] \
            + ["-S", test_file, "-o", stem_add_suffix(output_stem, "gcc.s")],
        log_stem=output_stem
    )
    if error is not None:
        return error

    # Compile
    error = compiler(test_file, output_stem, **kwargs)
    if error is not None:
        return error

    # Assemble
    error = run_component(
        component=Component.ASSEMBLER,
        cmd=gcc_cmd + ["-c", stem_add_suffix(output_stem, "s"), "-o", stem_add_suffix(output_stem, "o")],
        log_stem=output_stem
    )
    if error is not None:
        return error

    # Link
    error = run_component(
        component=Component.LINKER,
        cmd=gcc_cmd + ["-static", stem_add_suffix(output_stem, "o"), driver_file, "-o", output_stem],
        log_stem=output_stem
    )
    if error is not None:
        return error

    # Simulate
    error = run_component(
        component=Component.SIMULATION,
        cmd=["spike", f"--isa={isa}", "pk", output_stem],
        log_stem=output_stem
    )
    if error is not None:
        return error

    sanitizer_files = list(output_stem.parent.glob(".*san.log.*"))
    if len(sanitizer_files) != 0:
        return TestError(short_message="Sanitizer warnings", files=sanitizer_files)

    return None

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

    def write_result(self, test_file: Path, error: TestError | None = None):
        self._write_testcase(test_file, "" if error is None else \
            f"<error type={xml.quoteattr('error')} message={xml.quoteattr(error.get_short_message())}>\n"
            f"{xml.escape(error.get_message_with_file_content())}</error>\n"
        )

    def __exit__(self, *_):
        self._fd.write("</testsuite>\n")
        self._fd.close()

def run_tests(
    tests_dir: Path,
    report: JUnitXMLFile | None,
    jobs: int,
    **kwargs
) -> tuple[int, int]:
    """
    Runs tests in `tests_dir` against the compiler provided by `compiler` and puts outputs inside `output_dir`.
    Arguments `compiler` and `output_dir` are mandatory and are passed to `run_test`.
    Additional arguments are passed to `compiler` and `run_subprocess`.

    Returns a tuple of (passing: int, total: int) tests.
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
    ) as progress, ThreadPoolExecutor(max_workers=jobs) as executor:
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
            error = job.result()
            driver = job_to_driver[job]
            test_file = get_relative_path(test_from_driver(driver))

            if error is None:
                passed += 1
            else:
                failed += 1
                reporter.info(
                    rich_escape(f"{test_file}: {error.get_message_with_file_list()}"),
                    style="red"
                )

            elapsed = progress.tasks[task_id].elapsed or 0.0
            progress.update(
                task_id,
                advance=1,
                passed=passed,
                failed=failed,
                rate=(passed + failed) / elapsed if elapsed > 0 else 0.0,
            )

            if report is not None:
                report.write_result(test_file=test_file, error=error)

    assert len(drivers) == passed + failed, \
        f"Mismatch in number of tests with status ({passed} passed, {failed} failed, {len(drivers)} found)"
    return passed, passed + failed

def student_compiler(compiler_path: Path, input_file: Path, log_stem: Path, **kwargs) -> TestError | None:
    """
    Wrapper for `build/c_compiler -S <input_file> -o <log_stem>.s`.
    Additional arguments are passed to `run_subprocess`.

    Returns None if successful, a TestError otherwise.
    """
    # Modifying environment to store sanitizer errors
    env = environ.copy()
    env["ASAN_OPTIONS"] = f"log_path={log_stem}.asan.log"
    env["UBSAN_OPTIONS"] = f"log_path={log_stem}.ubsan.log"

    # Compile
    cmd = [compiler_path, "-S", input_file, "-o", stem_add_suffix(log_stem, "s")]
    return run_component(component=Component.COMPILER, cmd=cmd, log_stem=log_stem, env=env, **kwargs)

def symlink_reference_compiler(_input_file: Path, log_stem: Path, **kwargs) -> TestError | None:
    """
    Symlinks the result of riscv-gcc as its own result and move its logs as our own.
    It isn't really a compiler but can be passed as a compiler function to use the result of
    riscv-gcc as the output of the compiler, thus testing the ability of riscv-gcc to pass tests.

    Returns None; never fails.
    """
    reference_stem = stem_add_suffix(log_stem, Component.REFERENCE.value.name)
    compiler_stem = stem_add_suffix(log_stem, Component.COMPILER.value.name)
    for suffix in ["stdout.log", "stderr.log"]:
        move(stem_add_suffix(reference_stem, suffix), stem_add_suffix(compiler_stem, suffix))
    stem_add_suffix(log_stem, "s").symlink_to(stem_add_suffix(log_stem, "gcc.s"))
    return None

def parse_args(tests_dir: Path) -> Namespace:
    """Wrapper for argument parsing."""
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
        "-j", "--jobs",
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
        success = build_step(step=MakeRule.CLEAN.value, root_dir=root_dir)
        if not success:
            exit("Error when cleaning")

    # Prepare the output folder
    rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # There is no need for building the student compiler when testing with riscv-gcc
    if not args.validate_tests:
        success = build_step(
            step=MakeRule.COMPILER.value,
            root_dir=root_dir,
            jobs=args.jobs,
            optimise=args.optimise
        )
        if not success:
            exit("Error when building")

    # Run the tests and save the results into JUnit XML file
    with ExitStack() as stack:
        report = stack.enter_context(JUnitXMLFile(build_dir / "junit_results.xml")) \
            if args.generate_report else None
        passing, total = run_tests(
            tests_dir=args.dir,
            report=report,
            jobs=args.jobs,
            compiler=symlink_reference_compiler if args.validate_tests \
                else partial(student_compiler, build_dir / Component.COMPILER.value.name),
            output_dir=output_dir
        )

    # Skip unavailable coverage and exit immediately for test validation
    if args.validate_tests:
        if passing != total:
            exit(f"{total - passing} tests failed during test validation")
        reporter.info(f"All {total} tests are valid!")
        exit()

    # No coverage for optimised builds
    if not args.optimise:
        success = build_step(step=MakeRule.COVERAGE.value, root_dir=root_dir)
        if not success:
            exit("Error when processing coverage data")

        external_root = Path(environ["LOCALPWD"]) if "LOCALPWD" in environ else root_dir
        coverage_index = external_root.joinpath("coverage/index.html")
        reporter.info(
            "Check detailed coverage in coverage/index.html "
			f"(http://127.0.0.1:3000 in VS Code, or in a web browser at {rich_escape(coverage_index.as_uri())})\n"
        )

    reporter.info(f"[bold]Passed {passing}/{total} found test cases[/]")
