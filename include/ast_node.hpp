#ifndef AST_NODE_HPP
#define AST_NODE_HPP

#include <iostream>
#include <vector>

#include "ast_context.hpp"

class Node {
protected:
  std::vector<Node*> branches;

public:
  Node() {};
  virtual ~Node();
  virtual void emitRISC(std::ostream &stream, Context &context) const = 0;
};

#endif
