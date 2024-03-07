#pragma once

#include "ast_node.hpp"

namespace ast {

class ReturnStatement : public Node
{
private:
    NodePtr expression_;

public:
    ReturnStatement(Node* expression) : expression_(expression) {}

    void EmitRISC(std::ostream& stream, Context& context) const override;
    void Print(std::ostream& stream) const override;
};

} // namespace ast
