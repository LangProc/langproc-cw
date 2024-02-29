#pragma once

#include <string_view>
#include <stdexcept>

namespace AST {

enum class TypeSpecifier
{
    INT
};

constexpr std::string_view ToString(TypeSpecifier type)
{
    switch (type)
    {
    case TypeSpecifier::INT:
        return "int";
    }
    throw std::runtime_error("Unexpected type specifier");
}

}
