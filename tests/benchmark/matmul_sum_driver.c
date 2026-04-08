/* DISCLAIMER: Benchmark tests are NOT part of the assessed tests */

#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include "benchmark.h"

float matmul_sum(float A[5][5], float B[5][5]);

int main(void)
{
    float A[5][5] = {
        {1.0f, 2.0f, 3.0f, 4.0f, 5.0f},
        {0.0f, 1.0f, 0.0f, 1.0f, 0.0f},
        {2.0f, 0.0f, 1.0f, 0.0f, 2.0f},
        {3.0f, 1.0f, 4.0f, 1.0f, 5.0f},
        {1.0f, 0.0f, 0.0f, 0.0f, 1.0f}
    };

    float B[5][5] = {
        {1.0f, 0.0f, 2.0f, 0.0f, 1.0f},
        {0.0f, 1.0f, 0.0f, 1.0f, 0.0f},
        {1.0f, 1.0f, 1.0f, 1.0f, 1.0f},
        {2.0f, 0.0f, 0.0f, 0.0f, 2.0f},
        {0.0f, 2.0f, 1.0f, 2.0f, 0.0f}
    };

    uint64_t i0 = rdinstret64();
    float result = matmul_sum(A, B);
    uint64_t i1 = rdinstret64();

    printf("%" PRIu64 "\n", i1 - i0);

    return !(result > 164.999f && result < 165.001f);
}
