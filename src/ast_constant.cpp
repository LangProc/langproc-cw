#include "ast_constant.hpp"

namespace ast {

void IntConstant::EmitRISC(std::ostream& stream, Context&) const
{
    stream << "li a0, " << value_ << std::endl;
}

void IntConstant::Print(std::ostream& stream) const
{
    stream << value_;
}

} // namespace ast
