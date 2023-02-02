#ifndef LANGPROC_COMPILER_CLI_H
#define LANGPROC_COMPILER_CLI_H

#include <iostream>
#include <unistd.h>

int parse_command_line_args(int argc, char **argv, std::string &sourcePath, std::string &outputPath);

#endif
