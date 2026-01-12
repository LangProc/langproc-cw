#pragma once

#include <unistd.h>

#include <iostream>

struct CommandLineArguments {
  std::string compile_source_path;
  std::string compile_output_path;
};

CommandLineArguments ParseCommandLineArgs(int argc, char **argv);
