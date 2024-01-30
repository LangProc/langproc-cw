#include "ast_direct_declarator.hpp"

void DirectDeclarator::emitRISC(std::ostream &stream, Context &context) const
{
    identifier->emitRISC(stream, context);
    stream << ":" << std::endl;
}

void DirectDeclarator::print(std::ostream &stream) const
{
    identifier->print(stream);
}
