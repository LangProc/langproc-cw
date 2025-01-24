#include "ast_type_specifier.hpp"

#include <stdexcept>

namespace ast
{

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
