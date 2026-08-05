#pragma once

#include <cstddef>
#include <cstdint>

extern "C" {
double bms_anomaly_score(const double* samples, std::size_t steps, std::size_t channels,
                         std::size_t* worst_channel);
int bms_decode_cell_frame(const std::uint8_t* payload, std::size_t length,
                          double* first_cell_voltage, double* second_cell_voltage);
int bms_next_safety_state(int current_state, double max_cell_voltage, double pack_temp_c,
                          int ota_requested);
}
