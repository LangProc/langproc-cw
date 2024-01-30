#include "ast_type_specifier.hpp"

void TypeSpecifier::emitRISC(std::ostream &stream, Context &context) const {}

void TypeSpecifier::print(std::ostream &stream) const
{
    stream << type;
}
