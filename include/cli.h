#ifndef LANGPROC_COMPILER_CLI_H
#define LANGPROC_COMPILER_CLI_H

#include <iostream>
#include <unistd.h>

struct CommandLineArguments
{
    std::string compile_source_path;
    std::string compile_output_path;
};

CommandLineArguments ParseCommandLineArgs(int argc, char **argv);

#endif
