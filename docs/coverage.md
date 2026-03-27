# Coverage information

If you want to know which part of your code is executed (a.k.a. covered) when compiling all tests, use `test.py` without the `--optimise` flag.

This will generate a webpage `coverage/index.html` with a listing of all the source files and for each source file a listing of the number of times each line has been executed.
You can view the webpage in VS Code by right clicking on `coverage/index.html` then using `Show Preview`, or view it in a web browser by using a link printed by `test.py`.
VS Code will also display a warning on lines not executed.

![Index.html screenshot](./assets/coverage_example.png)

To know which lines are executed when a compiling single test, first make sure your compiler is built without optimisations (if you used the `--optimise` or `make` with `NDEBUG=1`, run `make clean && make`).
Then run your compiler on a file (`build/c_compiler -S [source-file.c] -o [dest-file.s]`).
Finally run `make coverage` to generate the coverage webpage and update the VS Code warnings.

## Adding tests

You can add a test by writing a test to be compiled by your compiler, and a driver.
Have a look at the example test in [tests/_example](../tests/_example); the driver is called [example_driver.c](../tests/_example/example_driver.c) and the test compiled by your compiler is called [example.c](../tests/_example/example.c).

The folder can have any name but the convention is to name it by the C language feature that the test is supposed to exercise in your compiler.
The file given to your compiler can have any name followed by the `.c` extension; I recommend the name reflects how the feature is tested.
The driver file _must_ have the same name as the test file but `.c` is replaced with `_driver.c`.

The driver file should contain a `main` function that takes no argument.
The return value of the `main` function must be 0 if the test is passed, or any non-zero _positive_ integer less than 127 and different than 124 (return value used to indicate a timeout) if the test is failed.
Although, you _definitely_ should use 1 to indicate a failure.
The driver file should also contain before `main` a prototype for every function in the test file given to your compiler that is called in the driver file.

You can check if your test is correct by running `test.py` with the `--validate_tests` flag.
If all found tests are correct, the command reports that all tests are valid, and the exit code is 0:

```console
> root@host:/workspaces/langproc-YYYY-cw-XXX# ./test.py --validate_tests
All 86 tests are valid!
> root@host:/workspaces/langproc-YYYY-cw-XXX# echo $?
0
```

otherwise you should see some errors:

```console
> root@host:/workspaces/langproc-YYYY-cw-XXX# ./test.py --validate_tests
tests/_example/example.c: Error when simulating with `spike --isa=rv32gc pk build/output/_example/example/example`, see:
        build/output/_example/example/example.simulation.stdout.log
        build/output/_example/example/example.simulation.stderr.log
        build/output/_example/example/example.c_compiler.stdout.log
        build/output/_example/example/example.c_compiler.stderr.log
        build/output/_example/example/example.s
        build/output/_example/example/example.gcc.s

1 tests failed during test validation
> root@host:/workspaces/langproc-YYYY-cw-XXX# echo $?
1
```
## Adding meaningful tests

A meaningful test is a test that isn't testing what other tests already test.
In other words a meaningful test improves the number of lines covered of the ideal correct compiler.
You should strive to add many meaningful tests to spot mistakes quickly before encoutering a problem down the line caused by a feature you were sure was correct.

In practice for the purposes of developping your compiler you should add two kind of tests:
1. tests revealing an incorrect behaviour of your compiler at the moment they were added, and
2. tests increasing the number of lines covered when compiling all tests.

To tests of the first kind, look at existing passing test cases thinking about what your compiler might do wrong if the tests were slightly different.
Then add that slightly different test.
Things to look for are:
* interesting values of integers (0, 1, 42, -1, the [minimum and maximum allowed value](https://en.cppreference.com/w/c/header/limits.html)),
* interesting values of strings and arrays,
* optimisations, unoptimisations, obfuscations,
* different way of expressing the same code (while-for substitutions, if-else branch swapping with condition inversion, expression rearrangement [but beware of floats](https://en.wikipedia.org/wiki/Floating-point_arithmetic#Accuracy_problems), etc.), and
* frowned upon, and [evil](https://en.wikipedia.org/wiki/Duff%27s_device) ways of writing C.

To add tests of the second kind:
1. generate coverage for all existing tests as explained at the start,
2. chose a section of code which isn't covered, preferably near an if statement or other kind of branching with a condition, and
3. try to come up with a valid test which makes the condition false (or true) so as to cover the section of code you chose.

Remember, there is no way to be sure a line not covered doesn't cause a crash in a marked tests; so go make that coverage percentage go up.
