#include <cli.h>

CommandLineArguments ParseCommandLineArgs(int argc, char **argv)
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
    CommandLineArguments cli_args;
    int opt;
    while ((opt = getopt(argc, argv, "S:o:")) != -1)
    {
        switch (opt)
        {
        case 'S':
            cli_args.compile_source_path = std::string(optarg);
            break;
        case 'o':
            cli_args.compile_output_path = std::string(optarg);
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

    if (cli_args.compile_source_path.length() == 0)
    {
        std::cerr << "The source path -S argument was not set." << std::endl;
        exit(2);
    }

    if (cli_args.compile_output_path.length() == 0)
    {
        std::cerr << "The output path -o argument was not set." << std::endl;
        exit(2);
    }

    return cli_args;
}
