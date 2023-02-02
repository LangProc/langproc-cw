#include <algorithm>
#include <iostream>
#include <vector>

const char *ARRAY_OF_NUMBERS[] = { "1", "2" , "99" };

static int process_arguments(int argc, const char *argv[])
{
  std::vector<int> numbers(argc - 1);
  for (int i = 1 ; i < argc ; i++) {
    numbers[i - 1] = atoi(argv[i]);
  }
  std::sort(numbers.begin(), numbers.end());
  return *(numbers.end() - 1);
}


int main(int argc, const char * argv[])
{
  std::cout << "Res 1: " << process_arguments(3, ARRAY_OF_NUMBERS) << std::endl;
  std::cout << "Res 2: " << process_arguments(argc, argv) << std::endl;
  return 0;
}
