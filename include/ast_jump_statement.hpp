#ifndef AST_JUMP_STATEMENT
#define AST_JUMP_STATEMENT

#include "ast_node.hpp"

class JumpStatement : public Node {
public:
  JumpStatement() {};
  ~JumpStatement() {};
  void emitRISC(std::ostream &stream, Context &context) const;
};

#endif
