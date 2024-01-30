#ifndef AST_STATEMENTS_HPP
#define AST_STATEMENTS_HPP

#include "ast_node.hpp"

class ReturnStatement : public Node
{
private:
  Node *expression;

public:
  ReturnStatement(Node *_expression) { expression = _expression; };
  ~ReturnStatement() { delete expression; };
  void emitRISC(std::ostream &stream, Context &context) const override;
  void print(std::ostream &stream) const override;
};

#endif
