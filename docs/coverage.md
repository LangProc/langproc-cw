Coverage information
====================

If you want to know which part of your code is executed when running your compiler on a file you can build your compiler with `make with_coverage`, run your compiler on the file, then run `make coverage`.

This will generate a webpage `coverage/index.html` with a listing of all the source files and for each source file a listing of the number of times each line has been executed.

![Index.html screenshot](./coverage_example.png)

It can also be used automatically on all test files by running
`scripts/test.sh coverage`.
