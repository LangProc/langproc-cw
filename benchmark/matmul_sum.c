float matmul_sum(float A[5][5], float B[5][5])
{
    int i, j, k;
    float sum;
    float cij;

    sum = 0.0f;

    for (i = 0; i < 5; i++) {
        for (j = 0; j < 5; j++) {
            cij = 0.0f;
            for (k = 0; k < 5; k++) {
                cij += A[i][k] * B[k][j];
            }
            sum += cij;
        }
    }

    return sum;
}