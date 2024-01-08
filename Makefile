CPPFLAGS += -std=c++20 -W -Wall -g -I include

.PHONY: default

default: bin/c_compiler

bin/c_compiler : src/cli.cpp src/compiler.cpp
	@mkdir -p bin
	g++ $(CPPFLAGS) -o bin/c_compiler $^

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
