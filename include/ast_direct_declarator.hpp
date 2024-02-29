#pragma once

#include "ast_node.hpp"

namespace AST {

class DirectDeclarator : public Node
{
private:
    NodePtr identifier_;

public:
    DirectDeclarator(Node* identifier) : identifier_(identifier){};

    void EmitRISC(std::ostream& stream, Context& context) const override;
    void Print(std::ostream& stream) const override;
};

} // namespace AST
