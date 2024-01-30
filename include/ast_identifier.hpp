#ifndef AST_IDENTIFIER_HPP
#define AST_IDENTIFIER_HPP

#include "ast_node.hpp"

class Identifier : public Node
{
private:
    std::string identifier;

public:
    Identifier(std::string _identifier) : identifier(_identifier){};
    ~Identifier(){};
    void emitRISC(std::ostream &stream, Context &context) const;
    void print(std::ostream &stream) const override
    {
        stream << identifier;
    };
};

#endif
