#pragma once

#include "ast_node.hpp"

namespace ast {

class DirectDeclarator : public Node
{
private:
    NodePtr identifier_;

public:
    DirectDeclarator(NodePtr identifier) : identifier_(std::move(identifier)){};

    void EmitRISC(std::ostream& stream, Context& context) const override;
    void Print(std::ostream& stream) const override;
};

} // namespace ast
