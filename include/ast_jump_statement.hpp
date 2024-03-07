#pragma once

#include "ast_node.hpp"

namespace ast {

class ReturnStatement : public Node
{
private:
    NodePtr expression_;

public:
    ReturnStatement(NodePtr expression) : expression_(std::move(expression)) {}

    void EmitRISC(std::ostream& stream, Context& context) const override;
    void Print(std::ostream& stream) const override;
};

} // namespace ast
