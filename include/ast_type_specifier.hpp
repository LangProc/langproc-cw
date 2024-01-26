#ifndef AST_TYPE_SPECIFIER
#define AST_TYPE_SPECIFIER

#include "ast_node.hpp"

class TypeSpecifier : public Node {
private:
  std::string type;
public:
  TypeSpecifier(std::string _type) : type(_type) {};
  ~TypeSpecifier() {};
  void emitRISC(std::ostream &stream, Context context) const {};
};

#endif
