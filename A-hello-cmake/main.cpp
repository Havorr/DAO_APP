#include <iostream>
#include "helper.h"

int main(int argc, char *argv[])
{
    std::cout << "Hello CMake!" << std::endl;
    std::cout << "2 + 3 = " << add(2, 3) << std::endl;

    return 0;
}

int* p = nullptr;
*p = 1;
