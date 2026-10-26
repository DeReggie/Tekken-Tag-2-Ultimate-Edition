#pragma once
#include <cstdint>
#include <string_view>

namespace cafe::title::eliza_assist {
// Protect stance selection and the first kick's string input window.
// Committed finishers run through native inactive assist handling, allowing
// the main fighter to act while their animations are still playing.
inline bool entry(std::string_view name) {
    return name == "Vp_rk00B" || name == "Vp_dash_C" ||
           name == "Vp_dash_EX" || name == "Vp_dash_EX2";
}
inline bool continuation(std::string_view name) {
    return name == "Vp_6rklk";
}
// Native 041CE0B0 consumes a positive countdown; 1 schedules its next tick.
inline constexpr uint32_t kRetryExpiryNextFrame = 1;
struct Session {
    uint32_t partner = 0;
    bool active = false;
    bool update(bool eliza, bool human, bool assault, uint32_t current_partner,
                std::string_view name, uint32_t frame, uint32_t recovery) {
        if (!eliza || !human || !assault || !current_partner || !frame ||
            !recovery || recovery > 180 || frame >= recovery ||
            (!entry(name) && !continuation(name))) {
            *this = {};
            return false;
        }
        if (partner && partner != current_partner) *this = {};
        if (entry(name)) {
            active = true;
            partner = current_partner;
        }
        return active;
    }
};
} // namespace cafe::title::eliza_assist
