#ifndef AST_FUNCTION_DEFINITION_HPP
#define AST_FUNCTION_DEFINITION_HPP

#include "ast_node.hpp"

class FunctionDefinition : public Node
{
private:
    Node *declarationSpecifiers;
    Node *declarator;
    Node *compoundStatement;

public:
    FunctionDefinition(Node *_declarationSpecifiers, Node *_declarator, Node *_compoundStatement) : declarationSpecifiers(_declarationSpecifiers), declarator(_declarator), compoundStatement(_compoundStatement){};
    ~FunctionDefinition()
    {
        delete declarationSpecifiers;
        delete declarator;
        delete compoundStatement;
    };
    void emitRISC(std::ostream &stream, Context &context) const;
    void print(std::ostream &stream) const override;
};

#endif
