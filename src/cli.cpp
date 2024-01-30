#include <cli.h>

CommandLineArguments parseCommandLineArgs(int argc, char **argv)
{
    std::string input = "";

    if ((argc <= 1) || (argv[argc - 1] == NULL) || (argv[argc - 1][0] == '-'))
    {
        std::cerr << "No command line arguments were provided" << std::endl; 
        exit(1);
    }
    else
    {
        input = argv[argc - 1];
    }


    // Prevent opterr messages from being outputted.
    opterr = 0;

    // ./bin/c_compiler -S [source-file.c] -o [dest-file.s]
    CommandLineArguments cliArgs;
    int opt;
    while ((opt = getopt(argc, argv, "S:o:")) != -1)
    {
        switch (opt)
        {
        case 'S':
            cliArgs.compileSourcePath = std::string(optarg);
            break;
        case 'o':
            cliArgs.compileOutputPath = std::string(optarg);
            break;
        case '?':
            if (optopt == 'S' || optopt == 'o')
            {
                fprintf(stderr, "Option -%c requires an argument.\n", optopt);
            }
            else if (isprint(optopt))
            {
                fprintf(stderr, "Unknown option `-%c'.\n", optopt);
            }
            else
            {
                fprintf(stderr, "Unknown option character `\\x%x'.\n", optopt);
            }
            fprintf(stderr, "Exiting due to failure to parse CLI args\n");
            exit(2);
        }
    }

    if (cliArgs.compileSourcePath.length() == 0)
    {
        std::cerr << "The source path -S argument was not set." << std::endl;
        exit(2);
    }

    if (cliArgs.compileOutputPath.length() == 0)
    {
        std::cerr << "The output path -o argument was not set." << std::endl;
        exit(2);
    }

    return cliArgs;
}
