#include "bms_core.h"

#include <assert.h>

int main(void) {
    double samples[] = {3.7, 3.7, 3.7};
    double score = -1.0;
    size_t worst = 99;
    assert(bms_v1_abi_version() == 0x00010000U);
    assert(bms_v1_anomaly_score(samples, 3, 1, &score, &worst) == BMS_V1_OK);
    assert(worst == 0);
    return 0;
}
