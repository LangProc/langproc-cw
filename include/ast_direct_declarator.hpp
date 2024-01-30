#ifndef AST_DIRECT_DECLARATOR_HPP
#define AST_DIRECT_DECLARATOR_HPP

#include "ast_node.hpp"

class DirectDeclarator : public Node
{
private:
    Node *identifier;

public:
    DirectDeclarator(Node *_identifier) : identifier(_identifier){};
    ~DirectDeclarator()
    {
        delete identifier;
    };
    void emitRISC(std::ostream &stream, Context &context) const;
    void print(std::ostream &stream) const override;
};

#endif
