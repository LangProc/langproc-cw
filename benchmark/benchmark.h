#include <inttypes.h>

static inline uint64_t rdinstret64(void) {
    uint32_t hi, lo, hi2;
    asm volatile(
        "1:\n"
        "rdinstreth %0\n"
        "rdinstret  %1\n"
        "rdinstreth %2\n"
        "bne %0, %2, 1b\n"
        : "=&r"(hi), "=&r"(lo), "=&r"(hi2)
    );
    return ((uint64_t)hi << 32) | lo;
}