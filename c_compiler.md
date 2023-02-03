Main coursework: A compiler for the C language
==============================================

Your program should read C source code from a file, and write RISC-V assembly to another file.

Environment
-----------

An Ubuntu 22.04 Dockerfile has been provided which defines all of the tools you need to get started, just like the labs.

It is strongly suggested that you do your final testing before each submission in this environment, otherwise you are likely to hit incompatibility problems, which may mean your program won't build in my test environment.

Many students develop their compiler in VS Code, as this has good support for collaborative programming and working inside Docker containers. Instructions for getting set up in VS Code are provided below. More generic instructions for those using other editors are also provided, further down the page.

### VS Code + Docker (the most popular option)

1) Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). If you are on Apple M1/M2, make sure to choose the Apple Silicon download.
2) Open VS Code and install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension
3) Open the folder containing this file, in VS Code
4) Open the Command Palette in VS Code. You can do this by the shortcut `Ctrl + Shift + P` on Windows or `Cmd + Shift + P` on Mac. Alternatively, you can access this from `View -> Command Palette`.
5) Enter `>Dev Containers: Reopen in Container` into the Command Palette
6) After a delay -- depending on how fast your Internet connection can download ~1GB -- you will now be in the container environment. For those interested, VS Code reads the container configuration from the [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) file.
7) Test that your tools are correctly setup by running `./toolchain_test.sh` in the VS Code terminal, accessible via `Terminal -> New Terminal`. Your output should look as follows:

    ```console
    root@e3221f21a2a1:/workspaces/langproc-env# ./toolchain_test.sh

    g++ -std=c++20 -W -Wall -g -I include -o bin/c_compiler src/cli.cpp src/compiler.cpp

    Compiling: compiler_tests/_example/example.c
    Compiled to: bin/riscv_example.s

    bbl loader
    Hello from RISC-V
    Test function produced value: 8.700000
    Example function returned: 5
    Test successful
    ```

### Another Editor + Docker

> Warning for Windows users: if you are running Windows and use this method, you may experience errors related to the line endings of your files. Windows uses the special characters CRLF (`\r\n`) to represent the end of a line, whereas Linux uses just LF (`\n`). As such, if you edit these files on Windows they are most likely to be saved using CRLF. See if you can change your editor to use LF file endings or, even better, see if your editor supports [EditorConfig](https://editorconfig.org/), which standardises formatting across all files based on the [.editorconfig](.editorconfig) file in the same folder as this file.

1) Install [Docker](https://www.docker.com/products/docker-desktop/). If you are on Apple M1/M2, make sure to choose the Apple Silicon download.
2) Open a terminal (Powershell on Windows; Terminal on Mac) to the folder containing this file
3) Inside that terminal, run `docker build -t compilers_image .`
4) Once that completes, run `docker run --rm -it -v "${PWD}:/code" -w "/code" --name "compilers_env" compilers_image`
5) You should now be inside the LangProc tools container, where you can run `./toolchain_test.sh` inside the `/code` folder to check that your tools are working correctly. Note that the folder containing this file, as well as any subdirectories, are mounted inside this container under the path `/code`. The output of running the command should look as follows:

    ```console
    root@ad12f00322f6:/code# ./toolchain_test.sh

    g++ -std=c++20 -W -Wall -g -I include -o bin/c_compiler src/cli.cpp src/compiler.cpp

    Compiling: compiler_tests/_example/example.c
    Compiled to: bin/riscv_example.s

    bbl loader
    Hello from RISC-V
    Test function produced value: 8.700000
    Example function returned: 5
    Test successful
    ```

Developing your compiler
------------------------

If you wish to use C++, then a basic framework for building your compiler has been provided.

Source files can be found in the [./src](./src) folder and header files can be found in the [./include](./include) folder.

You can test your compiler against the provided test-suite by running `./test.sh` from the folder containing this file; the output should look as follows:

```console
root@host:/workspaces/langproc-env# ./test.sh

g++ -std=c++20 -W -Wall -g -I include -o bin/c_compiler src/cli.cpp src/compiler.cpp

compiler_tests/_example/example.c
        > Pass
compiler_tests/array/declare_global.c
        > Fail: simulation did not exit with exit-code 0
```

By default, the first `_example/example.c` test should be passing.

This basic framework ignores the source input file and always produces the same assembly, which loads the value `5` into `a0`.

Program build and execution
---------------------------

Your program should be built by running the following command in the top-level directory of your repo:

    make bin/c_compiler

The compilation function is invoked using the flag `-S`, with the source file and output file specified on the command line:

    bin/c_compiler -S [source-file.c] -o [dest-file.s]

You can assume that the command-line arguments will always be in this order, and that there will be no spaces in source or destination paths.

Input
-----

The input file will be pre-processed [ANSI C](https://en.wikipedia.org/wiki/ANSI_C), also called C90 or C89. It's what's generally thought of as "classic" or "normal" C, but not the _really_ old one without function prototypes (you may never have come across that). C90 is still often used in embedded systems, and pretty much the entire Linux kernel is in C90.

You've mainly been taught C++, but you're probably aware of C as a subset of C++ without classes, which is a good mental model. Your programs (lexer, parser and compiler) will never be given code that has different parsing or execution semantics under C and C++ (so, for example, I won't give you code that uses `class` as an identifier).

The source code will not contain any compiler-specific or platform-specific extensions. If you pre-process a typical program (see later), you'll see many things such as `__attribute__` or `__declspec` coming from the system headers. You will not need to deal with any of these.

The test inputs will be a set of files of increasing complexity and variety. The test inputs will not have syntax errors or other programming errors, so your code does not need to handle these gracefully.

Here is a list of basic features that you might like to implement first.

* a file containing just a single function with no arguments
* variables of `int` type
* local variables
* arithmetic and logical expressions
* if-then-else statements
* while loops

Here is a list of intermediate features that you might like to implement once the basic features are working.

* files containing multiple functions that call each other
* functions that take up to four parameters
* for loops
* arrays declared globally (i.e. outside of any function in your file)
* arrays declared locally (i.e. inside a function)
* reading and writing elements of an array
* recursive function calls
* the `enum` keyword
* `switch` statements
* the `break` and `continue` keywords

Here is a list of more advanced features like you might like to implement once the basic and intermediate features are working.

* variables of `double`, `float`, `char`, `unsigned`, structs, and pointer types
* calling externally-defined functions (i.e. the file being compiled declares a function, but its definition is provided in a different file that is linked in later on)
* functions that take more than four parameters
* mutually recursive function calls
* locally scoped variable declarations (e.g. a variable that is declared inside the body of a while loop, such as `while(...) { int x = ...; ... }`.
* the `typedef` keyword
* the `sizeof(...)` function (which takes either a type or a variable)
* taking the address of a variable using the `&` operator
* dereferencing a pointer-variable using the `*` operator
* pointer arithmetic
* character literals, including escape sequences like `\n`
* strings (as NULL-terminated character arrays)
* declaration and use of structs

Your compiler will be assessed using test inputs that exercise the above features. No feature not listed above will be tested.
Here is a (partial) list of features that will not be tested.

* multithreading
* the `goto` keyword
* macros and other preprocessing directives
* the comma operator (for sequencing within expressions)
* the [old K&R style of declaring functions](https://stackoverflow.com/a/18820829)
* union types
* variable-length arrays
* the `const` keyword
* function pointers
* both implicit and explicit casting

All test inputs will be valid; that is, you can assume the absence of programmer errors like syntax faults, type mismatches, and array out-of-bounds errors. The entire compilation and testing process (including compilation, assembly, linking, and RISC-V simulation) is expected to complete within ten seconds per program (which should be plenty of time!), and is expected not to use an inordinate amount of memory or disk space. There is no requirement for the generated assembly to be optimised in any way -- the only requirement is that it produces the correct answer.

The [compiler_tests](compiler_tests) contains a large number of example inputs, divided into various categories, that you might like to use as testcases. Your compiler will be assessed on these "seen" inputs together with a further set of "unseen" inputs that are of a similar form. It is worth emphasising that it is not expected that many compilers will correctly compile all of the "seen" inputs (let alone the "unseen" ones!). You are encouraged to focus on compiling the "basic" features (as listed above) first, before moving on to more advanced features if you have time.

Output Format
-------------

The output format should be RISC-V assembly code.

It should be possible to assemble and link this code against a C run-time, and have it execute correctly on a MIPS processor as emulated by `spike`.

For instance, suppose I have a file called `test_program.c` that contains:

    int f() { return 10; }

and another file called `test_program_driver.c` that contains:

    int f();
    int main() { return !( 10 == f() ); }

I run the compiler on the test program, like so:

    bin/c_compiler -S test_program.c -o test_program.s

I then use GCC to assemble the generated assembly program (`test_program.s`), like so:

    riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -o test_program.o -c test_program.s

I then use GCC to link the generated object file (`test_program.o`) with the driver program (`test_program_driver.c`), to produce an executable (`test_program`), like so:

    riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -static -o test_program test_program.o test_program_driver.c

I then use spike to simulate the executable on RISC-V, like so:

    spike pk test_program

This command should produce the exit code `0`.
