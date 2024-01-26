#include "ast_jump_statement.hpp"

void JumpStatement::emitRISC(std::ostream &stream, Context context) const {
  // TODO these lines are hardcoded for the example test to pass, you have to correct them
  stream << "addi  t0, zero, 0"  << std::endl;
  stream << "addi  t0, t0,   5"  << std::endl;
  stream << "add   a0, zero, t0" << std::endl;
  stream << "ret"                << std::endl;
  //-------------------------------------------------------------------------------------
}
