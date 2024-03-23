#include <fstream>
#include <iostream>

#include "cli.hpp"
#include "ast.hpp"

using ast::NodePtr;

// Wrapper for ParseAST defined in YACC
NodePtr Parse(const std::string& compile_source_path);

// Output the pretty print version of what was parsed to the .printed output file.
void PrettyPrint(const NodePtr& root, const std::string& compile_output_path);

// Compile from the root of the AST and output this to the compiledOutputPath file.
void Compile(const NodePtr& root, const std::string& compile_output_path);

int main(int argc, char **argv)
{
    // Parse CLI arguments to fetch the source file to compile and the path to output to.
    // This retrives [source-file.c] and [dest-file.s], when the compiler is invoked as follows:
    // ./bin/c_compiler -S [source-file.c] -o [dest-file.s]
    const auto [compile_source_path, compile_output_path] = ParseCommandLineArgs(argc, argv);

    // Parse input and generate AST.
    auto ast_root = Parse(compile_source_path);

    // Check something was actually returned by parseAST().
    if (ast_root == nullptr)
    {
        std::cerr << "The root of the AST is a null pointer. ";
        std::cerr << "Likely the root was never initialised correctly during parsing." << std::endl;
        return 3;
    }

    // Print AST in a human-readable way. It's not assessed, but exists for your convenience.
    PrettyPrint(ast_root, compile_output_path);

    // Compile to RISC-V assembly, the main goal of this project.
    Compile(ast_root, compile_output_path);
}

NodePtr Parse(const std::string& compile_source_path)
{
    std::cout << "Parsing ..." << compile_source_path << std::endl;

    NodePtr root = ParseAST(compile_source_path);

    std::cout << "AST parsing complete" << std::endl;

    return root;
}

void PrettyPrint(const NodePtr& root, const std::string& compile_output_path)
{
    auto output_path = compile_output_path + ".printed";

    std::cout << "Printing parsed AST..." << std::endl;

    std::ofstream output(output_path, std::ios::trunc);
    root->Print(output);

    std::cout << "Printed parsed AST to: " << output_path << std::endl;
}

void Compile(const NodePtr& root, const std::string& compile_output_path)
{
    // Create a Context. This can be used to pass around information about
    // what's currently being compiled (e.g. function scope and variable names).
    ast::Context ctx;

    std::cout << "Compiling parsed AST..." << std::endl;

    std::ofstream output(compile_output_path, std::ios::trunc);
    root->EmitRISC(output, ctx);

    std::cout << "Compiled to: " << compile_output_path << std::endl;
}
