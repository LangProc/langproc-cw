#include <fstream>
#include <iostream>
#include <unistd.h>

#include "cli.h"
#include "ast.hpp"

int main(int argc, char **argv)
{
  // Parse CLI arguments, to fetch the values of the source and output files.
  std::string source_path = "";
  std::string output_path = "";
  if (parseCommandLineArgs(argc, argv, source_path, output_path)) {
    return 1;
  }

  // Parse input and generate AST
  Node* root = parseAST(source_path);

  // Open the output file in truncation mode (to overwrite the contents)
  std::ofstream output;
  output.open(output_path, std::ios::trunc);

  // Emit assembler directives
  // TODO these are just examples ones, make sure you understand the concept of directives and correct them
  std::vector<std::string> directives = {"text", "globl f"};
  for (auto directive : directives) {
    output << "." << directive << "\n";
  }
  output << std::endl;

  // Do actual compilation
  Context context;
  root->emitRISC(output, context);

  // Close output file
  output.close();

  return 0;
}
