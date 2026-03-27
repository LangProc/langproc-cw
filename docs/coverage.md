# Coverage information

If you want to know which part of your code is executed when compiling all tests, use `test.py` without the `--optimise` flag.

This will generate a webpage `coverage/index.html` with a listing of all the source files and for each source file a listing of the number of times each line has been executed.
VS Code will also display a warning on lines not executed.

![Index.html screenshot](./assets/coverage_example.png)

To know which lines are executed when a compiling single test, first make sure your compiler is built without optimisations (if you used the `--optimise` or `make` with `NDEBUG=1`, run `make clean && make`).
Then run your compiler on a file (`build/c_compiler -S [source-file.c] -o [dest-file.s]`).
Finally run `make coverage` to generate the coverage webpage and update the VS Code warnings.

## Viewing the coverage webpage

You can view the webpage by right clicking on `coverage/index.html` then using `Show Preview`, or in a web browser by using the link printed by `test.py`.
