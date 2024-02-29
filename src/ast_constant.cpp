#include "ast_constant.hpp"

namespace AST {

void IntConstant::EmitRISC(std::ostream& stream, Context& context) const
{
    stream << "li a0, " << value_ << std::endl;
}

void IntConstant::Print(std::ostream& stream) const
{
    stream << value_;
}

} // namespace AST
