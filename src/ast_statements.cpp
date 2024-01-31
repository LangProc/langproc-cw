#include "ast_statements.hpp"

void ReturnStatement::EmitRISC(std::ostream &stream, Context &context) const
{
    // TODO: this implementation is incomplete
    std::cerr << "ReturnStatement: EmitRISC is not fully implemented." << std::endl;
    if (expression_ != nullptr)
    {
        expression_->EmitRISC(stream, context);
    }
    stream << "ret" << std::endl;
}

void ReturnStatement::Print(std::ostream &stream) const
{
    stream << "return";
    if (expression_ != nullptr)
    {
        stream << " ";
        expression_->Print(stream);
    }
    stream << ";" << std::endl;
}
