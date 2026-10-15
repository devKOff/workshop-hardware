#pragma once

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace test_support {

static uint32_t g_mock_millis = 0;

inline uint32_t millis() {
    return g_mock_millis;
}

inline void set_millis(uint32_t ms) {
    g_mock_millis = ms;
}

inline void advance_millis(uint32_t ms) {
    g_mock_millis += ms;
}

} // namespace test_support

#define millis test_support::millis

#endif // TEST_SUPPORT_H