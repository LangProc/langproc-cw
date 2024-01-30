#include "ast_statements.hpp"

void ReturnStatement::emitRISC(std::ostream &stream, Context &context) const
{
    // TODO: this implementation is incomplete
    std::cerr << "ReturnStatement: emitRISC is not fully implemented." << std::endl;
    if (this->expression != nullptr)
    {
        expression->emitRISC(stream, context);
    }
    stream << "ret" << std::endl;
}

void ReturnStatement::print(std::ostream &stream) const
{
    stream << "return";
    if (this->expression != nullptr)
    {
        stream << " ";
        expression->print(stream);
    }
    stream << ";" << std::endl;
}
