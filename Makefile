# Based on https://stackoverflow.com/a/52036564 which is well worth reading!

CXXFLAGS := -std=c++20 # use the 2020 version of the C++ standard
CXXFLAGS += -Wall # enable most warnings
CXXFLAGS += -Wextra # enable extra warnings
CXXFLAGS += -Werror # treat all warnings as errors
CXXFLAGS += -fsanitize=address -fsanitize-recover=address # enable address sanitization
CXXFLAGS += -fsanitize=leak # enable leak sanitization
CXXFLAGS += -fsanitize=undefined # enable undefined behaviour sanitization
CXXFLAGS += -I include # look for header files in the `include` directory
JOBS = $(shell nproc)
ifdef DEBUG
CXXFLAGS += -g # generate debugging information
CXXFLAGS += -O0 # perform minimal optimisations
CXXFLAGS += -rdynamic # to get more helpful traces when debugging
CXXFLAGS += --coverage # enable code coverage
CXXFLAGS += -DDEBUG # enable code behind "ifdef DEBUG"
COVFLAGS = -j $(JOBS) --no-external --exclude "$(PWD)/build/*" --demangle-cpp -d .
else
CXXFLAGS += -O3 # perform optimisations
endif

SOURCES := $(wildcard src/*.cpp) # all .cpp files are to be considered source files
DEPENDENCIES := $(patsubst src/%.cpp,build/%.d,$(SOURCES))

OBJECTS := $(patsubst src/%.cpp,build/%.o,$(SOURCES))
OBJECTS += build/parser.tab.o build/lexer.yy.o

.PHONY: default clean coverage

default: build/c_compiler

build/c_compiler: $(OBJECTS)
	@find . -name "*.gcda" -delete
	@mkdir -p build
	g++ $(CXXFLAGS) -o $@ $^
ifdef DEBUG
	lcov -c -i $(COVFLAGS) -o build/base.info
endif

-include $(DEPENDENCIES)

build/%.o: src/%.cpp Makefile
	@mkdir -p $(@D)
	g++ $(CXXFLAGS) -MMD -MP -c $< -o $@

build/parser.tab.cpp build/parser.tab.hpp &: src/parser.y
	@mkdir -p build
	bison -v -d src/parser.y -o build/parser.tab.cpp

build/lexer.yy.cpp: src/lexer.flex build/parser.tab.hpp
	@mkdir -p build
	flex -o build/lexer.yy.cpp src/lexer.flex

ifdef DEBUG
coverage:
	@rm -rf coverage/
	@mkdir -p coverage
	@lcov -c $(COVFLAGS) -o coverage/runtime.info
	@lcov -a build/base.info -a coverage/runtime.info -o coverage/lcov.info
	@genhtml -j $(JOBS) --flat --ignore-errors unmapped -o coverage coverage/lcov.info
	@find . -name "*.gcda" -delete
endif

clean:
	@rm -rf coverage/
	@rm -rf build/
