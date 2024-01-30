#include "ast_identifier.hpp"

void Identifier::emitRISC(std::ostream &stream, Context &context) const
{
    stream << identifier;
}
