# Based on https://stackoverflow.com/a/52036564 which is well worth reading!

CXXFLAGS := -std=c++20 # use the 2020 version of the C++ standard
CXXFLAGS += -Wall # enable most warnings
CXXFLAGS += -Wextra # enable extra warnings
CXXFLAGS += -Werror # treat all warnings as errors
CXXFLAGS += -I include # look for header files in the `include` directory
ifdef NDEBUG
CXXFLAGS += -O3 # perform optimisations
CXXFLAGS += -DNDEBUG # disable code behind "ifndef NDEBUG" like in C's `assert`
else
CXXFLAGS += -fsanitize=address -fsanitize-recover=address # enable address sanitization
CXXFLAGS += -fsanitize=leak # enable leak sanitization
CXXFLAGS += -fsanitize=undefined # enable undefined behaviour sanitization
CXXFLAGS += -g # generate debugging information
CXXFLAGS += -O0 # perform minimal optimisations
CXXFLAGS += -rdynamic # to get more helpful traces when debugging
CXXFLAGS += --coverage # enable code coverage
# Get value of -j (no matter how it is provided, including --jobs=X) https://stackoverflow.com/a/76517886
JOBS = $(patsubst -j%,%,$(filter -j%,$(MAKEFLAGS)))
COVFLAGS := -j $(JOBS) # parallel
# Exclude external files like stdlib, exclude lexer and parser generated files
COVFLAGS += --no-external --exclude "$(CURDIR)/build/*"
COVGLAGS += --demangle-cpp # print nice C++ function names
COVGLAGS += -d . # coverage data for current program (not kernel which is default...)
endif

SOURCES := $(wildcard src/*.cpp) # all .cpp files are to be considered source files
DEPENDENCIES := $(patsubst src/%.cpp,build/%.d,$(SOURCES))

OBJECTS := $(patsubst src/%.cpp,build/%.o,$(SOURCES))
OBJECTS += build/parser.tab.o build/lexer.yy.o

.PHONY: default clean coverage

default: build/c_compiler

build/c_compiler: $(OBJECTS)
# Remove leftover runtime coverage data left from previous runs
	@find . -name "*.gcda" -delete
	@mkdir -p build
	ccache g++ $(CXXFLAGS) -o $@ $^
ifndef NDEBUG
# Initialise counters + use static data provided by compiler
	lcov -c -i $(COVFLAGS) -o build/base.info
endif

-include $(DEPENDENCIES)

build/%.o: src/%.cpp Makefile
	@mkdir -p $(@D)
	ccache g++ $(CXXFLAGS) -MMD -MP -c $< -o $@

build/parser.tab.cpp build/parser.tab.hpp &: src/parser.y
	@mkdir -p build
	bison -v -d src/parser.y -o build/parser.tab.cpp

build/lexer.yy.cpp: src/lexer.flex build/parser.tab.hpp
	@mkdir -p build
	flex -o build/lexer.yy.cpp src/lexer.flex

ifndef NDEBUG
coverage:
	@rm -rf coverage/
	@mkdir -p coverage
# Gather runtime coverage data
	lcov -c $(COVFLAGS) -o coverage/runtime.info
# Merge with static data
	@lcov -a build/base.info -a coverage/runtime.info -o coverage/lcov.info
# Generate webpage without folders (include, src) because students put code in headers + ignore mising data
	genhtml -j $(JOBS) --flat --ignore-errors unmapped -o coverage coverage/lcov.info
# Remove runtime coverage data to get fresh coverage from future runs without recompiling
	@find . -name "*.gcda" -delete
	@rm coverage/runtime.info
endif

clean:
	@rm -rf coverage/
	@rm -rf build/
