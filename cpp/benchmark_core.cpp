#include "bms_core.h"

#include <array>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>

int main(int argc, char** argv) {
    const int iterations = argc == 2 ? std::atoi(argv[1]) : 100000;
    if (iterations < 1 || iterations > 10000000) {
        std::cerr << "iterations must be between 1 and 10000000\n";
        return 2;
    }
    std::array<double, 256> samples{};
    for (std::size_t step = 0; step < 32; ++step) {
        for (std::size_t cell = 0; cell < 8; ++cell) {
            samples[step * 8 + cell] = 3.7 + static_cast<double>(cell) * 0.001 +
                                       static_cast<double>(step) * 0.0001;
        }
    }
    double score = 0.0;
    std::size_t worst = 0;
    const auto started = std::chrono::steady_clock::now();
    for (int iteration = 0; iteration < iterations; ++iteration) {
        if (bms_v1_anomaly_score(samples.data(), 32, 8, &score, &worst) != BMS_V1_OK) {
            return 1;
        }
    }
    const auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - started);
    const double microseconds_per_operation = elapsed.count() * 1000000.0 / iterations;
    const double operations_per_second = iterations / elapsed.count();
    std::cout << std::fixed << std::setprecision(3)
              << "{\"iterations\":" << iterations
              << ",\"microseconds_per_operation\":" << microseconds_per_operation
              << ",\"operations_per_second\":" << operations_per_second
              << ",\"score\":" << score << ",\"worst_cell\":" << worst << "}\n";
    return 0;
}
