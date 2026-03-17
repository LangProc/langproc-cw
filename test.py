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

__version__ = "1.1.0"
__author__ = "William Huynh, Filip Wojcicki, James Nock, Quentin Corradi"


from argparse import ArgumentParser, Namespace
from collections import namedtuple
from collections.abc import Callable
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, wait
from curses import setupterm, tparm as _tparm, tigetstr as _tigetstr, tigetnum as ti_get_num
from dataclasses import dataclass
from os import environ, cpu_count
from pathlib import Path
from shutil import rmtree
from subprocess import run as _run, DEVNULL
from sys import stdout
from termios import tcsetattr, tcgetattr, TCSANOW, ECHO
from threading import Lock
from xml.sax.saxutils import escape as xmlescape, quoteattr as xmlquoteattr
# To remove?
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Setup terminfo part of the curses library. *Not curses itself*, just terminfo
try:
    setupterm()
    del setupterm

    def ti_parm(attr: str, *args) -> str:
        if not stdout.isatty():
            return ""
        b = _tigetstr(attr)
        if b is None:
            return ""
        if len(args) == 0:
            return b.decode()
        return _tparm(b, *args).decode()

    def ti_get_str(attr: str) -> str:
        if not stdout.isatty():
            return ""
        b = _tigetstr(attr)
        return "" if b is None else b.decode()
except Exception as e:
    def ti_parm(x: str, *args) -> str:
        return ""
    def ti_get_str(attr: str) -> str:
        return ""
    def ti_get_num(attr: str) -> int:
        if attr == "cols":
            return 80
        raise InvalidArgument(f"`ti_get_num(attr={attr})` failed because `setupterm` failed")

COLOR_BLACK = 0
COLOR_RED = 1
COLOR_GREEN = 2
COLOR_YELLOW = 3
COLOR_BLUE = 4
COLOR_MAGENTA = 5
COLOR_CYAN = 6
COLOR_WHITE = 7

_progress_bars = []
unsafe_print = print
stdout_lock = Lock()
def print(*args, **kwargs):
    with stdout_lock:
        unsafe_print(*args, flush=True, **kwargs)
        for pb in _progress_bars:
            pb._update_no_stdout_lock()

def path_append(path: Path, extension: str) -> Path:
    return path.with_name(path.name + extension)

class JUnitXMLFile():
    def __init__(self, path: Path, description: str):
        assert path.is_file() or not path.exists()
        self._description = description
        self._path = path
        self._lock = Lock()

    def __enter__(self):
        self._fd = self._path.open(mode="w")
        del self._path
        self._fd.write(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<testsuite name={xmlquoteattr(self._description)}>\n"
        )
        del self._description
        return self

    def _write_test_xml(self, test_path: Path, body: str):
        with self._lock:
            self._fd.write(f"<testcase name={xmlquoteattr(str(test_path))}>{body}</testcase>\n")

    def log_success(self, test_path: Path, log: str | None = None):
        self._write_test_xml(test_path,
            "" if log is None else f"\n<system-out>{xmlescape(log)}</system-out>\n"
        )

    def log_failure(self, test_path: Path, description: str, log: str):
        message = xmlquoteattr(f"Error when {description}.")
        body = xmlescape(log)
        self._write_test_xml(test_path, f"\n<error type=\"error\" message={message}>{body}</error>\n")

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self._fd.write("</testsuite>\n")
        self._fd.close()

class AsyncProgressWithLog:
    """
    Creates a CLI progress bar that can update itself while allowing log to be printed.

    Parameters:
    - total_entries: the number of expected entries, progress is computed relative to it.
    - entries_display: a dictionary associating the character to display entries with
        to the color used to display progress of those entries.
    """

    # This is just a mutable pair with names
    @dataclass
    class _ColorCount:
        color: int
        count: int = 0

    def __init__(self, total_entries: int, entries_display: dict[str, int]):
        assert total_entries >= 1, total_entries
        assert len(entries_display) >= 1, entries_display
        assert all(len(s) == 1 for s in entries_display), list(entries_display.keys())
        self._total_entries = total_entries
        self._entries = {k: self._ColorCount(color=color) for k, color in entries_display.items()}
        self._lock = Lock()

    def _display_bar(self, cols: int, bar: str = ""):
        assert stdout_lock.locked()
        # save pos
        stdout.write(ti_get_str("sc"))
        # go to left of bar line
        stdout.write(ti_parm("cup", self._bar_line, 0))
        # clear line
        stdout.write(ti_get_str("el"))
        stdout.write(ti_parm("cup", self._bar_line, 0))
        stdout.write("[")
        stdout.write(bar)
        # reset color
        stdout.write(ti_get_str("sgr0"))
        # go to right of bar line
        stdout.write(ti_parm("cup", self._bar_line, cols - 1))
        # enter insert mode to prevent going to a newline when at the bottom of the screen
        stdout.write(ti_get_str("smir"))
        stdout.write("]")
        # exit insert mode
        stdout.write(ti_get_str("rmir"))
        # restore pos
        stdout.write(ti_get_str("rc"))
        stdout.flush()

    def __enter__(self):
        self._bar_line = len(_progress_bars)
        _progress_bars.append(self)
        with stdout_lock:
            # Prevent key presses from showing
            try:
                attrs = tcgetattr(stdout)
                self._old_attrs = deepcopy(attrs)
                attrs[3] &= ~ECHO
                tcsetattr(stdout, TCSANOW, attrs)
            except Exception as e:
                pass
            # Enter temporary terminal screen
            stdout.write(ti_get_str("smcup"))
            # Initialize the progress bar
            self._display_bar(ti_get_num("cols"))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        _progress_bars.remove(self)
        with stdout_lock:
            # Reset color
            stdout.write(ti_get_str("sgr0"))
            # Exit temporary terminal screen
            stdout.write(ti_get_str("rmcup"))
            # Restore key presses behaviour
            try:
                tcsetattr(stdout, TCSANOW, self._old_attrs)
            except Exception as e:
                pass
            # Sequence to reset terminal (should not have to be done)
            # stdout.write(ti_get_str("rs1"))
            # stdout.write(ti_get_str("rs2"))
            # stdout.write(ti_get_str("rsf"))
            # stdout.write(ti_get_str("rs3"))
            stdout.flush()

    def __getitem__(self, subscript):
        return self._entries.__getitem__(subscript).count

    _SplitEntry = namedtuple("SplitEntry", ["index", "remainder", "integer"])

    def _compute_bar(self, cols: int) -> str:
        remaining_bar = cols - 2
        remaining_entries = self._total_entries

        # This next section heuristicly computes width of the different segments of a nice progress bar
        # It should:
        # - print at least 1 char for every non zero segment (except remaining)
        # - stay within bounds
        # - segments should not shrink
        # I will use indices to iterate over parts of the list
        portions = deepcopy(sorted(self._entries.items(), key=lambda kv: kv[1].count))
        it = 0

        # 1. skip all 0 width elements
        while it < len(portions) and portions[it][1].count == 0:
            it += 1

        # 2. set to 1 the width of all segments of width between 0 and 1 chars
        while it < len(portions):
            cnt = portions[it][1].count
            # cnt > entries/bar
            if cnt*remaining_bar > remaining_entries:
                break
            remaining_bar -= 1
            remaining_entries -= cnt
            portions[it][1].count = 1
            it += 1

        # 3. allocate rounded portion of the bar to the rest
        while it < len(portions):
            cnt = portions[it][1].count
            width = round(cnt*remaining_bar/remaining_entries)
            portions[it][1].count = width
            remaining_entries -= cnt
            remaining_bar -= width
            it += 1

        # Build progress bar string
        bar = "".join(
            f"{ti_parm('setab', cc.color)}{ti_parm('setaf', cc.color)}{k * cc.count}" \
            for k, cc in portions
        )
        return bar

    def update(self):
        cols = ti_get_num("cols")
        bar = self._compute_bar(cols)
        # Write + flush on a single frame
        with stdout_lock:
            self._display_bar(cols, bar)

    def _update_no_stdout_lock(self):
        assert stdout_lock.locked()
        cols = ti_get_num("cols")
        bar = self._compute_bar(cols)
        # Write + flush on a single frame
        self._display_bar(cols, bar)

    def update_with_value_and_log(self, entry: str, log: str):
        assert entry in self._entries
        with self._lock:
            self._entries[entry].count += 1
        with stdout_lock:
            stdout.write(ti_parm("setaf", self._entries[entry].color))
            stdout.write(log)
            stdout.write(ti_get_str("sgr0"))
            stdout.write("\n")
        self.update()

def run_subprocess(cmd: list[str], description: str, log_stem: Path | None = None, **kwargs) -> str | None:
    """
    Wrapper for running a subprocess and handling return value.
    All arguments other than `cmd`, `description`, and `log_stem` are passed to `subprocess.run`

    Return None if successful, an error message otherwise
    """
    print(description.capitalize(), "...", sep="")
    stdout, stderr = (DEVNULL, DEVNULL) if log_stem is None \
        else (open(f"{log_stem}.stdout.log", "w"), open(f"{log_stem}.stderr.log", "w"))
    try:
        cp = _run(cmd, stdout=stdout, stderr=stderr, **kwargs)
    finally:
        if log_stem is not None:
            stdout.close()
            stderr.close()
    if cp.returncode != 0:
        cmd = ' '.join(str(x) for x in cmd)
        error = f"`{cmd}` timed out after {kwargs['timeout']}s" if cp.returncode == 124 \
            else f"`{cmd}` failed with return code `{cp.returncode}`"
        detail = "" if log_stem is None \
            else f"\nFor more detail, see:\n\t{log_stem}.stdout.log\n\t{log_stem}.stderr.log"
        return f"Error when {description}: {error}{detail}"
    return None

def clean(top_dir: Path, timeout: int | None = 15) -> str | None:
    """
    Wrapper for `make clean`.

    Return None if successful, an error message otherwise
    """
    custom_env = environ.copy()
    custom_env["DEBUG"] = "1"
    return run_subprocess(
        cmd=["make", "-C", top_dir, "clean"],
        description="cleaning project",
        timeout=timeout,
        env=custom_env,
    )

def make(
    top_dir: Path,
    build_dir: Path,
    multithreading: int,
    log_stem: Path | None = None,
    timeout: int | None = 60
) -> str | None:
    """
    Wrapper for `make -C <top_dir> build/c_compiler`.

    Return None if successful, an error message otherwise
    """
    assert build_dir.is_relative_to(top_dir)

    # TODO: next year's Makefile should have a NDEBUG option instead of DEBUG
    custom_env = environ.copy()
    custom_env["DEBUG"] = "1"
    compiler = build_dir.relative_to(top_dir) / "c_compiler"
    return run_subprocess(
        cmd=["make", "-C", top_dir, compiler, "-j", str(multithreading)],
        description="building with make",
        log_stem=path_append(log_stem, ".make"),
        timeout=timeout,
        env=custom_env,
    )

# TODO: Is cmake worth using for performance? for features? for clarity?
def cmake(
    src_dir: Path,
    build_dir: Path,
    multithreading: int,
    log_stem: Path | None = None,
    timeout: int | None = 60
) -> str | None:
    """
    Wrapper for `cmake -S <src_dir> -B <build_dir>` then `cmake --build <build_dir>`

    Return None if successful, an error message otherwise
    """
    # cmake configure + generate
    # -DCMAKE_BUILD_TYPE=Release is equal to -O3
    conf_gen_success = run_subprocess(
        cmd=["cmake", "-S", top_dir, "-B", build_dir, "-DCMAKE_BUILD_TYPE=Release"],
        description="building with cmake (configure + generate)",
        log_stem=path_append(log_stem, ".cmake.conf_gen"),
        timeout=timeout,
    )
    if conf_gen_success is not None:
        return conf_gen_success

    # cmake compile
    return run_subprocess(
        cmd=["cmake", "--build", build_dir, "--parallel", str(multithreading)],
        description="building with cmake (compile)",
        log_stem=path_append(log_stem, ".cmake.compile"),
        timeout=timeout,
    )

def build(
    top_dir: Path,
    use_cmake: bool = False,
    coverage: bool = False,
    multithreading: int = 1,
    log_stem: Path | None = None,
    timeout: int | None = 60
) -> str | None:
    """
    Wrapper for building the student compiler.

    Return None if successful, an error message otherwise
    """
    # Prepare the build folder
    build_dir = top_dir / "build"
    Path(build_dir).mkdir(parents=True, exist_ok=True)

    # Build the compiler using cmake or make
    if use_cmake and not coverage:
        return cmake(
            src_dir=top_dir,
            build_dir=build_dir,
            multithreading=multithreading,
            log_stem=log_stem,
            timeout=timeout
        )
    if use_cmake and coverage:
        print(
            ti_parm("setaf", COLOR_RED),
            "Coverage is not supported with CMake. Switching to make.",
            ti_get_str("sgr0"),
            sep=""
        )
    return make(
        top_dir=top_dir,
        build_dir=build_dir,
        multithreading=multithreading,
        log_stem=log_stem,
        timeout=timeout
    )

def coverage(top_dir: Path, timeout: int | None = 60) -> str | None:
    """
    Wrapper for `make coverage`.

    Return None if successful, an error message otherwise
    """
    custom_env = environ.copy()
    custom_env["DEBUG"] = "1"
    return run_subprocess(
        cmd=["make", "-C", top_dir, "coverage"],
        description="generating coverage summary",
        timeout=timeout,
        env=custom_env
    )

# TODO: is this necessary? I believe it's not.
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
    print(f"Serving coverage on http://{host}:{port}/ ... (Ctrl+C to exit)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\nServer has been stopped!")

def student_compiler(compiler_path: Path, input_test: Path, output_stem: Path, timeout: int | None) -> str | None:
    """
    Wrapper for `build/c_compiler -S <input_test> -o <output_stem>.s`.

    Return None if successful, an error message otherwise
    """
    # Modifying environment to combat errors on memory leak
    custom_env = environ.copy()
    custom_env["ASAN_OPTIONS"] = f"log_path={output_stem}.asan.log"
    custom_env["UBSAN_OPTIONS"] = f"log_path={output_stem}.ubsan.log"

    log = run_subprocess(
        cmd=[compiler_path, "-S", input_test, "-o", f"{output_stem}.s"],
        description=f"compiling `{input_test.name}`",
        log_stem=path_append(output_stem, ".compiler"),
        env=custom_env,
        timeout=timeout
    )
    if log is not None:
        log += \
            f"\t{'\n\t'.join(output_stem.parent.glob('*san.log.*'))}" \
            f"\t{output_stem}.s\n\t{output_stem}.s.printed\n\t{output_stem}.gcc.s"
    return log

def fake_compiler(_input_test: Path, output_stem: Path, timeout: int | None) -> str | None:
    path_append(output_stem, ".s").symlink_to(path_append(output_stem, ".gcc.s"))
    return None

def run_test(
    compiler: Callable[[Path, Path, int], str | None],
    driver: Path,
    output_dir: Path,
    xml_file: JUnitXMLFile | None = None,
    progress_bar: AsyncProgressWithLog | None = None,
    timeout: int = 30
) -> str | None:
    """
    Run an instance of a test case.

    Parameters:
    - driver: path of the test driver.

    Returns Result object
    """
    assert driver.is_file()
    to_assemble = driver.with_stem(driver.stem.removesuffix("_driver"))
    assert to_assemble.is_file()

    # Construct the path where logs and outputs would be stored, without the suffix
    # e.g. .../build/output/_example/example/example
    output_stem = output_dir.joinpath(driver.parent.name, to_assemble.stem, to_assemble.stem)

    # Recreate the directory
    rmtree(output_stem.parent, ignore_errors=True)
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    # GCC Reference Output
    gcc = "riscv32-unknown-elf-gcc"
    # GCC is not targetting rv32imfd because it is compatible with rv32gc which is the more widespread 32bits target
    gcc_arch = "-march=rv32gc"
    gcc_abi = "-mabi=ilp32d"
    description = f"generating reference assembly for `{to_assemble.name}`"
    log = run_subprocess(
        cmd=[gcc, "-std=c90", "-pedantic-errors", "-ansi", "-O0", gcc_arch, gcc_abi, "-S", to_assemble, "-o", f"{output_stem}.gcc.s"],
        description=description,
        log_stem=path_append(output_stem, ".reference")
    )
    if log is not None:
        xml_file.log_failure(test_path=to_assemble, description=description, log=log)
        progress_bar.update_with_value_and_log(entry="I", log=log)
        return log

    # Compile
    log = compiler(to_assemble, output_stem, timeout)
    if log is not None:
        xml_file.log_failure(test_path=to_assemble, description=f"compiling `{to_assemble.name}`", log=log)
        progress_bar.update_with_value_and_log(entry="F", log=log)
        return log

    # Unexected files change a success to a warning
    expected_files = {
        path_append(output_stem, ".s"),
        path_append(output_stem, ".s.printed"),
        path_append(output_stem, ".compiler.stdout.log"),
        path_append(output_stem, ".compiler.stderr.log"),
        path_append(output_stem, ".gcc.s"),
        path_append(output_stem, ".reference.stdout.log"),
        path_append(output_stem, ".reference.stderr.log"),
    }
    unexpected_files = set(output_stem.parent.glob("*")) - expected_files

    # Assemble
    description = f"assembling for `{to_assemble.stem}`"
    log = run_subprocess(
        cmd=[gcc, gcc_arch, gcc_abi, "-c", f"{output_stem}.s", "-o", f"{output_stem}.o"],
        description=description,
        log_stem=path_append(output_stem, ".assembler")
    )
    if log is not None:
        xml_file.log_failure(test_path=to_assemble, description=description, log=log)
        progress_bar.update_with_value_and_log(entry="F", log=log)
        return log

    # Link
    description = f"linking `{output_stem.name}`"
    log = run_subprocess(
        cmd=[gcc, gcc_arch, gcc_abi, "-static", f"{output_stem}.o", driver, "-o", output_stem],
        description=description,
        log_stem=path_append(output_stem, ".linker"),
        timeout=timeout
    )
    if log is not None:
        xml_file.log_failure(test_path=to_assemble, description=description, log=log)
        progress_bar.update_with_value_and_log(entry="F", log=log)
        return log

    # Simulate
    description = f"simulating `{output_stem.name}`"
    log = run_subprocess(
        cmd=["spike", "--isa=rv32gc", "pk", output_stem],
        description=description,
        log_stem=path_append(output_stem, ".simulation"),
        timeout=timeout
    )
    if log is not None:
        xml_file.log_failure(test_path=to_assemble, description=description, log=log)
        progress_bar.update_with_value_and_log(entry="F", log=log)
        return log

    if len(unexpected_files) != 0:
        log = f"Warnings when compiling `{to_assemble}`, see\n\t{'\n\t'.join(unexpected_files)}"
        xml_file.log_success(test_path=to_assemble, log=log)
        progress_bar.update_with_value_and_log(entry="W", log=log)
        return log
    xml_file.log_success(test_path=to_assemble)
    progress_bar.update_with_value_and_log(entry="S", log="Passed `{to_assemble}`")
    return None

def run_tests(
    compiler: Callable[[Path, Path, int], tuple[int, int]],
    output_dir: Path,
    tests_dir: Path,
    xml_file: JUnitXMLFile,
    multithreading: int,
    timeout: int = 30
) -> tuple[int, int]:
    """
    Runs tests in <test_dir> against compiler provided by <compiler>.
    Compiler outputs are stored in <output_dir>.

    Return (# passed tests, # total tests)
    """
    assert output_dir.is_dir()
    # Nested directories are not supported because `run_test` doesn't support them
    drivers = list(tests_dir.glob("*/*_driver.c"))
    total = len(drivers)

    with AsyncProgressWithLog(
        total_entries=total,
        entries_display={"S": COLOR_GREEN, "W": COLOR_YELLOW, "F": COLOR_RED, "I": COLOR_MAGENTA}
    ) as apwl:
        if multithreading > 1:
            with ThreadPoolExecutor(max_workers=multithreading) as executor:
                futures = wait(executor.submit(
                    run_test,
                    compiler=compiler,
                    driver=driver,
                    output_dir=output_dir,
                    xml_file=xml_file,
                    progress_bar=apwl,
                    timeout=timeout
                ) for driver in drivers)
            logs = [f.result() for f in futures.completed if f.result() is not None]
        else:
            logs = []
            for driver in drivers:
                log = run_test(
                    compiler=compiler,
                    driver=driver,
                    output_dir=output_dir,
                    xml_file=xml_file,
                    progress_bar=apwl,
                    timeout=timeout
                )
                if log is not None:
                    logs.append(log)
        passed = apwl["S"]
        warning = apwl["W"]
        failed = apwl["F"]
        invalid = apwl["I"]

    print("".join(l + "\n\n" for l in logs), end="")
    print(
        "Test Summary:\n"
        f"\t{passed} Passed ({passed/total:.2%})\n"
        f"\t{warning} Warnings ({warning/total:.2%})\n"
        f"\t{failed} Failed ({failed/total:.2%})\n"
        f"\t{invalid} Invalid tests ({invalid/total:.2%})"
    )
    return passed, total

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
        help="(Optional) paths to the compiler test folders. Use this to select "
        "certain tests. Leave blank to run all tests."
    )
    cpus = cpu_count()
    parser.add_argument(
        "-m", "--multithreading",
        nargs="?",
        const=8 if cpus is None else cpus,
        default=1,
        type=int,
        metavar="N",
        help="Build compiler and run tests using multiple threads. "
        "Use -m to use the default thread count, or -m N to use exactly N threads. "
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
        clean_log = clean(top_dir=root_dir)
        if clean_log is not None:
            raise RuntimeError(clean_log)

    # Prepare the output folder
    rmtree(output_dir, ignore_errors=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # There is no need for building the student compiler when testing with riscv-gcc
    if not args.validate_tests:
        build_log = build(
            top_dir=root_dir,
            use_cmake=args.use_cmake,
            coverage=args.coverage,
            multithreading=args.multithreading,
            log_stem=build_dir / "build"
        )
        if build_log is not None:
            raise RuntimeError(build_log)

    # Run the tests and save the results into JUnit XML file
    with JUnitXMLFile(path=build_dir / "junit_results.xml", description="Compiler benchmark") as xml_file:
        passing, total = run_tests(
            compiler=fake_compiler if args.validate_tests \
                else lambda test, out, to: student_compiler(build_dir / "c_compiler", test, out, to),
            output_dir=output_dir,
            tests_dir=Path(args.dir),
            xml_file=xml_file,
            multithreading=args.multithreading
        )

    # Skip unavailable coverage and exit immediately for test validation
    if args.validate_tests:
        if passing != total:
            raise RuntimeError(f"{total - passing} tests failed during test validation")
        return

    # TODO: Is this necessary?
    # Find coverage if required. Note, that the coverage server will be blocking
    if args.coverage:
        coverage_log = coverage(top_dir=root_dir)
        if coverage_log is not None:
            raise RuntimeError(coverage_log)
        serve_coverage_forever("0.0.0.0", 8000)

if __name__ == "__main__":
    main()
    # I think this should not be necessary with the change to AsyncProgressWithLog
    # if stdout.isatty():
        # This solves dodgy terminal behaviour on multithreading
        # os.system("stty echo")
