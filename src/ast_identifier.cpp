#include "ast_identifier.hpp"

namespace AST {

void Identifier::EmitRISC(std::ostream& stream, Context& context) const
{
    stream << identifier_;
}

void Identifier::Print(std::ostream& stream) const
{
    stream << identifier_;
};

}
