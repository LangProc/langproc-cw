#include <fstream>
#include <iostream>

#include "cli.h"
#include "ast.hpp"

Node *Parse(CommandLineArguments &args)
{
    std::cout << "Parsing: " << args.compile_source_path << std::endl;
    auto root = ParseAST(args.compile_source_path);
    std::cout << "AST parsing complete" << std::endl;
    return root;
}

// Output the pretty print version of what was parsed to the .printed output
// file.
void PrettyPrint(Node *root, CommandLineArguments &args)
{
    auto output_path = args.compile_output_path + ".printed";

    std::cout << "Printing parsed AST..." << std::endl;
    std::ofstream output(output_path, std::ios::trunc);
    root->Print(output);
    output.close();
    std::cout << "Printed parsed AST to: " << output_path << std::endl;
}

// Compile from the root of the AST and output this to the
// args.compiledOutputPath file.
void Compile(Node *root, CommandLineArguments &args)
{
    // Create a Context. This can be used to pass around information about
    // what's currently being compiled (e.g. function scope and variable names).
    Context ctx;

    std::cout << "Compiling parsed AST..." << std::endl;
    std::ofstream output(args.compile_output_path, std::ios::trunc);
    root->EmitRISC(output, ctx);
    output.close();
    std::cout << "Compiled to: " << args.compile_output_path << std::endl;
}

int main(int argc, char **argv)
{
    // Parse CLI arguments to fetch the source file to compile and the path to output to.
    // This retrives [source-file.c] and [dest-file.s], when the compiler is invoked as follows:
    // ./bin/c_compiler -S [source-file.c] -o [dest-file.s]
    auto command_line_arguments = ParseCommandLineArgs(argc, argv);

    // Parse input and generate AST
    auto ast_root = Parse(command_line_arguments);
    if (ast_root == nullptr)
    {
        // Check something was actually returned by parseAST().
        std::cerr << "The root of the AST was a null pointer. Likely the root was never initialised correctly during parsing." << std::endl;
        return 3;
    }

    PrettyPrint(ast_root, command_line_arguments);
    Compile(ast_root, command_line_arguments);

    // Clean up afterwards.
    delete ast_root;
    return 0;
}
