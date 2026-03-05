#include <string.h>

int ok;

void fakeputs(char *x)
{
    ok=!strcmp(x,"wibble");
}

int g(void);

int main()
{
    ok=0;
    g();
    return !(ok==1);
}
