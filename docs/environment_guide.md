Environment
===========

An Ubuntu 22.04 Dockerfile has been provided which defines all of the tools you need to get started, just like the labs.

It is strongly suggested that you do your final testing before each submission in this environment, otherwise you are likely to hit incompatibility problems, which may mean your program won't build in my test environment.

Many students develop their compiler in VS Code, as this has good support for collaborative programming and working inside Docker containers. Instructions for getting set up in VS Code are provided below. More generic instructions for those using other editors are also provided, further down the page.

### VS Code + Docker (the most popular option)

1) Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). If you are on Apple M1/M2, make sure to choose the Apple Silicon download.
2) Open VS Code and install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension.
3) Open the top folder of your repo (`/langproc-cw-.../`), in VS Code.
4) Open the Command Palette in VS Code:
    - Windows: `Ctrl + Shift + P`
    - Mac OS: `Cmd + Shift + P`
    - Alternatively, you can access this from the menu bar `View -> Command Palette`.
5) Enter `>Dev Containers: Reopen in Container` into the Command Palette.
6) After a delay you will now be in the container environment.
    - The delay will vary based on how fast you can download around 1GB over your Internet connection.
    - For those interested, VS Code reads the container configuration from the [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) file.
7) Test that your tools are correctly setup by running `./scripts/toolchain_test.sh` in the VS Code terminal, accessible via `Terminal -> New Terminal`. Your output should look as follows:

```console
> user@host:langproc-cw# ./scripts/toolchain_test.sh
>
[...]

Parsing: compiler_tests/_example/example.c
AST parsing complete
Printing parsed AST...
Printed parsed AST to: bin/riscv_example.s.printed
Compiling parsed AST...
Compiled to: bin/riscv_example.s
bbl loader
Hello from RISC-V
Test function produced value: 8.700000
Example function returned: 5
Test successful
```

8) You might also benefit from installing VS Code extensions for C++, Lex, and Yacc for better text highlighting and easier debugging. For example, you can press F5 (or fn + F5) to start the integrated VS Code debugger. By default, this attempts to compile [compiler_tests/_example/example.c](../compiler_tests/_example/example.c), as specified in [.vscode/launch.json](../.vscode/launch.json).



### Another Editor + Docker

> Warning for Windows users: if you are running Windows and use this method, you may experience errors related to the line endings of your files. Windows uses the special characters CRLF (`\r\n`) to represent the end of a line, whereas Linux uses just LF (`\n`). As such, if you edit these files on Windows they are most likely to be saved using CRLF. See if you can change your editor to use LF file endings or, even better, see if your editor supports [EditorConfig](https://editorconfig.org/), which standardises formatting across all files based on the [.editorconfig](.editorconfig) file in the same folder as this file.

1) Install [Docker](https://www.docker.com/products/docker-desktop/). If you are on Apple M1/M2, make sure to choose the Apple Silicon download.
2) Open a terminal (Powershell on Windows; Terminal on Mac) to the folder containing this file.
3) Inside that terminal, run `docker build -t compilers_image .` to build the Docker container image
4) Once that completes, run the following command to start the Docker container

    ```bash
    docker run --rm -it -v "${PWD}:/code" -w "/code" --name "compilers_env" compilers_image
    ```

5) You should now be inside the LangProc tools container, where you can run `./scripts/toolchain_test.sh` inside the `/code` folder to check that your tools are working correctly. Note that the folder containing this file, as well as any subdirectories, are mounted inside this container under the path `/code`. The output of running the command should look as follows:


    ```console
    root@ad12f00322f6:/code# ./scripts/toolchain_test.sh

    g++ -std=c++20 -W -Wall -g -I include -o bin/c_compiler src/cli.cpp src/compiler.cpp

    Compiling: compiler_tests/_example/example.c
    Compiled to: bin/riscv_example.s

    Parsing: compiler_tests/_example/example.c
    AST parsing complete
    Printing parsed AST...
    Printed parsed AST to: bin/riscv_example.s.printed
    Compiling parsed AST...
    Compiled to: bin/riscv_example.s
    bbl loader
    Hello from RISC-V
    Test function produced value: 8.700000
    Example function returned: 5
    Test successful
    ```
