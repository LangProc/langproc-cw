int f(void);

int g()
{
    return 10;
}

int main()
{
    return !( 10==f() );
}
