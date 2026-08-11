#pragma once

#include <stddef.h>
#include <stdint.h>

// Stable C ABI. New integrations should call only bms_v1_* symbols and check
// the returned status before reading output parameters.
#ifdef __cplusplus
extern "C" {
#endif

enum bms_v1_status {
    BMS_V1_OK = 0,
    BMS_V1_INVALID_ARGUMENT = 1,
    BMS_V1_NON_FINITE_INPUT = 2,
    BMS_V1_RESOURCE_LIMIT = 3,
};

enum bms_v1_safety_state {
    BMS_V1_NORMAL = 0,
    BMS_V1_ISOLATE_LATCHED = 1,
    BMS_V1_OTA_HOLD = 2,
};

uint32_t bms_v1_abi_version(void);

int32_t bms_v1_anomaly_score(const double* samples, size_t steps,
                             size_t channels, double* score,
                             size_t* worst_channel);

int32_t bms_v1_decode_cell_frame(const uint8_t* payload, size_t length,
                                 double* first_cell_voltage,
                                 double* second_cell_voltage);

int32_t bms_v1_next_safety_state(int32_t current_state,
                                 double max_cell_voltage, double pack_temp_c,
                                 int32_t ota_requested,
                                 int32_t reset_requested,
                                 int32_t* next_state);

// Source/binary compatibility for the original demonstrator. These wrappers
// remain for v0 clients; they delegate to the v1 implementation.
double bms_anomaly_score(const double* samples, size_t steps, size_t channels,
                         size_t* worst_channel);
int bms_decode_cell_frame(const uint8_t* payload, size_t length,
                          double* first_cell_voltage, double* second_cell_voltage);
int bms_next_safety_state(int current_state, double max_cell_voltage, double pack_temp_c,
                          int ota_requested);
#ifdef __cplusplus
}
#endif
