#pragma once

#include "ast_node.hpp"

namespace ast {

class IntConstant : public Node
{
private:
    int value_;

public:
    IntConstant(int value) : value_(value) {}

    void EmitRISC(std::ostream& stream, Context& context) const override;
    void Print(std::ostream& stream) const override;
};

} // namespace ast
