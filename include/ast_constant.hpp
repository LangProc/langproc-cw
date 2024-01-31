#ifndef AST_CONSTANT_HPP
#define AST_CONSTANT_HPP

#include "ast_node.hpp"

class IntConstant : public Node
{
private:
    int value_;

public:
    IntConstant(int value) : value_(value) {}

    void EmitRISC(std::ostream &stream, Context &context) const override
    {
        stream << "li a0, " << value_ << std::endl;
    }

    void Print(std::ostream &stream) const override
    {
        stream << value_;
    }
};

#endif
