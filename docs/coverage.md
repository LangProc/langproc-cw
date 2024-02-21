Coverage information
====================

If you want to know which part of your code is executed when running your compiler on a file you can build your compiler with `make with_coverage`, run your compiler on the file, then run `make coverage`.

This will generate a webpage `coverage/index.html` with a listing of all the source files and for each source file a listing of the number of times each line has been executed.

![Index.html screenshot](./coverage_example.png)

It can also be used automatically on all test files by running: `./scripts/test.py --coverage` or using the old test script: `COVERAGE=1 ./test.sh`.

## Viewing the coverage webpage

You can view the webpage in your browser by navigating to the coverage directory and running a Python HTTP server:

```console
> user@host:langproc-cw# cd coverage
> user@host:langproc-cw/coverage# python3 -m http.server
>
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

VS Code should prompt you to open the webpage in your browser.
You can also manually do so by navigating to [http://0.0.0.0:8000](`http://0.0.0.0:8000`).
