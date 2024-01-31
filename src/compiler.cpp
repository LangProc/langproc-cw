#include <fstream>
#include <iostream>

#include "cli.h"
#include "ast.hpp"

Node *parse(CommandLineArguments &args)
{
    std::cout << "Parsing: " << args.compileSourcePath << std::endl;
    auto root = parseAST(args.compileSourcePath);
    std::cout << "AST parsing complete" << std::endl;
    return root;
}

// Output the pretty print version of what was parsed to the .printed output
// file.
void prettyPrint(Node *root, CommandLineArguments &args)
{
    auto outputPath = args.compileOutputPath + ".printed";

    std::cout << "Printing parsed AST..." << std::endl;
    std::ofstream output(outputPath, std::ios::trunc);
    root->print(output);
    output.close();
    std::cout << "Printed parsed AST to: " << outputPath << std::endl;
}

// Compile from the root of the AST and output this to the
// args.compiledOutputPath file.
void compile(Node *root, CommandLineArguments &args)
{
    // Create a Context. This can be used to pass around information about
    // what's currently being compiled (e.g. function scope and variable names).
    Context ctx;

    std::cout << "Compiling parsed AST..." << std::endl;
    std::ofstream output(args.compileOutputPath, std::ios::trunc);
    root->emitRISC(output, ctx);
    output.close();
    std::cout << "Compiled to: " << args.compileOutputPath << std::endl;
}

int main(int argc, char **argv)
{
    // Parse CLI arguments to fetch the source file to compile and the path to output to.
    // This retrives [source-file.c] and [dest-file.s], when the compiler is invoked as follows:
    // ./bin/c_compiler -S [source-file.c] -o [dest-file.s]
    auto commandLineArguments = parseCommandLineArgs(argc, argv);

    // Parse input and generate AST
    auto astRoot = parse(commandLineArguments);
    if (astRoot == nullptr)
    {
        // Check something was actually returned by parseAST().
        std::cerr << "The root of the AST was a null pointer. Likely the root was never initialised correctly during parsing." << std::endl;
        return 3;
    }

    prettyPrint(astRoot, commandLineArguments);
    compile(astRoot, commandLineArguments);

    // Clean up afterwards.
    delete astRoot;
    return 0;
}
