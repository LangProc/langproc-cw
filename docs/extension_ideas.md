# Extension ideas

This document collects optional extensions you can implement in **any order once** you’re already passing the provided tests. The goal is to (1) **increase confidence in correctness**, (2) **grow language coverage**, (3) **learn “real compiler” middle-end design + optimisations**, and (4) **improve diagnostics**.

The point of implementing the extensions is not to improve your grade as they have minimal effect on design style and code readability portion of the coursework, where you can achieve maximum marks without any of the below. The idea is simply to provide ambitious students with some topics to read about and try implementing to improve their compiler skills and end up with a more impressive project to put on a CV.

---
## 1) Ensuring correctness with tougher tests

A good start is to add new test cases under `compiler_tests/`. Any new tests you place there will be automatically picked up by the existing testing script.

If you want a large source of additional programs (beyond hand-written tests), two common options are:

- Curated “torture” test suites, e.g. the [GCC c-torture](https://github.com/llvm/llvm-test-suite/tree/main/SingleSource/Regression/C/gcc-c-torture) tests mirrored in the LLVM test-suite


- Random C program generation, e.g. [Csmith](https://github.com/csmith-project/csmith?utm_source=chatgpt.com)
---

## 2) Implement language features beyond the specification

Below are some constructs that extend your compiler toward fuller C90 coverage. The order is *roughly* from easier to harder / more interesting.

### 2.1 `short` and `long` integer types
### 2.2 `goto`
### 2.3 Function pointers
### 2.4 `union`
### 2.5 Implicit and explicit casting
### 2.6 Preprocessor and macros

A full C preprocessor is a project in itself. If you want a sane scope:

* Start with:
  * `#include` of local files
  * `#define/#undef`
  * `#if 0` / `#ifdef` (simple conditionals)

* Later:
  * full expression evaluation in `#if`
  * macro argument expansion rules
  * stringification (`#`) and token pasting (`##`)

A lot of external test suites require a preprocessor, because they don't use preprocessed C. Hence, you could also use an existing C preprocessor (e.g., [TCPP](https://github.com/bnoazx005/tcpp)), crediting accordingly.

---

## 3) Introduce a real IR and implement optimisations

Currently, your compiler most likely goes “AST → assembly” directly, adding a middle-end is one of the most educational upgrades you can make.

Modern compilers like [**LLVM**](llvm.org) use a dedicated intermediate representation (IR). LLVM IR is a typed, SSA-based representation used as a common code format across optimisation and code generation phases.

### 3.1 Reason behind IR

A good IR (even a custom one) makes it easier to:

* build a control-flow graph (CFG)
* run local and global analyses (liveness, dominance, reaching definition, etc.)
* implement optimisations as independent passes
* keep front-end concerns separate from backend instruction emission

A very reasonable IR for a compiler is **three-address code (3AC)** with:

* temporaries (`t1 = t2 + t3`)
* explicit labels / jumps
* basic blocks forming a CFG

SSA is what real IRs use, so you can treat it as an ambitious goal, but it is not strictly necessary for the following optimisations.

### 3.2 Optimisation ideas

It is a good idea to put your custom optimisations behind a flag, e.g. `-O1`, so that they don't interfere with our automated testing.

#### (A) Constant folding

Evaluate constant expressions at compile time.

Before:

```c
int f() { return 2 * 3 + 4; }
```

After:

```c
int f() { return 10; }
```

#### (B) Algebraic simplification

Rewrite equivalent forms to cheaper ones.

* `x + 0 → x`
* `x * 1 → x`
* `x * 0 → 0`
* `x - x → 0`

#### (C) Strength reduction

Replace expensive ops with cheaper ones (where correct).

Example:

* `x * 8 → x << 3`

#### (D) Register allocation

A big, classic step, should be very interesting to implement.

A good progression:

1. **Naive**: spill everything to stack (baseline)
2. **Local allocation**: reuse a small set of registers within a basic block
3. **Linear scan** allocation (often simpler than graph coloring)
4. **Graph coloring** allocation (classic “hard but rewarding”)

Key enabling analysis:

* **liveness analysis** (what values are live-out of each instruction / block)

#### (E) Instruction-level dead code elimination (DCE)

Remove computations whose results are never used.

IR-ish example:

```text
t1 = a + b
t2 = c + d
return t1
```

`t2 = c + d` is dead and can be removed.

#### (F) Copy propagation

Turn:

```text
t1 = x
t2 = t1 + 5
```

into:

```text
t2 = x + 5
```

#### (G) Local common subexpression elimination (CSE)

Within a basic block:

```text
t1 = a + b
t2 = a + b
```

Rewrite to:

```text
t1 = a + b
t2 = t1
```

#### (H) CFG simplification (block/edge cleanup)

* Remove unreachable blocks
* Merge blocks with single predecessor/successor
* Simplify `if (0)` / `while (0)` patterns after constant folding



#### (I) Peephole optimisation

After codegen (regardless of other optimisations), look for small instruction patterns to simplify.

Example:

```asm
mov r1, r1
```

Remove it.

Or:

```asm
add r1, 0
```

Remove it.

#### (J) Loop-invariant code motion (LICM)

Move computations out of loops when they don’t depend on loop iteration.

Before:

```c
for (i=0; i<n; i++) {
  t = a*b;   // invariant
  x[i] = t + i;
}
```

After:

```c
t = a*b;
for (i=0; i<n; i++) {
  x[i] = t + i;
}
```

Requires CFG + dominance-ish reasoning (or a simpler “good enough” heuristic).

#### (K) Loop unrolling (trade-offs: I-cache vs control overhead)

Duplicate the loop body multiple times per iteration to reduce loop control overhead (branches, index updates) and to expose more opportunities for other optimisations (e.g., constant folding, CSE, better register reuse).

Example (unroll by 2); before:
```c
for (i = 0; i < n; i++) {
  sum += a[i];
}
```

After (conceptually):
```c
for (i = 0; i + 1 < n; i += 2) {
  sum += a[i];
  sum += a[i + 1];
}
if (i < n) {           /* cleanup */
  sum += a[i];
}
```

Pros:
- Fewer branch/jump instructions executed (lower loop control overhead)
- Larger basic blocks can enable LICM/CSE/constant propagation and improve instruction scheduling
- Can improve ILP (more independent instructions per iteration)

Cons:
- Instruction cache (I-cache) pressure / code size blow-up: larger code can evict hot code and slow down the whole program
- Potentially more register pressure (more live values at once), which can increase spills and negate benefits
- More complex control flow (cleanup/remainder loops) adds edge cases

Common heuristics:
- Only unroll when the loop body is “small” (few IR instructions)
- Only unroll when trip count is known or likely large enough
- Keep unroll factors low (2 or 4) for a first implementation

---

## 4) Diagnostics and error handling

A compiler that reports errors well is dramatically nicer to use and debug.

### 4.1 Differentiate syntax vs semantic errors

* **Syntax errors**: grammar/token stream issues (parser-level)

  * e.g., missing `;`, unexpected token, mismatched braces
* **Semantic errors**: the program parses, but doesn’t make sense

  * e.g., undeclared identifier, type mismatch, calling something that isn’t a function, invalid lvalue, wrong number of arguments

### 4.2 Source locations (line/column)

If you track positions in the lexer and propagate them into AST nodes, you can print:

* file, line, column
* the source line
* a caret `^` under the offending region

Example format:

```text
error: type mismatch in assignment
  foo.c:12:9
    x = y + 1;
        ^
```

### 4.3 Error recovery (report multiple errors)

Instead of stopping at the first error, you can:

* use yacc error productions to synchronize at “safe” points (`;`, `}`, etc.)
* continue parsing and collect additional diagnostics

This is harder than it sounds, but even limited recovery can be very helpful.

### 4.4 Warnings (optional but valuable)

A few high-value warnings:

* unused local variables
* unreachable code after `return`
* suspicious comparisons (e.g., always true/false due to constants)
* implicit narrowing conversions (once you implement casts/promotions)

