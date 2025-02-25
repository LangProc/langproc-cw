2024/25 Compilers Coursework
==============================

There are two components to the coursework:

- Worth 90%:
    - **A C compiler**. The source language is pre-processed C90, and the target language is RISC-V assembly. The target environment is Ubuntu 22.04, as described [here](docs/environment_guide.md). See [here](docs/c_compiler.md) for the full set of requirements and more information about the testing environment.

- Worth 10%:
    - **Overall design style and code readability.** This has been introduced to reward thoughtful planning throughout the project, rather than penalise you. There are no strict guidelines, but you should consider the use of abstraction, your internal representation of instructions, proper Git use, signs of appropriate testing, as well as general code hygiene.
    - **Evidence of time-tracking/project management.** This will be assessed orally at the start of Summer term. See [here](docs/management.md) for more information about this component.

Repositories
============

Each group gets a bare private repository. It is up to you if you want to clone the main specification, or to start from scratch.

Submission
==========

The deadline for submitting your C compiler is **Friday 21 March 2025 at 15:00**. There is no deadline for the project management component; instead, this will be assessed by a short oral viva that will be organised in Summer term.

Submission will be via GitHub (code) and Teams (commit hash), as in the labs.

All submissions will be tested functionally -- there is no expectation for your compiler to *optimise* its input. Moreover, your compiler will only be tested on *valid* inputs, so you do not need to handle faulty inputs in a graceful way.

Changelog
=========

* New for 2023/2024:

    * Provided guidance to generate coverage information.
    * Expanded features list and provided a visual test case distribution.
    * Included useful links to Godbolt, simulator, ISA, ABI, Assembler reference.
    * Directly linked to ANSI C parser and lexer.
    * Added a "Getting started" guide and incorporated last year's feedback from Ed.
    * Changed the 10% of the grade (previously only for time management) to also account for code design to reward thoughtful planning.
    * Improved the skeleton compiler to be more advanced by integrating lexer and parser to hopefully jump-start progress and avoid unnecessary debugging.
    * Covered assembler directives in more details by showcasing the meaning behind an example assembly program, because that topic had always caused confusion in the past years.
    * Added an improved testing script written in Python.

* New for 2022/2023:

    * Target architecture is now RISC-V rather than MIPS, in order to align with the modernised Instruction Architectures half of the module.
    * Instead of Vagrant, Docker is now used for the testing environment (with optional VS Code support).
    * Test scripts are now provided to check your compiler against the set of public tests, without having to write this yourself.
    * The basic compiler framework has been improved to support command line arguments.
    * GitHub Actions can now perform automated testing of your compiler.

* New for 2021/2022:

    * Various improvements to scripts for running test cases.

* New for 2020/2021:

    * In previous years, students were additionally required to submit a C-to-Python translator, as a "ramping up" task. This extra deliverable has been removed, as the labs provide plenty of "ramping up" practice.

    * We have provided a really basic compiler that simply ignores its input and produces a fixed, valid RISC-V assembly program. This should help you to get started a bit more rapidly.

* New for 2019/2020:

    * In previous years, students were additionally required to submit a set of testcases. This deliverable has been removed; instead, a large collection of testcases has been provided for you, as this was judged to be more useful.

    * In previous years, the compiler component counted for 42.8% of the module; it now counts for 55%. It was felt that this weighting more accurately reflects the effort that students put in to building a working compiler.

Acknowledgements
================

The coursework was originally designed by [David Thomas](https://www.southampton.ac.uk/people/5z9bmb/professor-david-thomas), who lectured this module until 2017-18. It is nowadays maintained by [John Wickerson](https://johnwickerson.github.io/), to whom any feedback should be sent. I'd like to thank Quentin Corradi, Archie Crichton, Yann Herklotz, William Huynh, James Nock, Simon Staal, and Filip Wojcicki for making many contributions to this repository over several years, such as improving the compiler-testing scripts, providing a basic "getting started" compiler, writing instructions for setting up development environments on a variety of operating systems, configuring automation using GitHub actions, and setting up coverage testing.
