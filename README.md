2021/2022 Compilers Coursework
==============================

There is a single assessed code deliverable, which is due on Friday 24 March 2022 at 23:59. This deliverable contains two components:

- [*C-compiler*](c_compiler.md) (90%): a compiler from C to RISC-V assembly. The source language is pre-processed C90. The target environment is Ubuntu 22.04, so the lab Ubuntu distribution, or equivalently an Ubuntu 22.04 VM as configured in the attached [Dockerfile](Dockerfile).

- [time-tracking/project management component](management.md) (10%), which will be assessed orally at the start of Summer term.

Repositories
============

Each group gets a bare private repository. It is up to you if you want to clone the master specification, or to start from scratch.

Submission
==========

Submission will be via GitHub (code) and Teams (commit hash), as in the labs.

All submissions will be tested functionally -- there is no expectation for your compiler to *optimise* its input. Moreover, your compiler will only be tested on *valid* inputs, so you do not need to handle faulty inputs in a graceful way.

Changelog
=========

* New for 2022/2023:

    * Target architecture is now RISC-V rather than MIPS, in order to align with the modernised Instruction Architectures half of the module.

* New for 2021/2022:

    * Various improvements to scripts for running test cases. (Thanks to Yann Herklotz for this.)

* New for 2020/2021:

    * In previous years, students were additionally required to submit a C-to-Python translator, as a "ramping up" task. This extra deliverable has been removed, as the labs provide plenty of "ramping up" practice.

    * We have provided a really basic compiler that simply ignores its input and produces a fixed, valid MIPS assembly program. This should help you to get started a bit more rapidly. (Thanks to Archie Crichton for writing this.)

* New for 2019/2020:

    * In previous years, students were additionally required to submit a set of testcases. This deliverable has been removed; instead, a large collection of testcases has been provided for you, as this was judged to be more useful.

    * In previous years, the compiler component counted for 42.8% of the module; it now counts for 55%. It was felt that this weighting more accurately reflects the effort that students put in to building a working compiler.
