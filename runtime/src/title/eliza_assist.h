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
// Installed input-only captures use 0x2800 and write the special buffer.
// Ordinary finite string inputs use 0x182/0x183. Neither automatic hit
// transitions nor a move's neutral-recovery row extend control.
struct InputWindow {
    uint32_t last = 0;
    bool buffered = false;
    void add(uint32_t mode, uint32_t button, uint32_t end, bool special_capture) {
        if (!end || end >= 180) return;
        if (mode == 0x2800 && special_capture) buffered = true;
        else if (!button || (mode != 0x182 && mode != 0x183)) return;
        if (end > last) last = end;
    }
    uint32_t control_end() const { return last ? last + 1 : 0; }
};
// Jaei Ken's opening rush has no player-selected follow-up. Contact
// automatically enters My_Jyaei_C2 during its active interval. Preserve
// an existing assist session across that gap, never start one mid-rush.
inline uint32_t geese_contact_bridge(std::string_view name, uint32_t last_active) {
    return name == "My_Jyaei_C" && last_active && last_active < 180 ? last_active + 1 : 0;
}
struct Session {
    uint32_t partner = 0;
    bool active = false;
    bool update_window(bool supported, bool human, bool assault,
                       uint32_t current_partner, uint32_t frame,
                       uint32_t control_end, bool starts, bool continues) {
        if (!supported || !human || !assault || !current_partner || !frame ||
            !control_end || control_end > 180 || frame >= control_end ||
            (!starts && !continues)) {
            *this = {};
            return false;
        }
        if (partner && partner != current_partner) *this = {};
        if (starts) { active = true; partner = current_partner; }
        return active;
    }
    bool update(bool eliza, bool human, bool assault, uint32_t current_partner,
                std::string_view name, uint32_t frame, uint32_t recovery) {
        return update_window(eliza, human, assault, current_partner, frame,
                             recovery, entry(name), continuation(name));
    }
};
} // namespace cafe::title::eliza_assist
