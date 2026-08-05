#include "bms_core.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

int main() {
    std::array<double, 12> samples{3.70, 3.71, 3.70, 3.71, 3.70, 3.71,
                                   3.70, 3.71, 3.70, 4.40, 3.70, 3.71};
    std::size_t worst = 99;
    const double score = bms_anomaly_score(samples.data(), 6, 2, &worst);
    assert(score > 100.0);
    assert(worst == 1);

    std::array<std::uint8_t, 8> frame{0x90, 0x88, 0x91, 0x16, 0, 0, 0, 0};
    double first = 0.0;
    double second = 0.0;
    assert(bms_decode_cell_frame(frame.data(), frame.size(), &first, &second) == 0);
    assert(first > 3.69 && first < 3.71);
    assert(second > 3.70 && second < 3.72);
    assert(bms_next_safety_state(0, 4.30, 30.0, 0) == 1);
    assert(bms_next_safety_state(0, 3.80, 30.0, 1) == 2);
    return 0;
}
