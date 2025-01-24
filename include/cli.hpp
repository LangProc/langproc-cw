#pragma once

#include <iostream>
#include <unistd.h>

struct CommandLineArguments
{
    std::string compile_source_path;
    std::string compile_output_path;
};

CommandLineArguments ParseCommandLineArgs(int argc, char **argv);
