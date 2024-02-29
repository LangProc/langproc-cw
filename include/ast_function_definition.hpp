#pragma once

#include "ast_node.hpp"
#include "ast_type_specifier.hpp"

namespace AST {

class FunctionDefinition : public Node
{
private:
    const TypeSpecifier declaration_specifiers_;
    NodePtr declarator_;
    NodePtr compound_statement_;

public:
    FunctionDefinition(TypeSpecifier declaration_specifiers, Node* declarator, Node* compound_statement) : declaration_specifiers_(declaration_specifiers), declarator_(declarator), compound_statement_(compound_statement){};

    void EmitRISC(std::ostream& stream, Context& context) const override;
    void Print(std::ostream& stream) const override;
};

} // namespace AST
