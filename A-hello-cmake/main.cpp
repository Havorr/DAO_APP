#include <iostream>
#include "helper.h"

int main(int argc, char *argv[])
{
    std::cout << "Hello CMake!" << std::endl;
    std::cout << "2 + 3 = " << add(2, 3) << std::endl;

    int* p = new int[1];
    delete[] p;
    p[0] = 1; // USE_AFTER_FREE (Coverity to wykryje)

    return 0;
}
