# Extension ideas

This document collects optional extensions you can implement in **any order once** you’re already passing the provided tests. The goal is to (1) **increase confidence in correctness**, (2) **grow language coverage**, (3) **learn “real compiler” middle-end design + optimisations**, and (4) **improve diagnostics**.

The point of implementing the extensions is not to improve your grade as they have minimal effect on design style and code readability portion of the coursework, where you can achieve maximum marks without any of the below. The idea is simply to provide ambitious students with some topics to read about and try implementing to improve their compiler skills and end up with a more impressive project to put on a CV.

---
---

## 1) Ensuring correctness with tougher tests

A good start is to add new test cases under `compiler_tests/`. Any new tests you place there will be automatically picked up by the existing testing script.

If you want a large source of additional programs (beyond hand-written tests), two common options are:

- Curated “torture” test suites, e.g. the [GCC c-torture](https://github.com/llvm/llvm-test-suite/tree/main/SingleSource/Regression/C/gcc-c-torture) tests mirrored in the LLVM test-suite


- Random C program generation, e.g. [Csmith](https://github.com/csmith-project/csmith)

---
---

## 2) Implement language features beyond the specification

Below are some constructs that extend your compiler toward fuller C90 coverage. The order is *roughly* from easier to harder / more interesting.

### `short` and `long` integer types

By implementing these, you should now support all [C90 arithmetic types](https://en.cppreference.com/w/c/language/arithmetic_types.html):
- `char` / `unsigned char` / `signed char`
- `short` / `unsigned short`
- `int` / `unsigned int`
- `long` / `unsigned long`
- `float`
- `double`

### `union`

`union` share most functionality with `struct`, so you should abstract these similarities.

### Explicit and implicit casting

You should start with explicit casting on the integer types, as it is simpler and can help with implicit casting.

### Variable length arrays (VLA)

Stack allocated VLAs like:

```c
float values[n];
```

### `goto`

`goto` interferes with scopes and register allocation; especially [variable length arrays](https://en.cppreference.com/w/c/language/goto.html).
* You should start with implementing `goto` jumping to the same scope without jumping over variable declarations.
* Then `goto` jumping into outer scopes (still without jumping over variable declarations).
* Then `goto` jumping over variable declarations; except for variable length arrays as it is simply not correct.
* And finally generalised `goto`.

### Function pointers

Function pointers require very careful type handling.

### Preprocessor and macros

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
---

## 3) Optimisations and Intermediate Representation (IR)

It is a good idea to put your custom optimisations behind a flag, e.g. `-O1`, so that they don't interfere with our automated testing.

### Peephole optimisations

[Peephole optimisations](https://en.wikipedia.org/wiki/Peephole_optimization) happen after codegen, before emitting assembly. They do not depend on any IR analysis, so they are a good option if you are not planning on implementing any custom IR. The goal is to check across small windows of instruction to find patterns to simplify with equivalent logic.

Examples to remove:

```asm
mov r1, r1
```

or:

```asm
add r1, 0
```

Examples of substitutions:

```asm
li r1, 4
mul r2, r2, r1
```

becomes:

```asm
slli r2, r2, 2
```

The [ISA `C` extension](https://docs.riscv.org/reference/isa/unpriv/c-st-ext.html) is a possible source of instructions for peephole optimisation.

---

### Simple optimisations

These optimisations are simple enough that you could do them without introducing an IR. However, they do benefit from even a simple IR, so consider that if you think you have enough time to work on IR first.

#### Constant folding

Evaluate constant expressions at compile time.

Before:

```c
int f() { return 2 * 3 + 4; }
```

After:

```c
int f() { return 10; }
```

#### Algebraic simplification

Rewrite equivalent forms to cheaper ones.

* `x + 0 → x`
* `x * 1 → x`
* `x * 0 → 0`
* `x - x → 0`

#### Strength reduction

Replace expensive ops with cheaper ones (where correct).

Example:

* `x * 8 → x << 3`

---

### Introducing an Intermediate Representation (IR)

Your compiler most likely goes “AST → assembly” directly and adding a middle-end is one of the most educational upgrades you can make.

Modern compilers like [**LLVM**](llvm.org) use a dedicated intermediate representation. LLVM IR is a typed, [SSA-based](https://en.wikipedia.org/wiki/Static_single-assignment_form) representation used as a common code format across optimisation and code generation phases. However, you can perform a lot of optimisations even with a simple custom IR.

#### Reason behind IR

A good IR (even a custom one) makes it easier to:

* build a control-flow graph (CFG)
* run local and global analyses (liveness, dominance, reaching definition, etc.)
* implement optimisations as independent passes
* keep front-end concerns separate from backend instruction emission

#### Your custom IR

A very reasonable IR for a compiler is [**three-address code (3AC)**](https://en.wikipedia.org/wiki/Three-address_code) with:

* 3 operands, assignment and operator (`t1 := t2 + t3`)
* data as sized integers and floats
* explicit labels / jumps
* function calls
* basic blocks forming a CFG

SSA is what real IRs use, so you can treat it as an ambitious goal, but it is not strictly necessary for the following optimisations.

---

### Advanced (IR-dependent) optimisations

#### Register allocation

A big, classic step, should be very interesting to implement.

A good progression:

1. **Naive**: spill everything to stack (baseline)
2. **Local allocation**: reuse a small set of registers within a basic block
3. **Linear scan** allocation (often simpler than graph coloring)
4. **Graph coloring** allocation (classic “hard but rewarding”)

Key enabling analysis:

* **liveness analysis** (what values are live-out of each instruction / block)

#### Loop unrolling

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

#### Tail-call optimisation (TCO)

A [*tail call*](https://en.wikipedia.org/wiki/Tail_call) is a function call that happens as the final action of a function, e.g. `return f(x);`.
In this case, the current stack frame is no longer needed after the call. **Tail-call optimisation** replaces the *call*+*return* sequence with a *jump* (or an equivalent “tail call”) that *reuses the current stack frame*, preventing stack growth in tail-recursive code.

Example (tail recursion):

```c
int fact_tr(int n, int acc) {
  if (n <= 1) return acc;
  return fact_tr(n - 1, n * acc);   /* tail call */
}
```

With TCO, `fact_tr` can run in constant stack space (similar to a loop), even for large `n`.

#### Instruction-level dead code elimination (DCE)

Remove computations whose results are never used. Beware of side-effects which cannot be removed: `*x = 0` may be dead code, but in many cases removing it is invalid.

IR-ish example:

```text
t1 = a + b
t2 = c + d
return t1
```

`t2 = c + d` is dead and can be removed.

#### Copy propagation

Turn:

```text
t1 = x
t2 = t1 + 5
```

into:

```text
t2 = x + 5
```

#### Local common subexpression elimination (CSE)

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

#### CFG simplification (block/edge cleanup)

* Remove unreachable blocks
* Merge blocks with single predecessor/successor

#### Loop-invariant code motion (LICM)

Move computations out of loops when they don’t depend on loop iteration. Again, beware of side-effects which cannot be removed: `*x = 0` may be loop-invariant, but in many cases removing it is invalid.

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

---
---

## 4) Type checking, diagnostics and error handling

A compiler that reports errors well is dramatically nicer to use and debug.

### Differentiate syntax vs semantic errors

* **Syntax errors**: grammar/token stream issues (parser-level)

  * e.g., missing `;`, unexpected token, mismatched braces
* **Semantic errors**: the program parses, but doesn’t make sense

  * e.g., undeclared identifier, type mismatch, calling something that isn’t a function, invalid lvalue, wrong number of arguments

### Source locations (line/column)
  
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

When C code is produced by a preprocessor or another tool (flex/yacc), the resulting file may include `#line` directives (or equivalent line markers). These tell the compiler to report diagnostics as if the code came from a different **source file / line number** than the physical location in the generated output. This is important for user experience: errors should point to the original `.c` rather than the generated file.


### Error recovery (report multiple errors)

Instead of stopping at the first error, you can:

* use yacc error productions to synchronize at “safe” points (`;`, `}`, etc.)
* continue parsing and collect additional diagnostics

This is harder than it sounds, but even limited recovery can be very helpful.

### Warnings

A few high-value warnings:

* unused local variables
* unreachable code after `return`
* suspicious comparisons (e.g., always true/false due to constants)
* implicit narrowing conversions (once you implement casts/promotions)
* array out of bound access
* suspicious casts (`void*`, pointer size change, function pointer casts, pointer level change [`int**` → `int*`], pointer/array casts, complex data type casts betwen `union`/`struct`/`enum`, `int` → `enum`, `float` →`int`).
* suspicious mix of operations (pointer and arithmetics, pointer as array index, indexing non array pointer, dereferencing function pointer, calling data pointer).

