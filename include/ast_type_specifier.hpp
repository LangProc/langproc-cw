#pragma once

#include <stdexcept>
#include <string_view>

namespace ast {

enum class TypeSpecifier { INT };

template <typename LogStream>
LogStream& operator<<(LogStream& ls, const TypeSpecifier& type) {
  const auto TypeToString = [&type] {
    switch (type) {
      case TypeSpecifier::INT:
        return "int";
    }
    throw std::runtime_error("Unexpected type specifier");
  };
  return ls << TypeToString();
}

}  // namespace ast
