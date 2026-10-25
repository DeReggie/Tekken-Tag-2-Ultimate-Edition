#include "title/eliza_assist.h"
#include <cassert>
using cafe::title::eliza_assist::Session;
int main() {
    Session s;
    auto update = [&](const char* name, unsigned frame, unsigned recovery,
                      bool assault = true, unsigned partner = 1) {
        return s.update(true, true, assault, partner, name, frame, recovery);
    };
    // A late b+4 -> Glide entry remains possible beyond its frame-15 hit.
    assert(update("Vp_rk00B", 1, 45));
    assert(update("Vp_rk00B", 27, 45));
    assert(update("Vp_dash_EX", 1, 33));
    assert(update("Vp_dash_EX", 24, 33));
    assert(update("Vp_6rklk", 1, 46));
    assert(update("Vp_6rklk", 18, 46));
    assert(update("Vp_66lklk", 23, 58));
    assert(update("Vp_66lklk_H", 1, 54));
    assert(update("Vp_66lklk_H", 53, 54));
    assert(!update("Vp_66lklk_H", 54, 54));
    assert(!update("Vp_6rklk", 1, 46)); // cannot start midway through a string
    assert(update("Vp_dash_C", 1, 33));
    assert(update("Vp_6rklk", 18, 46));
    assert(update("Vp_6rklkrk", 49, 50));
    assert(!update("Vp_6rklkrk", 50, 50));
    assert(update("Vp_dash_EX2", 1, 33));
    assert(!update("sDm_High", 1, 30)); // interruption releases immediately
    assert(!update("Vp_6rklk", 1, 46));
    assert(update("Vp_dash_EX", 1, 33));
    assert(!update("Co_StChgOutB", 1, 35));
    assert(update("Vp_rk00B", 1, 45));
    assert(!update("Vp_rk00B", 2, 45, false));
    assert(!s.update(false, true, true, 1, "Vp_dash_EX", 1, 33));
    assert(!s.update(true, false, true, 1, "Vp_dash_EX", 1, 33));
    assert(!s.update(true, true, true, 0, "Vp_dash_EX", 1, 33));
    assert(update("Vp_dash_EX", 1, 33));
    assert(!update("Vp_6rklk", 1, 46, true, 2)); // roster/partner changed
    assert(!update("Vp_rk00B", 0, 45));
    assert(!update("Vp_dash_EX", 1, 0));
    assert(!update("Vp_dash_EX", 1, 10000));
    // Timings follow the installed pack, including modified recovery.
    assert(update("Vp_rk00B", 45, 60));
    assert(!update("Vp_rk00B", 60, 60));
}
