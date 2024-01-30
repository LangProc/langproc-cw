#ifndef LANGPROC_COMPILER_CLI_H
#define LANGPROC_COMPILER_CLI_H

#include <iostream>
#include <unistd.h>

struct CommandLineArguments
{
    std::string compileSourcePath;
    std::string compileOutputPath;
};

CommandLineArguments parseCommandLineArgs(int argc, char **argv);

#endif
