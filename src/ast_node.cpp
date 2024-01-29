#include "ast_node.hpp"

Node::~Node()  {
  for (unsigned i = 0; i < branches.size(); i++){
    delete branches[i];
  }
}
