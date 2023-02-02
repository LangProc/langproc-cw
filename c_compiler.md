Deliverable 3: A compiler for the C language
============================================

Your program should read C source code from a file, and write RISC-V assembly to another file.

Environment
-----------

The target environment for the coursework is Ubuntu 22.04, just like the labs. It is strongly suggested that you do your final testing before each submission in this environment, otherwise you are likely to hit incompatibility problems, which may mean your program won't build in my test environment.

This repository contains a [Dockerfile](Dockerfile), which is a script that sets up a blank Ubuntu 22.04 environment, and then installs all the tools that are needed for building and testing your compiler. If you configure your testing environment to match the Dockerfile script, you should be fine.

You can enter the virtual machine described by the Dockerfile by going to the directory that contains the Dockerfile and running the following series of commands. First, create the virtual machine "image" by running:

    docker build -t "compilers_cw" .
	
(The `.` at the end is part of the command, by the way. It tells Docker to look in the current directory for the Dockerfile script.) Then create a "container" so that you can enter the virtual machine by running:

    docker run -it -v "`pwd`:`pwd`" -w "`pwd`" --name "compilers_cw_machine" compilers_cw
	
You are now in an Ubuntu 22.04 shell with all the required tools installed. (By the way, the `-it` flag instructs Docker to create a shell through which you can interact with the virtual machine. The `-v pwd:pwd` and `-w pwd` flags mean that your host machine's files are accessible to your virtual machine.) 

When you're finished, you can leave the shell by typing:

    exit
	
If you want to clean up, you can remove the container you created by typing:

	docker ps -a
	docker rm compilers_cw_machine
	
and then removing the image by typing:

	docker images
	docker rmi compilers_cw


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

    gcc-r5 -mfp32 -o test_program.o -c test_program.s
    
I then use GCC to link the generated object file (`test_program.o`) with the driver program (`test_program_driver.c`), to produce an executable (`test_program`), like so:

    mips-linux-gnu-gcc -mfp32 -static -o test_program test_program.o test_program_driver.c

I then use spike to simulate the executable on RISC-V, like so:

    spike test_program
    
This command should produce the exit code `0`.
