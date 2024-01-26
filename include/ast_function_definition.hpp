#ifndef AST_FUNCTION_DEFINITION_HPP
#define AST_FUNCTION_DEFINITION_HPP

#include "ast_node.hpp"

class FunctionDefinition : public Node {
public:
  FunctionDefinition(Node* declaration_specifiers, Node* declarator, Node* compound_statement);
  ~FunctionDefinition() {};
  void emitRISC(std::ostream &stream, Context context) const;
};

#endif
