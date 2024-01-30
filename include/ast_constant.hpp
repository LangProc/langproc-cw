#ifndef AST_CONSTANT_HPP
#define AST_CONSTANT_HPP

#include "ast_node.hpp"

class IntConstant : public Node
{
private:
    int value;

public:
    IntConstant(int _value) : value(_value) {}

    void emitRISC(std::ostream &stream, Context &ctx) const override
    {
        stream << "li a0, " << value << std::endl;
    }

    void print(std::ostream &stream) const override
    {
        stream << value;
    }
};

#endif
