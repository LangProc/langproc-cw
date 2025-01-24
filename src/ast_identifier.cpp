#include "ast_identifier.hpp"

namespace ast {

void Identifier::EmitRISC(std::ostream& stream, Context&) const
{
    stream << identifier_;
}

void Identifier::Print(std::ostream& stream) const
{
    stream << identifier_;
};

}
