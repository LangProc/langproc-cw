#ifndef AST_DIRECT_DECLARATOR
#define AST_DIRECT_DECLARATOR

#include "ast_node.hpp"

class DirectDeclarator : public Node {
public:
  DirectDeclarator(Node* identifier);
  ~DirectDeclarator() {};
  void emitRISC(std::ostream &stream, Context &context) const;
};

#endif
