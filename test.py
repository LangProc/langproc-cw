#!/usr/bin/env python3

"""
A wrapper script to run all the compiler tests. This script will call the
Makefile, run the tests and store the outputs in build/output.

Usage: ./test.py [-h] [-v] [-j [N]] [--verbosity {0,1,2,3}] [--clean] [--optimise] [--report] [--validate_tests] [dir]

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
# switch to process_cpu_count next ubuntu update (python 3.14)
from os import environ, cpu_count
from sys import stdout, exit
from signal import Signals, valid_signals, strsignal
from shutil import rmtree, move
from pathlib import Path
from argparse import ArgumentParser, Namespace
from enum import IntEnum, Enum
from itertools import chain
from functools import partial
from contextlib import nullcontext, ExitStack
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.markup import escape as rich_escape
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn

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
        if min_verbosity <= self.verbosity:
            self.console.print(message, style=style, highlight=False)

    def debug(self, message: str, style: str = ""):
        self._emit(message, style, Verbosity.DEBUG)

    def info(self, message: str, style: str = "cyan"):
        self._emit(message, style, Verbosity.NORMAL)

    def warning(self, message: str, style: str = "yellow"):
        self._emit(message, style, Verbosity.NORMAL)

    def error(self, message: str, style: str = "red"):
        self._emit(message, style, Verbosity.QUIET)

    def status(self, message: str, style: str = "cyan", verbosity: Verbosity = Verbosity.NORMAL):
        message = f"{message}..."
        if verbosity > self.verbosity:
            styled_message = message if style == "" else f"[{style}]{message}[/]"
            return self.console.status(styled_message, spinner="dots")

        # For higher verbosity (when other logs are printed as well), fall back to _emit(...)
        self._emit(message, style, verbosity)
        return nullcontext()

reporter = Reporter()

BUILD_DIR_NAME = "build"
OUTPUT_DIR_NAME = "output"
TESTS_DIR_NAME = "tests"
BENCHMARK_DIR_NAME = "benchmark"

class TestStep(Enum):
    REFERENCE = "gcc_reference", "Generating reference assembly"
    COMPILER = "c_compiler", "Compiling"
    ASSEMBLER = "assembler", "Assembling"
    LINKER = "linker", "Linking"
    SIMULATION = "simulation", "Simulating"

    def __new__(cls, value: str, action: str):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.action = action
        return obj


class MakeRule(Enum):
    CLEAN = "clean", "Cleaning project"
    COMPILER = f"{BUILD_DIR_NAME}/{TestStep.COMPILER.value}", "Building compiler"
    COVERAGE = "coverage", "Processing coverage data"

    def __new__(cls, value: str, action: str):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.action = action
        return obj


def get_return_code_msg(return_code: int) -> str:
    """Describes a return code."""
    if return_code < 0 and -return_code in valid_signals():
        signal_name = strsignal(-return_code).lower() or 'unknown signal'
        return f"Process ended by {signal_name} {Signals(-return_code)}"
    if return_code == 124:
        return "Timeout"
    if return_code != 0:
        return "Error"
    return "Success"

def append_suffix_to_stem(stem: Path, suffix: str) -> Path:
    return stem.with_name(f"{stem.name}.{suffix}")

def get_logs_from_stem(stem: Path) -> list[Path]:
    return [append_suffix_to_stem(stem, f"{s}.log") for s in ["stdout", "stderr"]]

def run_subprocess(
    cmd: list[str | Path],
    log_files: tuple[Path, Path] | None,
    **kwargs
) -> int:

    with ExitStack() as stack:
        if log_files is not None:
            # stdout and stderr go to files
            stdout = stack.enter_context(log_files[0].open(mode="w"))
            stderr = stack.enter_context(log_files[1].open(mode="w"))
        else:
            # stdout and stderr go to terminal
            stdout = stderr = None

        return subprocess.run(cmd, stdout=stdout, stderr=stderr, **kwargs).returncode

def run_make_rule(
    rule: MakeRule,
    root_dir: Path,
    verbosity: Verbosity = Verbosity.NORMAL,
    jobs: int = 1,
    optimise: bool = False,
    **kwargs
) -> bool:
    """
    Wrapper for `make <rule>`.

    Returns True if successful, False otherwise.
    """
    quiet = verbosity > reporter.verbosity
    cmd = [
        "make",
        f"-j{jobs}",
        "-s" if quiet else "-Oline",
        "-C", root_dir,
        f"{'N' if optimise else ''}DEBUG=1",
        rule.value
    ]

    with reporter.status(rule.action, verbosity=verbosity):
        return_code = run_subprocess(
            cmd,
            log_files=get_logs_from_stem(root_dir / f"make_{rule.value.replace('/', '_')}") \
                if quiet else None,
            **kwargs
        )

    if return_code == 0:
        return True

    # Clean version of the command for students to quickly retry the failing rule
    failed_cmd_str = shlex.join(["make"] + cmd[-2:])
    reporter.error(
        f"{get_return_code_msg(return_code)} when {rule.action.lower()} with `{failed_cmd_str}`."
    )

    return False

def get_relative_path_str(path: Path) -> str:
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
        return "".join(chain(
            [self._short_message, ", see:\n"],
            (f"\t{get_relative_path_str(file)}\n" for file in self._files)
        ))

    def get_message_with_file_content(self) -> str:
        return "".join(chain(
            [self._short_message, ".\n"],
            (f"\t{get_relative_path_str(file)}:\n{file.read_text()}:\n" for file in self._files)
        ))

def run_test_step(
    step: TestStep,
    cmd: list[str | Path],
    log_stem: Path,
    **kwargs
) -> TestError | None:
    """
    Runs one compiler testing step.
    On error links additional relevant output files.

    Returns None if successful, a TestError otherwise.
    """

    files = get_logs_from_stem(append_suffix_to_stem(log_stem, step.value))
    return_code = run_subprocess(cmd, log_files=files, **kwargs)

    if return_code == 0:
        return None

    error_msg = get_return_code_msg(return_code)
    # All passes after student compiler should add files to refer to
    # I tried to link them in the order students should inspect them
    # If the compiler succeeded and a further step failed, it is likely caused by the compiler
    # so we should link the compiler outputs, in particular the produced assembly (see below)
    if step is not TestStep.REFERENCE:
        # If the compiler output is present add it with the reference to compare to;
        # if the compiler failed we don't expect it but link it if present,
        # otherwise it's probably the reason of the failure,
        # so it's worth mentioning first in the error message
        asm_file = append_suffix_to_stem(log_stem, "s")
        if step is TestStep.COMPILER:
            if asm_file.is_file():
                files.append(asm_file)
            # Don't link it if it failed, don't need to duplicate link std(out/err)
        else:
            files.extend(get_logs_from_stem(append_suffix_to_stem(log_stem, TestStep.COMPILER.value)))
            if asm_file.is_file():
                files.append(asm_file)
            else:
                error_msg = "Compiler output missing"

        # the .s.printed is not required but likely produced so we optionally link it
        printed_file = append_suffix_to_stem(asm_file, "printed")
        if printed_file.is_file():
            files.append(printed_file)
        # No point in comparing assembly with gcc if the student compiler did not generate it
        if asm_file.is_file():
            files.append(append_suffix_to_stem(log_stem, "gcc.s"))
        # In any case add sanitizer files because we really want students to write good code
        files.extend(log_stem.parent.glob(".*san.log.*"))

    # Clean version of the command for students to quickly retry the failing step:
    # shortening paths and removing ccache (compiler output caching)
    failed_cmd_str = shlex.join(
        (get_relative_path_str(x) if isinstance(x, Path) else x)
        for x in cmd[(0 if cmd[0] != "ccache" else 1):]
    )
    return TestError(
        short_message=f"{error_msg} when {step.action.lower()} with `{failed_cmd_str}`",
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
    Additional arguments are passed to `compiler` and `run_test_step`.

    Returns None if successful, otherwise the TestError of the failing step,
        or a TestError if every step succeeds but there are sanitizer warnings.
    """
    test_file = test_from_driver(driver_file)
    if not test_file.is_file():
        raise FileNotFoundError(
            f"Test driver `{get_relative_path_str(driver_file)}` doesn't have"
            f"an associated test file ({get_relative_path_str(test_file)})"
        )

    # Construct the stem to use for output files, so the path without the suffix
    # e.g. .../build/output/_example/example/example
    output_stem = output_dir.joinpath(test_file.parent.name, test_file.stem, test_file.stem)

    # Recreate the directory
    rmtree(output_stem.parent, ignore_errors=True)
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    # GCC is not targetting rv32imfd (base target of the course) because:
    # rv32imfd is compatible with rv32gc and the C extension is a part of extended goals
    # _zicntr allows for cycles and instructions measurements with rdcycle and rdinstret
    isa = "rv32gc_zicntr"
    gcc_cmd = ["ccache", "riscv32-unknown-elf-gcc", f"-march={isa}", "-mabi=ilp32d"]

    # GCC Reference Output
    if (error := run_test_step(
        step=TestStep.REFERENCE,
        cmd=gcc_cmd + [
            "-std=c90", "-pedantic", "-ansi", "-O0",
            "-S", test_file, # We went with this flag order, but gcc's -S doesn't take a value
            "-o", append_suffix_to_stem(output_stem, "gcc.s")
        ],
        log_stem=output_stem,
        **kwargs
    )) is not None:
        return error

    # Compile
    if (error := compiler(test_file, output_stem, **kwargs)) is not None:
        return error

    # Assemble
    if (error := run_test_step(
        step=TestStep.ASSEMBLER,
        cmd=gcc_cmd + [
            "-c", append_suffix_to_stem(output_stem, "s"), # -c doesn't take a value
            "-o", append_suffix_to_stem(output_stem, "o")
        ],
        log_stem=output_stem,
        **kwargs
    )) is not None:
        return error

    # Link
    if (error := run_test_step(
        step=TestStep.LINKER,
        cmd=gcc_cmd + [
            "-static", # Finally not pretending -static takes a value (it doesn't)
            append_suffix_to_stem(output_stem, "o"), driver_file,
            "-o", output_stem
        ],
        log_stem=output_stem,
        **kwargs
    )) is not None:
        return error

    # Simulate
    if (error := run_test_step(
        step=TestStep.SIMULATION,
        cmd=["spike", f"--isa={isa}", "pk", output_stem],
        log_stem=output_stem,
        **kwargs
    )) is not None:
        return error

    if sanitizer_files := list(output_stem.parent.glob(".*san.log.*")):
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
            f"<error type={xml.quoteattr('error')} "
            f"message={xml.quoteattr(error.get_short_message())}>\n"
            f"{xml.escape(error.get_message_with_file_content())}</error>\n"
        )

    def __exit__(self, *_):
        self._fd.write("</testsuite>\n")
        self._fd.close()

def measure_compiler_stats(benchmark_dir: Path, repetitions: int):
    """
    Measure compiler's compilation time, execution time and ELF size
    """
    reporter.info("[bold]Benchmark results:[/]", style="purple")

    for test_case_dir in benchmark_dir.iterdir():

        test_case_name = test_case_dir.stem
        test_case_stem = (test_case_dir / test_case_name)

        # Compilation time obtained from the time spent by compiler to compiler the test case
        compilation_log = append_suffix_to_stem(test_case_stem, "compilation_time.log")
        try:
            compilation_time = compilation_log.read_text(encoding="utf-8").strip()
            compilation_msg = f"{float(compilation_time) / repetitions:.2f} s"
        except FileNotFoundError:
            compilation_msg = "N/A"

        # Simulated instructions using ASM rdinstret in driver code
        simulation_log = append_suffix_to_stem(test_case_stem, "simulation.stdout.log")
        simulated_instructions = int(simulation_log.read_text(encoding="utf-8").strip())

        # Binary size obtained as the sum of .text + .data + .rodata sections of ELF file
        elf_file = test_case_stem.with_name(f"{test_case_stem.name}.o")
        cmd = ["riscv32-unknown-elf-size", "-A", str(elf_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        binary_size = 0

        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] in {".text", ".data", ".rodata"}:
                binary_size += int(parts[1])

        # Report compiler stats to terminal, students can decide how to process them further
        reporter.info(
            f"{test_case_name}: "
            f"compilation time = {compilation_msg}, "
            f"simulated instructions = {simulated_instructions}, "
            f"binary size = {binary_size} B",
            style="purple"
        )

def run_tests(drivers: list[Path], jobs: int, report: JUnitXMLFile | None = None, **kwargs) -> tuple[int, int]:
    """
    Runs tests in `tests_dir` against the compiler provided by `compiler`.
    Puts outputs inside `output_dir`.
    Arguments `compiler` and `output_dir` are mandatory and are passed to `run_test`.
    Additional arguments are passed to `compiler` and `run_test_step`.

    Returns a tuple of (passing, total) tests.
    """
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
        task_id = progress.add_task("tests", total=len(drivers), passed=0, failed=0, rate=0.0)

        job_to_driver = {
            executor.submit(run_test, driver_file=driver, **kwargs): driver
            for driver in drivers
        }
        for job in as_completed(job_to_driver):
            driver = job_to_driver[job]
            test_file = get_relative_path_str(test_from_driver(driver))

            if (error := job.result()) is not None:
                failed += 1
                reporter.info(
                    rich_escape(f"{test_file}: {error.get_message_with_file_list()}"),
                    style="red"
                )
            else:
                passed += 1

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
        "Mismatch in number of tests with status " \
        f"({passed} passed, {failed} failed, {len(drivers)} found)"
    return passed, passed + failed

def student_compiler(
    compiler_path: Path,
    repetitions: int,
    input_file: Path,
    output_stem: Path,
    **kwargs
) -> TestError | None:
    """
    Wrapper for `build/c_compiler -S <input_file> -o <log_stem>.s`.
    Additional arguments are passed to `run_test_step`.

    Returns None if successful, a TestError otherwise.
    """
    # Modifying environment to store sanitizer errors
    env = environ.copy()
    env["ASAN_OPTIONS"] = f"log_path={output_stem}.asan.log"
    env["UBSAN_OPTIONS"] = f"log_path={output_stem}.ubsan.log"

    cmd = [str(compiler_path), "-S", str(input_file), "-o", str(append_suffix_to_stem(output_stem, "s"))]

    if repetitions > 0:
        time_cmd = ["/usr/bin/time", "-f", "%e", "-o", append_suffix_to_stem(output_stem, "compilation_time.log")]
        cmd = time_cmd + ["bash", "-lc", f"for i in $(seq 1 {repetitions}); do {shlex.join(cmd)}; done"]

    # Compile
    return run_test_step(step=TestStep.COMPILER, cmd=cmd, log_stem=output_stem, env=env, **kwargs)

def symlink_reference_compiler(_input_file: Path, output_stem: Path, **kwargs) -> TestError | None:
    """
    Symlinks the result of riscv-gcc as its own result and move its logs as our own.
    It isn't really a compiler but can be passed as a compiler function to use the result of
    riscv-gcc as the output of the compiler, thus testing the ability of riscv-gcc to pass tests.

    Returns None; never fails.
    """
    reference_stem = append_suffix_to_stem(output_stem, TestStep.REFERENCE.value)
    compiler_stem = append_suffix_to_stem(output_stem, TestStep.COMPILER.value)
    for suffix in ["stdout.log", "stderr.log"]:
        move(
            append_suffix_to_stem(reference_stem, suffix),
            append_suffix_to_stem(compiler_stem, suffix)
        )
    append_suffix_to_stem(output_stem, "s").symlink_to(append_suffix_to_stem(output_stem, "gcc.s"))
    return None

def parse_args() -> Namespace:
    """Wrapper for argument parsing."""
    parser = ArgumentParser()
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"BetterTesting {__version__}"
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
        "--verbosity",
        type=lambda arg: Verbosity(int(arg)),
        choices=Verbosity,
        default=Verbosity.NORMAL,
        help="Disable verbose output into the terminal. Note that all logs will "
            "be stored automatically into log files regardless of this option."
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
        "--report",
        action="store_true",
        default=False,
        help="Generate a JUnit report to use as a test summary for CI/CD."
    )
    parser.add_argument(
        "--benchmark",
        nargs="?",
        const=100,
        default=0,
        type=int,
        metavar="N",
        help="Benchmark compiler and gather related statistics like compilation "
            "time, execution time, and ELF size. Use -j to use the default compilation "
            "repetitions, or -j N to do exactly N repetitions."
    )
    parser.add_argument(
        "--validate_tests",
        action="store_true",
        default=False,
        help="Use GCC to validate tests instead of testing the compiler. "
            "Use it to validate tests you add (see docs/coverage.md for useful tests)."
    )
    return parser.parse_args()

def get_drivers_from_path(dir: Path, exclude_dir: Path | None = None) -> list[Path]:
    drivers = []
    for test_candidate in dir.rglob("*_driver.c"):
        if exclude_dir is not None and test_candidate.is_relative_to(exclude_dir):
            continue
        drivers.append(test_candidate)

    return sorted(drivers, key=lambda p: (p.parent.name, p.name))

if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent
    build_dir = root_dir / BUILD_DIR_NAME
    output_dir = build_dir / OUTPUT_DIR_NAME

    tests_dir = root_dir / TESTS_DIR_NAME
    benchmark_dir = tests_dir / BENCHMARK_DIR_NAME

    args = parse_args()
    reporter.verbosity = args.verbosity

    # Clean the repo if required
    if args.clean:
        if not run_make_rule(
            rule=MakeRule.CLEAN,
            verbosity=Verbosity.VERBOSE,
            root_dir=root_dir
        ):
            exit(1)

    # Prepare the output folder
    rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # There is no need for building the student compiler when testing with riscv-gcc
    if not args.validate_tests:
        if not run_make_rule(
            rule=MakeRule.COMPILER,
            verbosity=Verbosity.NORMAL,
            root_dir=root_dir,
            jobs=args.jobs,
            optimise=args.optimise
        ):
            exit(1)

    # Run the tests and save the results into JUnit XML file
    with ExitStack() as stack:
        report = stack.enter_context(JUnitXMLFile(build_dir / "junit_results.xml")) \
            if args.report else None
        passing_tests, total_tests = run_tests(
            drivers=get_drivers_from_path(tests_dir, exclude_dir=benchmark_dir),
            jobs=args.jobs,
            report=report,
            compiler=symlink_reference_compiler if args.validate_tests \
                else partial(student_compiler, build_dir / TestStep.COMPILER.value, 0),
            output_dir=output_dir
        )

    # Run the benchmarks
    if args.benchmark:
        if args.jobs > 1:
            reporter.warning("Benchmarking with jobs > 1 may affect compilation timing analysis")

        passing_benchmark, total_benchmark = run_tests(
            drivers=get_drivers_from_path(benchmark_dir),
            jobs=args.jobs,
            compiler=symlink_reference_compiler if args.validate_tests \
                else partial(student_compiler, build_dir / TestStep.COMPILER.value, args.benchmark),
            output_dir=output_dir
        )

        if passing_benchmark == total_benchmark:
            measure_compiler_stats(benchmark_dir=output_dir / BENCHMARK_DIR_NAME, repetitions=args.benchmark)
        else:
            reporter.warning(f"Skipping benchmarking due to failures")

    # Skip unavailable coverage and exit immediately for test validation
    if args.validate_tests:
        if passing_tests != total_tests:
            exit(f"Number of tests failed during test validation: {total_tests - passing_tests}")
        reporter.info(f"All {total_tests} tests are valid!")
        exit(0)

    # No coverage for optimised builds
    if not args.optimise:
        if not run_make_rule(
            rule=MakeRule.COVERAGE,
            verbosity=Verbosity.DEBUG,
            root_dir=root_dir
        ):
            exit(1)

    reporter.error(f"[bold]Passed {passing_tests}/{total_tests} found test cases[/]", style="cyan")
