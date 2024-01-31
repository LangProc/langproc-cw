#include "ast_identifier.hpp"

void Identifier::EmitRISC(std::ostream &stream, Context &context) const
{
    stream << identifier_;
}

void Identifier::Print(std::ostream &stream) const
{
    stream << identifier_;
};
