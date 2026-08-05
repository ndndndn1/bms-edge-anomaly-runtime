#include "bms_core.h"

#include <algorithm>
#include <cmath>
#include <vector>

double bms_anomaly_score(const double* samples, std::size_t steps, std::size_t channels,
                         std::size_t* worst_channel) {
    if (samples == nullptr || worst_channel == nullptr || steps < 3 || channels == 0) {
        return -1.0;
    }
    std::vector<double> channel_scores(channels, 0.0);
    for (std::size_t channel = 0; channel < channels; ++channel) {
        std::vector<double> deltas;
        deltas.reserve(steps - 1);
        for (std::size_t step = 1; step < steps; ++step) {
            const double current = samples[step * channels + channel];
            const double previous = samples[(step - 1) * channels + channel];
            deltas.push_back(std::abs(current - previous));
        }
        std::vector<double> ordered = deltas;
        std::sort(ordered.begin(), ordered.end());
        const double median = ordered[ordered.size() / 2];
        std::vector<double> deviations;
        deviations.reserve(ordered.size());
        for (double value : deltas) {
            deviations.push_back(std::abs(value - median));
        }
        std::sort(deviations.begin(), deviations.end());
        const double mad = deviations[deviations.size() / 2];
        // Two millivolts is the detector's measurement-noise floor. It prevents
        // quantized, otherwise healthy telemetry from producing an infinite
        // robust z-score when the median absolute deviation is zero.
        const double scale = std::max(mad * 1.4826, 0.002);
        const double peak = *std::max_element(deltas.begin(), deltas.end());
        channel_scores[channel] = (peak - median) / scale;
    }
    *worst_channel = static_cast<std::size_t>(
        std::distance(channel_scores.begin(), std::max_element(channel_scores.begin(), channel_scores.end())));
    return channel_scores[*worst_channel];
}

int bms_decode_cell_frame(const std::uint8_t* payload, std::size_t length,
                          double* first_cell_voltage, double* second_cell_voltage) {
    if (payload == nullptr || length != 8 || first_cell_voltage == nullptr ||
        second_cell_voltage == nullptr) {
        return -1;
    }
    const std::uint16_t raw_first = static_cast<std::uint16_t>(payload[0] << 8U) | payload[1];
    const std::uint16_t raw_second = static_cast<std::uint16_t>(payload[2] << 8U) | payload[3];
    *first_cell_voltage = static_cast<double>(raw_first) / 10000.0;
    *second_cell_voltage = static_cast<double>(raw_second) / 10000.0;
    return 0;
}

int bms_next_safety_state(int current_state, double max_cell_voltage, double pack_temp_c,
                          int ota_requested) {
    constexpr int normal = 0;
    constexpr int isolate = 1;
    constexpr int ota_hold = 2;
    if (max_cell_voltage > 4.25 || pack_temp_c > 60.0) {
        return isolate;
    }
    if (ota_requested != 0 && current_state == normal) {
        return ota_hold;
    }
    if (current_state == isolate && max_cell_voltage < 4.15 && pack_temp_c < 50.0) {
        return normal;
    }
    return current_state;
}
