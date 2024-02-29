#include "ast_node.hpp"

namespace AST {

void NodeList::PushBack(Node* item)
{
    nodes_.emplace_back(item);
}

void NodeList::EmitRISC(std::ostream& stream, Context& context) const
{
    for (const auto& node : nodes_)
    {
        if (node == nullptr)
        {
            continue;
        }
        node->EmitRISC(stream, context);
    }
}

void NodeList::Print(std::ostream& stream) const
{
    for (const auto& node : nodes_)
    {
        if (node == nullptr)
        {
            continue;
        }
        node->Print(stream);
    }
}

}
