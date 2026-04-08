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
from argparse import ArgumentParser, Namespace, ArgumentError
from enum import IntEnum, Enum
from itertools import chain
from functools import partial
from contextlib import nullcontext, ExitStack
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.markup import escape as rich_escape
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn

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

    def status(self, message: str, verbosity: Verbosity = Verbosity.NORMAL):
        style = "cyan"
        styled_message = f"[{style}]{message}[/]"
        if verbosity > self.verbosity:
            return self.console.status(styled_message, spinner="dots")

        # For higher verbosity (when other logs are printed as well), use fallback
        self._emit(f"{styled_message}...", style, verbosity)
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
    BUILD = f"{BUILD_DIR_NAME}/{TestStep.COMPILER.value}", "Building compiler"
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

def get_logs_from_stem(stem: Path) -> tuple[Path, Path]:
    return tuple(append_suffix_to_stem(stem, f"{s}.log") for s in ("stdout", "stderr"))

def run_subprocess(cmd: list[str | Path], log_stem: Path | None, **kwargs) -> int:
    with ExitStack() as stack:
        stdout, stderr = (
            tuple(stack.enter_context(path.open("w")) for path in get_logs_from_stem(log_stem))
            if log_stem is not None
            else (None, None)
        )

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
            cmd=cmd,
            log_stem=(root_dir / f"make_{rule.value.replace('/', '_')}") if quiet else None,
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

def get_sanitizer_files_from_stem_parent(stem: Path) -> Iterator[Path]:
    return stem.parent.glob("*.*san.log.*")

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

    component_log_stem = append_suffix_to_stem(log_stem, step.value)
    return_code = run_subprocess(cmd, log_stem=component_log_stem, **kwargs)

    if return_code == 0:
        return None

    error_msg = get_return_code_msg(return_code)
    files = list(get_logs_from_stem(component_log_stem))
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
        files.extend(get_sanitizer_files_from_stem_parent(log_stem))

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

def output_stem_from_test(output_dir: Path, test_file: Path) -> Path:
    return output_dir.joinpath(test_file.parent.name, test_file.stem, test_file.stem)

type CompilerType = Callable[[Path, Path], TestError | None]

def run_test(
    compiler: CompilerType,
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
    output_stem = output_stem_from_test(output_dir, test_file)

    # Recreate the directory
    remake_dir(output_stem.parent)

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

    if sanitizer_files := list(get_sanitizer_files_from_stem_parent(output_stem)):
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

def run_tests(
    drivers: list[Path],
    jobs: int,
    output_dir: Path,
    report_path: str | None = None,
    status: str = "Running tests",
    **kwargs
) -> tuple[int, int]:
    """
    Runs tests in `tests_dir` against the compiler provided by `compiler`.
    Puts outputs inside `output_dir`.
    Arguments `compiler` and `output_dir` are mandatory and are passed to `run_test`.
    Additional arguments are passed to `compiler` and `run_test_step`.

    Returns a tuple of (passing, total) tests.
    """
    passed = failed = 0

    with ExitStack() as stack:
        progress = stack.enter_context(Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}[/]"),
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
        ))
        xml_file = stack.enter_context(
            JUnitXMLFile(output_dir / report_path) if report_path is not None else nullcontext()
        )
        executor = stack.enter_context(ThreadPoolExecutor(max_workers=jobs))

        task_id = progress.add_task(status, total=len(drivers), passed=0, failed=0, rate=0.0)

        job_to_driver = {
            executor.submit(run_test, driver_file=driver, output_dir=output_dir, **kwargs): driver
            for driver in drivers
        }

        for job in as_completed(job_to_driver):
            test_file = get_relative_path_str(test_from_driver(job_to_driver[job]))

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

            if xml_file is not None:
                xml_file.write_result(test_file=test_file, error=error)

    assert len(drivers) == passed + failed, \
        "Mismatch in number of tests with status " \
        f"({passed} passed, {failed} failed, {len(drivers)} found)"

    return passed, passed + failed

def student_compiler(
    compiler_path: Path,
    repetitions: int = 0,
    opt_flag: str | None = None
) -> CompilerType:
    """
    Wrapper for `build/c_compiler [opt_flag] -S <input_file> -o <log_stem>.s`,
    with optional time measurement. Additional arguments are passed to `run_test_step`.

    Returns None if successful, a TestError otherwise.
    """
    def compiler(input_file: Path, output_stem: Path, **kwargs) -> TestError | None:
        env = environ.copy()

        cmd = [compiler_path, "-S", input_file, "-o", append_suffix_to_stem(output_stem, "s")]
        if opt_flag is not None:
            cmd.insert(1, opt_flag)

        if repetitions > 0:
            time_cmd = [
                "/usr/bin/time", "-f", "%e",
                "-o", append_suffix_to_stem(output_stem, "compilation_time.log")
            ]
            cmd = time_cmd + [
                "bash", "-lc",
                f"for i in $(seq 1 {repetitions}); do {shlex.join([str(el) for el in cmd])}; done"
            ]
        else:
            # Modifying environment to store sanitizer errors
            env["ASAN_OPTIONS"] = f"log_path={output_stem}.asan.log"
            env["UBSAN_OPTIONS"] = f"log_path={output_stem}.ubsan.log"


        return run_test_step(step=TestStep.COMPILER, cmd=cmd, log_stem=output_stem, env=env, **kwargs)

    return compiler

def symlink_reference_compiler(_input_file: Path, output_stem: Path, **_kwargs) -> TestError | None:
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

def remake_dir(dir: Path):
    rmtree(dir, ignore_errors=True)
    dir.mkdir(parents=True, exist_ok=True)

def get_drivers_from_path(dir: Path, exclude_dir: Path | None = None) -> list[Path]:
    return [driver for driver in dir.rglob("*_driver.c")
            if exclude_dir is None or not driver.is_relative_to(exclude_dir)]

def benchmark(output_dir: Path, benchmark_dir: Path, repetitions: int):
    assert repetitions > 0, f"Number of repetitions should be positive, got {repetitions}"

    for driver in get_drivers_from_path(benchmark_dir):
        output_stem =  output_stem_from_test(output_dir, test_from_driver(driver))

        # Compilation time obtained from the time spent by compiler to compiler the test case
        compilation_log = append_suffix_to_stem(output_stem, "compilation_time.log")
        try:
            total_compilation_time = compilation_log.read_text(encoding="utf-8").strip()
            compilation_time = float(total_compilation_time) / repetitions
        except (FileNotFoundError, ValueError):
            compilation_time = None

        # Simulated instructions using ASM rdinstret in driver code
        simulation_log = append_suffix_to_stem(output_stem, "simulation.stdout.log")
        try:
            simulated_instructions = int(simulation_log.read_text(encoding="utf-8").strip())
        except ValueError:
            simulated_instructions = None

        # Binary size obtained as the sum of .text + .data + .rodata sections of ELF file
        elf_file = output_stem.with_suffix(".o")
        cmd = ["riscv32-unknown-elf-size", "-A", elf_file]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        binary_size = 0
        try:
            for parts in (line.split() for line in result.stdout.splitlines()):
                if len(parts) >= 2 and parts[0] in {".text", ".data", ".rodata"}:
                    binary_size += int(parts[1])
        except ValueError:
            binary_size = None

        reporter.error(
            f"\t{output_stem.name}: "
            f"compilation time = {compilation_time or 'N/A'} s, "
            f"simulated instructions = {simulated_instructions or 'N/A'}, "
            f"binary size = {binary_size or 'N/A'} B",
            style="purple"
        )

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
        help="Build compiler and run tests using parallelism. "
            "Use -j to use the default job count, or -j N to use exactly N jobs. "
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
        nargs="?",
        const=Path("junit_results.xml"),
        default=None,
        metavar="PATH",
        help="Generate a JUnit report to use as a test summary for CI/CD. "
            "Use --report for the default path, or --report PATH to choose a file."
    )
    parser.add_argument(
        "--benchmark",
        nargs="?",
        const=1000,
        default=0,
        type=int,
        metavar="N",
        help="Benchmark compiler and gather related statistics like compilation "
            "time, execution time, and ELF size. Use --benchmark to use the default "
            "compilation repetitions, or --benchmark N to do exactly N repetitions."
    )
    parser.add_argument(
        "--validate_tests",
        action="store_true",
        default=False,
        help="Use GCC to validate tests instead of testing the compiler. "
            "Use it to validate tests you add (see docs/coverage.md for useful tests)."
    )
    return parser.parse_args()

if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent
    args = parse_args()
    reporter.verbosity = args.verbosity

    build_dir = root_dir / BUILD_DIR_NAME
    output_dir = build_dir / OUTPUT_DIR_NAME
    tests_dir = root_dir / TESTS_DIR_NAME
    benchmark_dir = tests_dir / BENCHMARK_DIR_NAME
    compiler_path = MakeRule.BUILD.value

    # Shared arguments to run_make_rule
    run_make_rule_common = partial(
        run_make_rule,
        root_dir=root_dir,
        jobs=args.jobs,
        optimise=args.optimise
    )

    # Skip building steps when using riscv-gcc
    if not args.validate_tests:
        # Clean the repo if required
        if (args.clean and not run_make_rule_common(
            rule=MakeRule.CLEAN,
            verbosity=Verbosity.VERBOSE
        )) or not run_make_rule_common(
            rule=MakeRule.BUILD,
            verbosity=Verbosity.NORMAL
        ):
            exit(1)

    # Clean the output folder
    remake_dir(output_dir)

    # Shared arguments to run_tests
    run_tests_common = partial(
        run_tests,
        jobs=args.jobs,
        output_dir=output_dir,
        report_path=args.report,
    )

    # Run the tests and save the results into JUnit XML file if asked (in CI/CD typically)
    passing_tests, total_tests = run_tests_common(
        drivers=get_drivers_from_path(tests_dir, exclude_dir=benchmark_dir),
        compiler=symlink_reference_compiler if args.validate_tests \
            else student_compiler(compiler_path),
    )

    reporter.error(f"[bold]Passed {passing_tests}/{total_tests} found test cases[/]", style="cyan")

    if args.benchmark:
        opt_flag = "-O1"

        if args.jobs > 1 or not args.optimise:
            reporter.warning(f"Benchmarking with jobs > 1 or unoptimised builds can affect timing")

        # Start by checking if students' optimisations don't fail more seen tests than before
        passing_tests_with_opt, _ = run_tests_common(
            drivers=get_drivers_from_path(tests_dir, exclude_dir=benchmark_dir),
            compiler=symlink_reference_compiler if args.validate_tests \
                else student_compiler(compiler_path, opt_flag=opt_flag),
        )
        if passing_tests_with_opt < passing_tests:
            reporter.error(f"Enabling optimisations with {opt_flag} causes "
                           f"{passing_tests-passing_tests_with_opt} previously successful tests to fail")

        # Benchmark students' compiler with and without their custom optimisations, if relevant
        benchmark_configs = (
            [(" without optimisations", None), (" with optimisations", opt_flag)]
            if not args.validate_tests
            else [("", None)]
        )

        for optimisation_msg, opt_flag in benchmark_configs:

            # Run the benchmark tests according to opt_flag
            passing_benchmark, total_benchmark = run_tests_common(
                drivers=get_drivers_from_path(benchmark_dir),
                status=f"Running benchmark{optimisation_msg}",
                compiler=symlink_reference_compiler if args.validate_tests \
                    else student_compiler(compiler_path, repetitions=args.benchmark, opt_flag=opt_flag),
            )

            if passing_benchmark != total_benchmark:
                reporter.warning(f"Skipping benchmarking{optimisation_msg} due to failures")
                continue

            reporter.error(f"[bold]Benchmark results{optimisation_msg}:[/]", style="purple")
            benchmark(output_dir=output_dir, benchmark_dir=benchmark_dir, repetitions=args.benchmark)

        passing_tests += passing_benchmark
        total_tests += total_benchmark

    # Skip unavailable coverage and exit immediately for test validation
    if args.validate_tests:
        if passing_tests != total_tests:
            reporter.error(
                "Number of tests failed during test validation: "
                f"{total_tests - passing_tests}"
            )
            exit(1)
        reporter.error(f"All {total_tests} tests are valid!", style="cyan")
        exit(0)

    # Run coverage if students' compiler was built w/o optimising
    if not (args.optimise or run_make_rule_common(
        rule=MakeRule.COVERAGE,
        verbosity=Verbosity.DEBUG
    )):
        exit(1)