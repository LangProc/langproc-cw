# Coverage information

If you want to know which part of your code is executed (a.k.a. covered) when compiling all tests, run `./test.py` without the `--optimise` flag. Make sure to pass `--clean` flag if you have built with optimisations before.

This will generate a webpage `coverage/index.html` which shows the number of times each line has been executed for each source file `.c`.
You can view the webpage in VS Code by right clicking on `coverage/index.html` then using `Show Preview`, or view it in a web browser by using a link printed by `test.py`.
VS Code will also display a warning on lines not executed.

![Index.html screenshot](./assets/coverage_example.png)

To know which lines are executed when compiling a single test, run your compiler on a file (`build/c_compiler -S [source-file.c] -o [dest-file.s]`).
Then, run `make coverage` to generate the coverage webpage and update the VS Code warnings.

## Adding tests

You can add a test by writing a test (see [_example/example.c](../tests/_example/example.c)) to be compiled by your compiler, and its driver (see [_example/example_driver.c](../tests/_example/example_driver.c)).

The folder can have any name but the convention is to name it by the C language feature that the test is supposed to exercise in your compiler.
The file given to your compiler can have any name followed by the `.c` extension, like `<feature>.c`. It is helpful for the name to reflect how the feature is tested.
The driver file **must** match the test case, like `<feature>_driver.c`.

The driver file must contain a `main()` function that takes no argument.
The return value of the `main` function must be 0 if the test is passed, or any non-zero _positive_ integer less than 127 and different than 124 (return value used to indicate a timeout) if the test is failed.
Although, you _definitely_ should use 1 to indicate a failure.
The driver file should also contain a prototype for every function declared in the test file that is called in `main`.

You can check if your test is correct by running `./test.py` with the `--validate_tests` flag:

```console
> root@host:/workspaces/langproc-YYYY-cw-XXX# ./test.py --validate_tests
All 86 tests are valid!
```

In case of errors, you would see:

```console
> root@host:/workspaces/langproc-YYYY-cw-XXX# ./test.py --validate_tests
tests/_example/example.c: Error when simulating with `spike --isa=rv32gc pk build/output/_example/example/example`, see:
        build/output/_example/example/example.simulation.stdout.log
        build/output/_example/example/example.simulation.stderr.log
        build/output/_example/example/example.c_compiler.stdout.log
        build/output/_example/example/example.c_compiler.stderr.log
        build/output/_example/example/example.s
        build/output/_example/example/example.gcc.s

Number of tests failed during test validation: 1
```
## Adding meaningful tests

A meaningful test is a test that isn't testing what other tests already test.
In other words, a meaningful test improves the number of lines covered of the ideal correct compiler.
You should strive to add many meaningful tests to spot mistakes quickly before encountering a problem down the line caused by a feature you were sure was correct.

In practice for the purposes of developing your compiler you should add two kind of tests:
1. tests revealing an incorrect behaviour of your compiler at the moment they are added
2. tests increasing the number of covered lines in source files

For tests of the first kind, look at existing passing test cases and think about what your compiler might do wrong if the tests were slightly different, especially in corner cases.
Things to look for are:
* interesting values of integers (0, 1, 42, -1, the [minimum and maximum allowed values](https://en.cppreference.com/w/c/header/limits.html))
* unusual values of strings and arrays
* optimisations, simplifications, obfuscations
* different way of expressing the same code (while-for substitutions, if-else branch swapping with condition inversion, expression rearrangement [but beware of floats](https://en.wikipedia.org/wiki/Floating-point_arithmetic#Accuracy_problems), etc.)
* frowned upon, and [evil](https://en.wikipedia.org/wiki/Duff%27s_device) ways of writing C

To add tests of the second kind:
1. Generate coverage for all existing tests as explained at the start
2. Choose a section of code which isn't covered, preferably near an if statement or other kind of branching with a condition
3. Try to come up with a valid test which triggers that condition to cover the yet-uncovered section of code

Remember, an uncovered line is never actually tested. Hence, it is possible for it to cause a crash during an unseen test - so go make that coverage percentage go up!
