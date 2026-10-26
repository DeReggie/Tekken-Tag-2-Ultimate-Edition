#include "title/eliza_assist.h"
#include <cassert>
#include <initializer_list>
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
    // Selecting either finisher returns input ownership immediately;
    // neither its startup nor its hit animation may extend the session.
    assert(!update("Vp_66lklk", 1, 58));
    assert(!update("Vp_66lklk", 23, 58));
    assert(!update("Vp_66lklk_H", 1, 54));
    assert(!update("Vp_6rklk", 1, 19)); // cannot restart mid-string
    assert(update("Vp_dash_C", 1, 33));
    assert(update("Vp_6rklk", 18, 19));
    assert(!update("Vp_6rklkrk", 1, 50));
    // If no second kick was selected, return when its input window closes.
    assert(update("Vp_dash_C", 1, 33));
    assert(update("Vp_6rklk", 18, 19));
    assert(!update("Vp_6rklk", 19, 19));
    assert(!update("Jn_3lp00", 1, 30)); // next df+1 belongs to the main
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
    // A deferred expiry releases on finisher selection, even when the
    // incoming move is still at frame 1 with many recovery frames left.
    for (const char* finisher : {"Vp_66lklk", "Vp_66lklk_H", "Vp_6rklkrk"}) {
        Session sequence;
        assert(sequence.update(true, true, true, 1, "Vp_dash_EX", 1, 33));
        assert(sequence.update(true, true, true, 1, "Vp_6rklk", 18, 19));
        assert(!sequence.update(true, true, true, 1, finisher, 1, 58));
        assert(!sequence.update(true, true, true, 1, finisher, 2, 58));
    }
    using cafe::title::eliza_assist::InputWindow;
    InputWindow input;
    input.add(0x2800, 0, 25, true); // Geese 2: restored motion capture
    input.add(0x182, 0, 25, false); // automatic special dispatch
    input.add(0x80, 0, 47, false);  // neutral recovery is irrelevant
    assert(input.buffered && input.control_end() == 26);
    Session geese;
    assert(geese.update_window(true, true, true, 1, 25, input.control_end(), true, false));
    InputWindow f1;
    f1.add(0x2800, 0, 34, true); // f+1 owns its fresh motion window
    assert(geese.update_window(true, true, true, 1, 1, f1.control_end(), true, false));
    assert(geese.update_window(true, true, true, 1, 34, f1.control_end(), true, false));
    // Committing a terminal special releases before its startup finishes.
    assert(!geese.update_window(true, true, true, 1, 1, 0, false, false));
    assert(!geese.update_window(true, true, true, 1, 2, 0, false, false));
    InputWindow shoryu;
    shoryu.add(0x182, 0x40000002, 22, false);
    shoryu.add(0x182, 0x40000008, 22, false);
    Session eliza;
    assert(eliza.update_window(true, true, true, 1, 22, shoryu.control_end(), true, false));
    assert(!eliza.update_window(true, true, true, 1, 23, shoryu.control_end(), true, false));
    // Ignore unbounded neutral input tables and unrelated property actions.
    InputWindow neutral;
    neutral.add(0x182, 0x40000001, 32767, false);
    neutral.add(0x2800, 0, 40, false);
    neutral.add(0x80, 0, 60, false);
    assert(!neutral.buffered && !neutral.control_end());
    assert(!eliza.update_window(false, true, true, 1, 1, 23, true, false));
    assert(!eliza.update_window(true, true, false, 1, 1, 23, true, false));
    assert(!eliza.update_window(true, false, true, 1, 1, 23, true, false));

    // 2 -> f+1 -> hcb+3 must not hand control back between the opening
    // rush and its automatic contact follow-up (the latter can super-cancel).
    Session jaei;
    assert(jaei.update_window(true, true, true, 1, 20, 26, true, false));
    assert(jaei.update_window(true, true, true, 1, 1, 35, true, false));
    const auto rush_end = cafe::title::eliza_assist::geese_contact_bridge("My_Jyaei_C", 29);
    assert(rush_end == 30);
    assert(jaei.update_window(true, true, true, 1, 1, rush_end, false, true));
    assert(jaei.update_window(true, true, true, 1, 22, rush_end, false, true));
    assert(jaei.update_window(true, true, true, 1, 1, 29, true, false)); // My_Jyaei_C2
    assert(jaei.update_window(true, true, true, 1, 28, 29, true, false));
    assert(!jaei.update_window(true, true, true, 1, 29, 29, true, false));
    Session whiff;
    assert(whiff.update_window(true, true, true, 1, 1, 35, true, false));
    assert(whiff.update_window(true, true, true, 1, 29, rush_end, false, true));
    assert(!whiff.update_window(true, true, true, 1, 30, rush_end, false, true));
    Session detached;
    assert(!detached.update_window(true, true, true, 1, 1, rush_end, false, true));
    assert(!cafe::title::eliza_assist::geese_contact_bridge("My_Jyaei_D", 29));
    assert(!cafe::title::eliza_assist::geese_contact_bridge("Vp_66lklk", 23));

}
