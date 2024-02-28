# Based on https://stackoverflow.com/a/52036564 which is well worth reading!

CXXFLAGS += -std=c++20 -W -Wall -g -Wno-unused-parameter -Wno-unused-variable -Wno-unused-function -fsanitize=address -static-libasan -O0 -rdynamic --coverage -I include

SOURCES := $(wildcard src/*.cpp)
DEPENDENCIES := $(patsubst src/%.cpp,build/%.d,$(SOURCES))

OBJECTS := $(patsubst src/%.cpp,build/%.o,$(SOURCES))
OBJECTS += build/parser.tab.o build/lexer.yy.o

.PHONY: default clean coverage

default: bin/c_compiler

bin/c_compiler: $(OBJECTS)
	@mkdir -p bin
	g++ $(CXXFLAGS) -o $@ $^

-include $(DEPENDENCIES)

build/%.o: src/%.cpp Makefile
	@mkdir -p $(@D)
	g++ $(CXXFLAGS) -MMD -MP -c $< -o $@

build/parser.tab.cpp build/parser.tab.hpp: src/parser.y
	@mkdir -p build
	bison -v -d src/parser.y -o build/parser.tab.cpp

build/lexer.yy.cpp: src/lexer.flex build/parser.tab.hpp
	@mkdir -p build
	flex -o build/lexer.yy.cpp src/lexer.flex

coverage:
	@rm -rf coverage/
	@mkdir -p coverage
	lcov -c --no-external --exclude "`pwd`/src/lexer.*" --exclude "`pwd`/src/parser.*" --exclude "`pwd`/build/*" -d . -o coverage/cov.info
	genhtml coverage/cov.info -o coverage
	@find . -name "*.gcda" -delete

clean :
	@rm -rf coverage/
	@rm -rf build/
	@rm -rf bin/
