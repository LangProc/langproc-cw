#pragma once

#include <iostream>
#include <memory>
#include <vector>

#include "ast_context.hpp"

namespace AST {

class Node
{
public:
    virtual ~Node() {}
    virtual void EmitRISC(std::ostream& stream, Context& context) const = 0;
    virtual void Print(std::ostream& stream) const = 0;
};

using NodePtr = std::unique_ptr<const Node>;

// Represents a list of nodes.
class NodeList : public Node
{
private:
    std::vector<NodePtr> nodes_;

public:
    NodeList(Node* first_node) { nodes_.emplace_back(first_node); }

    void PushBack(Node* item);
    virtual void EmitRISC(std::ostream& stream, Context& context) const override;
    virtual void Print(std::ostream& stream) const override;
};

} // namespace AST
