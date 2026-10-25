#pragma once
#include <cstdint>
#include <string_view>

namespace cafe::title::eliza_assist {
// A move-scoped extension of the native Tag Assault session, not a timer
// extension for all fighters. Recovery is read from the installed move's
// neutral cancel, so custom pack timings cannot outlive their actual move.
inline bool entry(std::string_view name) {
    return name == "Vp_rk00B" || name == "Vp_dash_C" ||
           name == "Vp_dash_EX" || name == "Vp_dash_EX2";
}
inline bool continuation(std::string_view name) {
    return name == "Vp_6rklk" || name == "Vp_66lklk" ||
           name == "Vp_66lklk_H" || name == "Vp_6rklkrk";
}
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
