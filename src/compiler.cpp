#include<iostream>

int main()
{
	std::cout << ".globl f"                   << std::endl;
	std::cout << ".text"                      << std::endl;
	std::cout << "f:"                         << std::endl;
	std::cout << "        addi    sp,sp,-32"  << std::endl;
	std::cout << "        sw      s0,28(sp)"  << std::endl;
	std::cout << "        addi    s0,sp,32"   << std::endl;
	std::cout << "        sw      a0,-20(s0)" << std::endl;
	std::cout << "        sw      a1,-24(s0)" << std::endl;
	std::cout << "        lw      a4,-20(s0)" << std::endl;
	std::cout << "        lw      a5,-24(s0)" << std::endl;
	std::cout << "        add     a5,a4,a5"   << std::endl;
	std::cout << "        mv      a0,a5"      << std::endl;
	std::cout << "        lw      s0,28(sp)"  << std::endl;
	std::cout << "        addi    sp,sp,32"   << std::endl;
	std::cout << "        jr      ra"         << std::endl;
}
