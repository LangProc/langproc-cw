2022/2023 Compilers Coursework
==============================

There are two components to the coursework:

- [*A C compiler*](c_compiler.md), worth 90%. The source language is pre-processed C90, and the target language is RISC-V assembly. The target environment is Ubuntu 22.04, as described in the attached [Dockerfile](Dockerfile). See [here](./c_compiler.md) for the full set of requirements and more information about the testing environment.

- [*Evidence of time-tracking/project management*](management.md), worth 10%. This will be assessed orally at the start of Summer term. See [here](management.md) for more information about this component.

Repositories
============

Each group gets a bare private repository. It is up to you if you want to clone the main specification, or to start from scratch.

Submission
==========

The deadline for submitting your C compiler is **Friday 24 March 2023 at 23:59**. There is no deadline for the project management component; instead, this will be assessed by a short oral viva that will be organised in Summer term.

Submission will be via GitHub (code) and Teams (commit hash), as in the labs.

All submissions will be tested functionally -- there is no expectation for your compiler to *optimise* its input. Moreover, your compiler will only be tested on *valid* inputs, so you do not need to handle faulty inputs in a graceful way.

Changelog
=========

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

    * We have provided a really basic compiler that simply ignores its input and produces a fixed, valid MIPS assembly program. This should help you to get started a bit more rapidly.

* New for 2019/2020:

    * In previous years, students were additionally required to submit a set of testcases. This deliverable has been removed; instead, a large collection of testcases has been provided for you, as this was judged to be more useful.

    * In previous years, the compiler component counted for 42.8% of the module; it now counts for 55%. It was felt that this weighting more accurately reflects the effort that students put in to building a working compiler.

Acknowledgements
================

* The coursework was originally designed by [David Thomas](https://www.southampton.ac.uk/people/5z9bmb/professor-david-thomas), who lectured this module until 2017-18. It is nowadays maintained by [John Wickerson](https://johnwickerson.github.io/), to whom any feedback should be sent.
* Thanks to [Yann Herklotz](https://yannherklotz.com/) for making various improvements to the compiler-testing scripts.
* Thanks to [Archie Crichton](https://www.doc.ic.ac.uk/~ac11018/) for providing a basic "getting started" compiler.
* Extra-special thanks to [James Nock](https://www.linkedin.com/in/jpnock) for overhauling the scripts for configuring the development environment, for writing detailed instructions for setting this up on various operating systems, and for creating GitHub actions capable of automatically testing compilers.
