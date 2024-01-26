#ifndef AST_IDENTIFIER
#define AST_IDENTIFIER

#include "ast_node.hpp"

class Identifier : public Node {
private:
  std::string* identifier;
public:
  Identifier(std::string* _identifier) : identifier(_identifier) {};
  ~Identifier() {delete identifier;};
  void emitRISC(std::ostream &stream, Context context) const;
};

#endif
