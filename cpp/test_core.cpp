#include "bms_core.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>

int main() {
    assert(bms_v1_abi_version() == 0x00010000U);

    std::array<double, 12> samples{3.70, 3.71, 3.70, 3.71, 3.70, 3.71,
                                   3.70, 3.71, 3.70, 4.40, 3.70, 3.71};
    std::size_t worst = 99;
    double score = -1.0;
    assert(bms_v1_anomaly_score(samples.data(), 6, 2, &score, &worst) == BMS_V1_OK);
    assert(score > 100.0);
    assert(worst == 1);

    samples[0] = std::nan("");
    assert(bms_v1_anomaly_score(samples.data(), 6, 2, &score, &worst) ==
           BMS_V1_NON_FINITE_INPUT);
    assert(bms_v1_anomaly_score(samples.data(), 5000, 2, &score, &worst) ==
           BMS_V1_RESOURCE_LIMIT);

    std::array<std::uint8_t, 8> frame{0x90, 0x88, 0x91, 0x16, 0, 0, 0, 0};
    double first = 0.0;
    double second = 0.0;
    assert(bms_v1_decode_cell_frame(frame.data(), frame.size(), &first, &second) == BMS_V1_OK);
    assert(first > 3.69 && first < 3.71);
    assert(second > 3.70 && second < 3.72);

    std::int32_t state = -1;
    assert(bms_v1_next_safety_state(BMS_V1_NORMAL, 4.30, 30.0, 0, 0, &state) == BMS_V1_OK);
    assert(state == BMS_V1_ISOLATE_LATCHED);
    assert(bms_v1_next_safety_state(state, 3.80, 30.0, 0, 0, &state) == BMS_V1_OK);
    assert(state == BMS_V1_ISOLATE_LATCHED);
    assert(bms_v1_next_safety_state(state, 3.80, 30.0, 0, 1, &state) == BMS_V1_OK);
    assert(state == BMS_V1_NORMAL);
    assert(bms_v1_next_safety_state(state, 3.80, 30.0, 1, 0, &state) == BMS_V1_OK);
    assert(state == BMS_V1_OTA_HOLD);
    assert(bms_v1_next_safety_state(state, 3.80, 30.0, 0, 0, &state) == BMS_V1_OK);
    assert(state == BMS_V1_NORMAL);
    assert(bms_v1_next_safety_state(99, 3.80, 30.0, 0, 0, &state) ==
           BMS_V1_INVALID_ARGUMENT);
    assert(bms_v1_next_safety_state(BMS_V1_NORMAL, 3.80, 30.0, 2, 0, &state) ==
           BMS_V1_INVALID_ARGUMENT);
    return 0;
}
