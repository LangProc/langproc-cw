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

    float result = 0.0f;
    int repetitions = 100000;

    for (int i = 0; i < repetitions; i++){
        result += matmul_sum(A, B);
    }

    return !(result > (164.999f * repetitions) && result < (165.001f * repetitions));
}
