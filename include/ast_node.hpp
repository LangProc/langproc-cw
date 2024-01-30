#ifndef AST_NODE_HPP
#define AST_NODE_HPP

#include <iostream>
#include <vector>

#include "ast_context.hpp"

class Node
{
protected:
    std::vector<Node *> branches;

public:
    Node(){};
    virtual ~Node();
    virtual void emitRISC(std::ostream &stream, Context &context) const = 0;
    virtual void print(std::ostream &stream) const = 0;
};

// Represents a list of nodes.
class NodeList : public Node
{
private:
    std::vector<Node *> nodes;

public:
    NodeList(Node *firstNode) : nodes({firstNode}) {}

    ~NodeList()
    {
        for (auto node : nodes)
        {
            delete node;
        }
    }

    inline void push_back(Node *item)
    {
        nodes.push_back(item);
    }

    virtual void emitRISC(std::ostream &stream, Context &context) const override
    {
        for (auto node : nodes)
        {
            if (node == nullptr)
            {
                continue;
            }
            node->emitRISC(stream, context);
        }
    }

    virtual void print(std::ostream &stream) const override
    {
        for (auto node : nodes)
        {
            if (node == nullptr)
            {
                continue;
            }
            node->print(stream);
        }
    }
};

#endif
