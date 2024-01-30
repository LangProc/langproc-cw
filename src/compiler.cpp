#include <fstream>
#include <iostream>

#include "cli.h"
#include "ast.hpp"

int main(int argc, char **argv)
{
    // Parse CLI arguments to fetch the source file to compile and the path to output to.
    // This retrives [source-file.c] and [dest-file.s], when the compiler is invoked as follows:
    // ./bin/c_compiler -S [source-file.c] -o [dest-file.s]
    auto commandLineArguments = parseCommandLineArgs(argc, argv);

    // Parse input and generate AST
    std::cout << "Parsing: " << commandLineArguments.compileSourcePath << std::endl;
    auto root = parseAST(commandLineArguments.compileSourcePath);
    std::cout << "AST parsing complete" << std::endl;

    if (root == nullptr)
    {
        // Check something was actually returned by parseAST().
        std::cerr << "The root of the AST was a null pointer. Likely the root was never initialised correctly during parsing." << std::endl;
        return 3;
    }

    // Open the output files in truncation mode (to overwrite the contents)
    std::ofstream compiledOutput, prettyPrintOutput;
    compiledOutput.open(commandLineArguments.compileOutputPath, std::ios::trunc);

    auto prettyPrintOutputPath = commandLineArguments.compileOutputPath + ".printed";
    prettyPrintOutput.open(prettyPrintOutputPath, std::ios::trunc);

    // Emit assembler directives.
    // TODO: these are just examples ones, make sure you understand
    // the concept of directives and correct them. They likely should
    // be emitted elsewhere in your compiler.
    std::vector<std::string> directives = {"text", "globl f"};
    for (auto directive : directives)
    {
        compiledOutput << "." << directive << "\n";
    }
    compiledOutput << std::endl;

    // Output the pretty print version of what was parsed to the .printed output
    // file.
    std::cout << "Printing parsed AST..." << std::endl;
    root->print(prettyPrintOutput);
    prettyPrintOutput.close();
    std::cout << "Printed parsed AST to: " << prettyPrintOutputPath << std::endl;

    // Create a Context. This can be used to pass around information about
    // what's currently being compiled (e.g. function scope and variable names).
    Context ctx;

    // Compile from the root of the AST and output this to the compiledOutput
    // file.
    std::cout << "Compiling parsed AST..." << std::endl;
    root->emitRISC(compiledOutput, ctx);
    compiledOutput.close();
    std::cout << "Compiled to: " << commandLineArguments.compileOutputPath << std::endl;

    // Clean up afterwards.
    delete root;
    return 0;
}
