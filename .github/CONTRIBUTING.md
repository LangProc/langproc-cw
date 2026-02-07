# Contributing

## Style Guides

For C++ code, try to follow the [Google naming style guide](https://google.github.io/styleguide/cppguide.html#Function_Names) where possible. This will allow for consistency across the code base.

These can be simplified to:

- Class data members should be snake_case_ and end with a underscore (note: this doesn't apply to class members)
    - Using this convention prevents the need to use `this->` when accessing class data members since it is obvious from the trailing underscore
- Function names should be PascalCase
- Variable names should be snake_case
- Parameter name should be snake_case
