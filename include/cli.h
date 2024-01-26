#ifndef LANGPROC_COMPILER_CLI_H
#define LANGPROC_COMPILER_CLI_H

#include <iostream>
#include <unistd.h>

int parseCommandLineArgs(int argc, char **argv, std::string &source_path, std::string &output_path);

#endif
