#include "ast_function_definition.hpp"

FunctionDefinition::FunctionDefinition(Node *declaration_specifiers, Node *declarator, Node *compound_statement)
{
    branches.insert(branches.end(), {declaration_specifiers, declarator, compound_statement});
}

void FunctionDefinition::emitRISC(std::ostream &stream, Context &context) const
{
    // Emit declarator
    branches[1]->emitRISC(stream, context);

    // Emit compound_statement
    if (branches[2] != nullptr)
    {
        branches[2]->emitRISC(stream, context);
    }
}

void FunctionDefinition::print(std::ostream &stream) const
{
    // TODO: this is not complete.
    branches[0]->print(stream);
    stream << " ";

    branches[1]->print(stream);
    stream << "() {" << std::endl;

    if (branches[2] != nullptr)
    {
        branches[2]->print(stream);
    }
    stream << "}" << std::endl;
}
