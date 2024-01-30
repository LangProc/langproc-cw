#include "ast_direct_declarator.hpp"

DirectDeclarator::DirectDeclarator(Node* identifier) {
  branches.insert(branches.end(), {identifier});
}

void DirectDeclarator::emitRISC(std::ostream &stream, Context &context) const {
  // Emit identifier
  branches[0]->emitRISC(stream, context);
  stream << ":" << std::endl;
}

void DirectDeclarator::print(std::ostream &stream) const {
    branches[0]->print(stream);
}
