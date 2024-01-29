CXXFLAGS += -std=c++20 -W -Wall -g -Wno-unused-parameter -Wno-unused-variable -Wno-unused-function -I include

CPPFILES := $(wildcard src/*.cpp)
DEPENDENCIES := $(patsubst %.cpp,%.d,$(CPPFILES))
-include $(DEPENDENCIES)
OBJFILES := $(patsubst %.cpp,%.o,$(CPPFILES))
OBJFILES += src/lexer.yy.o src/parser.tab.o


.PHONY: default clean with_coverage coverage

default: bin/c_compiler

bin/c_compiler : $(OBJFILES)
	@mkdir -p bin
	g++ $(CXXFLAGS) -o $@ $^

%.o: %.cpp Makefile
	g++ $(CXXFLAGS) -MMD -MP -c $< -o $@

src/parser.tab.cpp src/parser.tab.hpp: src/parser.y
	bison -v -d src/parser.y -o src/parser.tab.cpp

src/lexer.yy.cpp : src/lexer.flex src/parser.tab.hpp
	flex -o src/lexer.yy.cpp src/lexer.flex

with_coverage : CXXFLAGS += --coverage
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
	@rm -f src/*.tab.hpp
	@rm -f src/*.tab.cpp
	@rm -f src/*.yy.cpp
	@rm -f src/*.output

