#include "ast_function_definition.hpp"

FunctionDefinition::FunctionDefinition(Node* declaration_specifiers, Node* declarator, Node* compound_statement) {
  branches.insert(branches.end(), {declaration_specifiers, declarator, compound_statement});
}

void FunctionDefinition::emitRISC(std::ostream &stream, Context &context) const {
  // Emit declarator
  branches[1]->emitRISC(stream, context);

  // Emit compound_statement
  branches[2]->emitRISC(stream, context);
}
