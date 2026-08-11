#include "bms_core.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace {
constexpr std::uint32_t kAbiVersion = 0x00010000U;
constexpr std::size_t kMinSteps = 3;
constexpr std::size_t kMaxSteps = 4096;
constexpr std::size_t kMaxChannels = 512;
constexpr double kTripVoltage = 4.25;
constexpr double kTripTemperature = 60.0;
constexpr double kResetVoltage = 4.15;
constexpr double kResetTemperature = 50.0;

bool valid_state(std::int32_t state) {
    return state == BMS_V1_NORMAL || state == BMS_V1_ISOLATE_LATCHED ||
           state == BMS_V1_OTA_HOLD;
}
}  // namespace

std::uint32_t bms_v1_abi_version() { return kAbiVersion; }

std::int32_t bms_v1_anomaly_score(const double* samples, std::size_t steps,
                                  std::size_t channels, double* score,
                                  std::size_t* worst_channel) {
    if (samples == nullptr || score == nullptr || worst_channel == nullptr ||
        steps < kMinSteps || channels == 0) {
        return BMS_V1_INVALID_ARGUMENT;
    }
    if (steps > kMaxSteps || channels > kMaxChannels ||
        channels > std::numeric_limits<std::size_t>::max() / steps) {
        return BMS_V1_RESOURCE_LIMIT;
    }
    const std::size_t sample_count = steps * channels;
    if (!std::all_of(samples, samples + sample_count,
                     [](double value) { return std::isfinite(value); })) {
        return BMS_V1_NON_FINITE_INPUT;
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
        const double scale = std::max(mad * 1.4826, 0.002);
        const double peak = *std::max_element(deltas.begin(), deltas.end());
        channel_scores[channel] = (peak - median) / scale;
    }
    *worst_channel = static_cast<std::size_t>(
        std::distance(channel_scores.begin(),
                      std::max_element(channel_scores.begin(), channel_scores.end())));
    *score = channel_scores[*worst_channel];
    return BMS_V1_OK;
}

std::int32_t bms_v1_decode_cell_frame(const std::uint8_t* payload, std::size_t length,
                                      double* first_cell_voltage,
                                      double* second_cell_voltage) {
    if (payload == nullptr || length != 8 || first_cell_voltage == nullptr ||
        second_cell_voltage == nullptr) {
        return BMS_V1_INVALID_ARGUMENT;
    }
    const std::uint16_t raw_first = static_cast<std::uint16_t>(payload[0] << 8U) | payload[1];
    const std::uint16_t raw_second = static_cast<std::uint16_t>(payload[2] << 8U) | payload[3];
    *first_cell_voltage = static_cast<double>(raw_first) / 10000.0;
    *second_cell_voltage = static_cast<double>(raw_second) / 10000.0;
    return BMS_V1_OK;
}

std::int32_t bms_v1_next_safety_state(std::int32_t current_state,
                                      double max_cell_voltage, double pack_temp_c,
                                      std::int32_t ota_requested,
                                      std::int32_t reset_requested,
                                      std::int32_t* next_state) {
    if (next_state == nullptr || !valid_state(current_state) ||
        (ota_requested != 0 && ota_requested != 1) ||
        (reset_requested != 0 && reset_requested != 1)) {
        return BMS_V1_INVALID_ARGUMENT;
    }
    if (!std::isfinite(max_cell_voltage) || !std::isfinite(pack_temp_c)) {
        return BMS_V1_NON_FINITE_INPUT;
    }

    const bool electrical_trip = max_cell_voltage > kTripVoltage ||
                                 pack_temp_c > kTripTemperature;
    const bool reset_safe = max_cell_voltage < kResetVoltage &&
                            pack_temp_c < kResetTemperature;
    if (electrical_trip) {
        *next_state = BMS_V1_ISOLATE_LATCHED;
    } else if (current_state == BMS_V1_ISOLATE_LATCHED) {
        *next_state = (reset_requested == 1 && reset_safe) ? BMS_V1_NORMAL
                                                           : BMS_V1_ISOLATE_LATCHED;
    } else if (ota_requested == 1) {
        *next_state = BMS_V1_OTA_HOLD;
    } else {
        // OTA hold is a reversible advisory state. Dropping the OTA request
        // resumes normal processing; it never clears a latched isolation.
        *next_state = BMS_V1_NORMAL;
    }
    return BMS_V1_OK;
}

double bms_anomaly_score(const double* samples, std::size_t steps, std::size_t channels,
                         std::size_t* worst_channel) {
    double score = -1.0;
    return bms_v1_anomaly_score(samples, steps, channels, &score, worst_channel) == BMS_V1_OK
               ? score
               : -1.0;
}

int bms_decode_cell_frame(const std::uint8_t* payload, std::size_t length,
                          double* first_cell_voltage, double* second_cell_voltage) {
    return bms_v1_decode_cell_frame(payload, length, first_cell_voltage,
                                    second_cell_voltage) == BMS_V1_OK
               ? 0
               : -1;
}

int bms_next_safety_state(int current_state, double max_cell_voltage, double pack_temp_c,
                          int ota_requested) {
    std::int32_t next_state = current_state;
    const auto status = bms_v1_next_safety_state(current_state, max_cell_voltage, pack_temp_c,
                                                 ota_requested != 0 ? 1 : 0, 0, &next_state);
    return status == BMS_V1_OK ? next_state : -1;
}
