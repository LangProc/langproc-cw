# CMake allows faster rebuilds and generates compile_commands.json
# which is required by clangd for code navigation and refactoring.
# Basic workflow: https://stackoverflow.com/questions/7859623/how-do-i-use-cmake
# To use this with the Python script, add the flag --use_cmake

cmake_minimum_required(VERSION 3.20)

set(CMAKE_C_COMPILER "clang")
set(CMAKE_CXX_COMPILER "clang++")

# [!] Change to your project name
project(langproc-cw
    LANGUAGES C CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    set(CMAKE_C_COMPILER_LAUNCHER "${CCACHE_PROGRAM}")
    set(CMAKE_CXX_COMPILER_LAUNCHER "${CCACHE_PROGRAM}")
endif()

#===--------------------------- Program ----------------------------------===//

find_package(BISON 3.0 REQUIRED)
find_package(FLEX REQUIRED)
BISON_TARGET(Parser src/parser.y
    ${CMAKE_CURRENT_BINARY_DIR}/parser.tab.cpp
    COMPILE_FLAGS "-v"
)
FLEX_TARGET(Lexer src/lexer.flex
    ${CMAKE_CURRENT_BINARY_DIR}/lexer.yy.cpp
)

file(GLOB_RECURSE SRC_FILES src/*.cpp src/*.c)

add_executable(
    c_compiler
    ${SRC_FILES}
    ${BISON_Parser_OUTPUTS}
    ${FLEX_Lexer_OUTPUTS}
)

target_include_directories(
    c_compiler PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
