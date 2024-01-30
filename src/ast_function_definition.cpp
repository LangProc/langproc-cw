#include "ast_function_definition.hpp"

void FunctionDefinition::emitRISC(std::ostream &stream, Context &context) const
{
    // TODO: this is not complete.
    std::cerr << "FunctionDefinition: emitRISC is not fully implemented." << std::endl;

    // Emit assembler directives.
    // TODO: these are just examples ones, make sure you understand
    // the concept of directives and correct them.
    stream << ".text" << std::endl;
    stream << ".globl f" << std::endl;

    this->declarator->emitRISC(stream, context);

    if (this->compoundStatement != nullptr)
    {
        this->compoundStatement->emitRISC(stream, context);
    }
}

void FunctionDefinition::print(std::ostream &stream) const
{
    // TODO: this is not complete.
    std::cerr << "FunctionDefinition: print is not fully implemented." << std::endl;

    this->declarationSpecifiers->print(stream);
    stream << " ";

    this->declarator->print(stream);
    stream << "() {" << std::endl;

    if (this->compoundStatement != nullptr)
    {
        this->compoundStatement->print(stream);
    }
    stream << "}" << std::endl;
}
