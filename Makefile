CPPFLAGS += -std=c++20 -W -Wall -g -Wno-unused-parameter -Wno-unused-variable -Wno-unused-function -I include

.PHONY: default clean with_coverage coverage

default: bin/c_compiler

bin/c_compiler : src/lexer.yy.o src/parser.tab.o src/cli.o src/compiler.o
	@mkdir -p bin
	g++ $(CPPFLAGS) -o bin/c_compiler $^

src/parser.tab.cpp src/parser.tab.hpp: src/parser.y
	yacc -v -d src/parser.y -o src/parser.tab.cpp

src/lexer.yy.cpp : src/lexer.flex src/parser.tab.hpp
	flex -o src/lexer.yy.cpp src/lexer.flex

with_coverage : CPPFLAGS += --coverage
with_coverage : bin/c_compiler

coverage : coverage/index.html

coverage/index.html :
	@mkdir -p coverage
# somehow lexer and parser coverage info are available but not accurate. To exclude them use:
# lcov -c --no-external --exclude "`pwd`/src/lexer.*" --exclude "`pwd`/src/parser.*" -d . -o coverage/cov.info
	lcov -c --no-external -d . -o coverage/cov.info
	genhtml coverage/cov.info -o coverage
	@find . -name "*.gcda" -delete

clean :
	@rm -rf coverage
	@find . -name "*.o" -delete
	@rm -rf bin/*
