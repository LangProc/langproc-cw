#include <cli.h>

int parse_command_line_args(int argc, char **argv, std::string &sourcePath, std::string &outputPath)
{
    std::string input = "";

    if ((argc <= 1) || (argv[argc - 1] == NULL) || (argv[argc - 1][0] == '-'))
    {
        std::cerr << "No command line arguments were provided" << std::endl;
        return 1;
    }
    else
    {
        input = argv[argc - 1];
    }

    // Prevent opterr messages from being outputted.
    opterr = 0;

    // bin/c_compiler -S [source-file.c] -o [dest-file.s]
    int opt;
    while ((opt = getopt(argc, argv, "S:o:")) != -1)
    {
        switch (opt)
        {
        case 'S':
            sourcePath = std::string(optarg);
            break;
        case 'o':
            outputPath = std::string(optarg);
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
            return 1;
        }
    }

    if (sourcePath.length() == 0)
    {
        std::cerr << "The source path -S argument was not set." << std::endl;
        return 1;
    }

    if (outputPath.length() == 0)
    {
        std::cerr << "The output path -o argument was not set." << std::endl;
        return 1;
    }

    return 0;
}
