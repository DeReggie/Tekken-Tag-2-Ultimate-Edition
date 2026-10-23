// The Settings page (see launcher.h), a page of the window beside the main
// one: the game's keyboard keys, an input a row in the GamePad's groups.
// Clicking a row's key and pressing a key on the keyboard gives it that key
// (taken from the input that had it, which gets the old one: they swap), and
// keyboard.ini is saved at once; the game reads it again while it runs.
// Keys are positions (USB HID usages, keymap.h), named as the user's layout
// names them.

#include "launcher.h"

#include "widgets.h"

#include <algorithm>
#include <cstdio>

namespace launcher {
namespace {

// What a key shows when it types something: that character, in capitals;
// dead keys (an accent typed before a letter) as their accent.
std::string typed_text(guint keyval) {
    struct Dead {
        guint keyval;
        gunichar shown;
    };
    static constexpr Dead kDead[] = {
        {GDK_KEY_dead_grave, U'`'},           {GDK_KEY_dead_acute, U'\u00b4'},     {GDK_KEY_dead_circumflex, U'^'},
        {GDK_KEY_dead_tilde, U'~'},           {GDK_KEY_dead_macron, U'\u00af'},    {GDK_KEY_dead_breve, U'\u02d8'},
        {GDK_KEY_dead_abovedot, U'\u02d9'},   {GDK_KEY_dead_diaeresis, U'\u00a8'}, {GDK_KEY_dead_abovering, U'\u00b0'},
        {GDK_KEY_dead_doubleacute, U'\u02dd'}, {GDK_KEY_dead_caron, U'\u02c7'},     {GDK_KEY_dead_cedilla, U'\u00b8'},
        {GDK_KEY_dead_ogonek, U'\u02db'},
    };
    gunichar c = keyval ? gdk_keyval_to_unicode(keyval) : 0;
    for (const Dead& d : kDead) {
        if (!c && d.keyval == keyval) c = d.shown;
    }
    if (!c || g_unichar_iscntrl(c) || g_unichar_isspace(c)) return {};
    char text[8];
    return std::string(text, static_cast<size_t>(g_unichar_to_utf8(g_unichar_toupper(c), text)));
}

// The keyboard and its layout now, from GTK 4.18 on (the property is looked
// up, so that the launcher still starts with an older GTK); none before.
GdkDevice* layout_keyboard(GtkWidget* window) {
    GdkSeat* seat = gdk_display_get_default_seat(gtk_widget_get_display(window));
    GdkDevice* keyboard = seat ? gdk_seat_get_keyboard(seat) : nullptr;
    return keyboard && g_object_class_find_property(G_OBJECT_GET_CLASS(keyboard), "active-layout-index") ? keyboard
                                                                                                         : nullptr;
}

std::optional<guint> active_layout(GdkDevice* keyboard) {
    int layout = -1;
    if (keyboard) g_object_get(keyboard, "active-layout-index", &layout, nullptr);
    return layout >= 0 ? std::optional<guint>(static_cast<guint>(layout)) : std::nullopt;
}

} // namespace

// ---------------------------------------------------------------- the page

GtkWidget* Launcher::build_settings() {
    settings_content_ = ui::box(GTK_ORIENTATION_VERTICAL, 12, "launcher-content");
    GtkWidget* title = ui::label("Keyboard", "section-title");
    gtk_box_append(GTK_BOX(settings_content_), title);
    gtk_box_append(GTK_BOX(settings_content_),
                   ui::label("Keys by position on the keyboard; the game uses them as the Wii U GamePad's buttons. "
                             "Changes apply at once, also while the game runs.",
                             "dim small"));
    GtkWidget* card = ui::box(GTK_ORIENTATION_VERTICAL, 18, "card");
    gtk_widget_set_margin_top(card, 4);
    keys_error_ = ui::label("", "error-text");
    gtk_widget_set_visible(keys_error_, FALSE);
    gtk_box_append(GTK_BOX(card), keys_error_);
    keys_note_ = ui::box(GTK_ORIENTATION_HORIZONTAL, 10, "check-row");
    GtkWidget* warning = gtk_image_new_from_icon_name("dialog-warning-symbolic");
    gtk_widget_add_css_class(warning, "warn");
    gtk_widget_set_valign(warning, GTK_ALIGN_START);
    gtk_box_append(GTK_BOX(keys_note_), warning);
    GtkWidget* note = ui::label("");
    gtk_widget_set_hexpand(note, TRUE);
    gtk_box_append(GTK_BOX(keys_note_), note);
    gtk_widget_set_visible(keys_note_, FALSE);
    gtk_box_append(GTK_BOX(card), keys_note_);

    GtkWidget* groups = ui::columns_new(18);
    GtkWidget* list = nullptr;
    const char* group = nullptr;
    for (int i = 0; i < kInputs; ++i) {
        const Input& in = inputs()[i];
        if (!group || std::string(group) != in.group) {
            group = in.group;
            GtkWidget* box = ui::box(GTK_ORIENTATION_VERTICAL, 0);
            gtk_box_append(GTK_BOX(box), ui::label(group, "key-group-title", false));
            list = ui::box(GTK_ORIENTATION_VERTICAL, 0, "key-list");
            gtk_box_append(GTK_BOX(box), list);
            ui::columns_append(groups, box);
        }
        KeyRow& r = key_rows_[i];
        r.row = ui::box(GTK_ORIENTATION_VERTICAL, 0, "key-row");
        GtkWidget* line = ui::box(GTK_ORIENTATION_HORIZONTAL, 10);
        GtkWidget* icon = gtk_image_new_from_icon_name((std::string("ttt2-input-") + in.id).c_str());
        gtk_image_set_pixel_size(GTK_IMAGE(icon), 32);
        gtk_widget_set_valign(icon, GTK_ALIGN_CENTER);
        gtk_box_append(GTK_BOX(line), icon);
        GtkWidget* names = ui::box(GTK_ORIENTATION_VERTICAL, 1);
        gtk_widget_set_hexpand(names, TRUE);
        gtk_widget_set_valign(names, GTK_ALIGN_CENTER);
        GtkWidget* name = ui::label(in.name, nullptr, false);
        gtk_label_set_ellipsize(GTK_LABEL(name), PANGO_ELLIPSIZE_END);
        gtk_box_append(GTK_BOX(names), name);
        // (Wrapped in the width the row has: a message does not widen it.)
        r.note = ui::label("", "key-note");
        gtk_label_set_max_width_chars(GTK_LABEL(r.note), 1);
        gtk_widget_set_visible(r.note, FALSE);
        gtk_box_append(GTK_BOX(names), r.note);
        gtk_box_append(GTK_BOX(line), names);

        r.button = gtk_button_new();
        ui::add_classes(r.button, "keycap");
        ui::set_id(r.button, std::string("key:") + in.id);
        gtk_widget_set_valign(r.button, GTK_ALIGN_CENTER);
        // The key, or "Press a key…" while it waits for one: as wide as
        // each other, so that the rows keep their layout.
        r.label = gtk_label_new("");
        gtk_label_set_ellipsize(GTK_LABEL(r.label), PANGO_ELLIPSIZE_END);
        gtk_label_set_max_width_chars(GTK_LABEL(r.label), 14);
        r.face = gtk_stack_new();
        gtk_stack_set_transition_type(GTK_STACK(r.face), GTK_STACK_TRANSITION_TYPE_CROSSFADE);
        gtk_stack_set_transition_duration(GTK_STACK(r.face), 120);
        gtk_stack_add_named(GTK_STACK(r.face), r.label, "key");
        GtkWidget* waiting = gtk_label_new("Press a key…");
        gtk_widget_add_css_class(waiting, "key-waiting");
        gtk_stack_add_named(GTK_STACK(r.face), waiting, "waiting");
        gtk_button_set_child(GTK_BUTTON(r.button), r.face);
        ui::set_tooltip(r.button, std::string("Change the key for ") + in.full);
        g_object_set_data(G_OBJECT(r.button), "input", GINT_TO_POINTER(i));
        g_signal_connect(r.button, "clicked", G_CALLBACK(+[](GtkWidget* b, gpointer data) {
                             static_cast<Launcher*>(data)->pick_key(
                                 GPOINTER_TO_INT(g_object_get_data(G_OBJECT(b), "input")));
                         }),
                         this);
        gtk_box_append(GTK_BOX(line), r.button);
        gtk_box_append(GTK_BOX(r.row), line);
        gtk_box_append(GTK_BOX(list), r.row);
    }
    gtk_box_append(GTK_BOX(card), groups);

    GtkWidget* row = ui::box(GTK_ORIENTATION_HORIZONTAL, 10);
    restore_button_ = ui::button("Restore Defaults");
    ui::set_id(restore_button_, "restore-keys");
    clicked(restore_button_, [](Launcher* self) { self->restore_keys(); });
    gtk_box_append(GTK_BOX(row), restore_button_);
    gtk_box_append(GTK_BOX(card), row);
    gtk_box_append(GTK_BOX(settings_content_), card);

    GtkWidget* scroller = gtk_scrolled_window_new();
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroller), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_scrolled_window_set_child(GTK_SCROLLED_WINDOW(scroller), ui::clamp_new(settings_content_, kColumn));

    // Keys are taken on the window, before any widget sees them (Tab, Enter
    // and the arrows are keys like the others there).
    GtkEventController* keys = gtk_event_controller_key_new();
    gtk_event_controller_set_propagation_phase(keys, GTK_PHASE_CAPTURE);
    g_signal_connect(keys, "key-pressed", G_CALLBACK(on_key_pressed), this);
    g_signal_connect(keys, "key-released", G_CALLBACK(on_key_released), this);
    gtk_widget_add_controller(window_, keys);
    watch_layout();
    return scroller;
}

bool Launcher::in_settings() const {
    const char* page = stack_ ? gtk_stack_get_visible_child_name(GTK_STACK(stack_)) : nullptr;
    return page && std::string_view(page) == "settings";
}

void Launcher::open_settings() {
    if (install_.state != InstallState::kInstalled || in_settings()) return;
    // (Read each time: it may have been changed by hand meanwhile.)
    Keymap::Notes notes;
    keymap_ = Keymap::load(places_.keyboard(), &notes);
    const std::string file = places_.keyboard().string();
    for (const std::string& w : notes.warnings) {
        std::fprintf(stderr, "ttt2-launcher: %s: %s\n", file.c_str(), w.c_str());
    }
    for (const std::string& w : notes.shared) {
        std::fprintf(stderr, "ttt2-launcher: %s: one key on two inputs, %s\n", file.c_str(), w.c_str());
    }
    if (!notes.error.empty()) std::fprintf(stderr, "ttt2-launcher: %s: %s\n", file.c_str(), notes.error.c_str());
    // What is shown is not the game's: the page says so, and Restore
    // Defaults (or any key chosen) saves what is shown.
    keys_as_shown_ = notes.as_shown();
    std::string why;
    if (!notes.error.empty()) {
        why = "keyboard.ini cannot be read (" + notes.error + "): the game uses its default keys, shown here. "
              "Choosing a key, or Restore Defaults, writes the file anew.";
    } else if (!notes.shared.empty()) {
        std::string keys;
        for (size_t i = 0; i < notes.shared.size(); ++i) keys += (i ? "; " : "") + notes.shared[i];
        why = "keyboard.ini, changed by hand, gives a key to two inputs, which the game presses together (" + keys +
              "). Here each input has a key of its own: choosing a key, or Restore Defaults, saves them as shown.";
    }
    ui::set_text(gtk_widget_get_last_child(keys_note_), why);
    gtk_widget_set_visible(keys_note_, !why.empty());
    gtk_widget_set_visible(keys_error_, FALSE);
    // (The keyboard's layout now: no key needs to be pressed for the labels.)
    if (const auto layout = active_layout(layout_keyboard(window_))) layout_ = *layout;
    show_keys();
    gtk_stack_set_visible_child_name(GTK_STACK(stack_), "settings");
    gtk_label_set_text(GTK_LABEL(title_), "Settings");
    gtk_widget_set_visible(back_button_, TRUE);
    gtk_widget_set_visible(refresh_button_, FALSE);
    gtk_widget_grab_focus(key_rows_[0].button);
}

void Launcher::close_settings() {
    if (!in_settings()) return;
    stop_picking();
    gtk_stack_set_visible_child_name(GTK_STACK(stack_), "main");
    gtk_label_set_text(GTK_LABEL(title_), "Tekken Tag 2 Ultimate Edition");
    gtk_widget_set_visible(back_button_, FALSE);
    gtk_widget_set_visible(refresh_button_, TRUE);
    if (GtkWidget* gear = ui::find_id(game_card_, "settings")) gtk_widget_grab_focus(gear);
}

// ---------------------------------------------------------------- keys

std::string Launcher::key_label(int usage) const {
    const Key* key = key_by_usage(usage);
    if (!key || !key->typed) return key_name(usage);
    // What this key types in the layout used (else the first one),
    // unshifted; on the number row its digit when it types one with Shift
    // (AZERTY's & is the key of 1, as the keycap says).
    GdkKeymapKey* entries = nullptr;
    guint* keyvals = nullptr;
    int count = 0;
    std::string label;
    if (gdk_display_map_keycode(gtk_widget_get_display(window_), static_cast<guint>(key->evdev + 8), &entries,
                                &keyvals, &count)) {
        for (const guint layout : {layout_, 0u}) {
            guint plain = 0, shifted = 0;
            for (int i = 0; i < count; ++i) {
                if (entries[i].group != static_cast<int>(layout)) continue;
                if (entries[i].level == 0) plain = keyvals[i];
                else if (entries[i].level == 1) shifted = keyvals[i];
            }
            label = typed_text(plain);
            const std::string digit = typed_text(shifted);
            if (usage >= 30 && usage <= 39 && digit.size() == 1 && digit[0] >= '0' && digit[0] <= '9') label = digit;
            if (!label.empty()) break;
        }
        g_free(entries);
        g_free(keyvals);
    }
    return label.empty() ? key->name : label;
}

void Launcher::show_keys() {
    for (int i = 0; i < kInputs; ++i) {
        const KeyRow& r = key_rows_[i];
        const std::string label = key_label(keymap_.key(i));
        ui::set_text(r.label, label);
        gtk_stack_set_visible_child_name(GTK_STACK(r.face), picking_ == i ? "waiting" : "key");
        if (picking_ == i) gtk_widget_add_css_class(r.button, "picking");
        else gtk_widget_remove_css_class(r.button, "picking");
        // (Read out as the input and its key, not the key alone.)
        const std::string spoken = std::string(inputs()[i].full) + ": " + (picking_ == i ? "press a key" : label);
        gtk_accessible_update_property(GTK_ACCESSIBLE(r.button), GTK_ACCESSIBLE_PROPERTY_LABEL, spoken.c_str(), -1);
    }
    // (Restore Defaults also writes a file that is not what is shown. Pressed
    // with the keyboard, it greys out holding the focus: that goes to the
    // first key, as it would be lost.)
    const bool restorable = !keymap_.is_default() || !keys_as_shown_;
    if (!restorable && gtk_root_get_focus(GTK_ROOT(window_)) == restore_button_) {
        gtk_widget_grab_focus(key_rows_[0].button);
    }
    gtk_widget_set_sensitive(restore_button_, restorable);
}

void Launcher::watch_layout() {
    // (Before GTK 4.18, only the keys pressed tell the layout: key_layout.)
    GdkDevice* keyboard = layout_keyboard(window_);
    if (!keyboard) return;
    const auto changed = +[](GObject* device, GParamSpec*, gpointer data) {
        if (const auto layout = active_layout(GDK_DEVICE(device))) static_cast<Launcher*>(data)->set_layout(*layout);
    };
    g_signal_connect(keyboard, "notify::active-layout-index", G_CALLBACK(changed), this);
}

void Launcher::set_layout(guint layout) {
    if (layout == layout_) return;
    layout_ = layout;
    if (in_settings()) show_keys();
}

void Launcher::key_layout(guint keycode, guint layout) {
    // A key that the keymap defines in fewer layouts than the letters (Shift,
    // Enter, Tab, the arrows: in one) gives its own layout, the first,
    // whichever one is used: only a key defined in every layout tells.
    const auto groups = [&](guint code) {
        GdkKeymapKey* entries = nullptr;
        guint* keyvals = nullptr;
        int count = 0, most = 0;
        if (gdk_display_map_keycode(gtk_widget_get_display(window_), code, &entries, &keyvals, &count)) {
            for (int i = 0; i < count; ++i) most = std::max(most, entries[i].group + 1);
            g_free(entries);
            g_free(keyvals);
        }
        return most;
    };
    constexpr guint kLetterA = 30 + 8; // (every layout has a key there)
    if (groups(keycode) >= std::max(groups(kLetterA), 1)) set_layout(layout);
}

void Launcher::pick_key(int input) {
    const bool again = picking_ == input;
    stop_picking();
    if (again) return;
    picking_ = input;
    modifier_ = 0;
    show_keys();
}

void Launcher::stop_picking() {
    modifier_ = 0;
    if (picking_ < 0) return;
    const int input = picking_;
    picking_ = -1;
    // (A refusal's message goes with it.)
    if (gtk_widget_has_css_class(key_rows_[input].note, "error-text")) {
        ++key_rows_[input].serial;
        gtk_widget_set_visible(key_rows_[input].note, FALSE);
    }
    show_keys();
}

Launcher::Taken Launcher::take_key(guint keycode) {
    const auto taken = [&](Taken t) {
        taken_ = t;
        return t;
    };
    const int input = picking_;
    if (input < 0) return taken({false, "no key is being chosen"});
    const Key* key = keycode >= 8 ? key_by_evdev(static_cast<int>(keycode) - 8) : nullptr;
    if (key && key->usage == kEscape) {
        stop_picking();
        return taken({false, "cancelled with Esc"});
    }
    const Keymap before = keymap_;
    const Keymap::Bound bound =
        key ? keymap_.bind(input, key->usage) : Keymap::Bound{false, -1, "This key cannot be used"};
    if (!bound.ok) {
        note_key(input, bound.why, "error-text", false, 4);
        return taken({false, bound.why});
    }
    picking_ = -1;
    modifier_ = 0;
    if (!save_keys(before)) return taken({false, gtk_label_get_text(GTK_LABEL(keys_error_))});
    show_keys();
    note_key(input, "", nullptr, false, 0); // (an older message of its own is not about this key: gone)
    std::string text = std::string(inputs()[input].full) + " is " + key_label(key->usage);
    if (bound.swapped >= 0) {
        note_key(bound.swapped, std::string("Swapped with ") + inputs()[input].full, "swapped-note", true, 3);
        text += std::string(", swapped with ") + inputs()[bound.swapped].full;
    }
    return taken({true, text});
}

void Launcher::restore_keys() {
    stop_picking();
    const Keymap before = keymap_;
    keymap_.reset();
    if (!save_keys(before)) return;
    show_keys();
    // (The rows that changed show it for a moment.)
    for (int i = 0; i < kInputs; ++i) {
        if (before.key(i) != keymap_.key(i)) note_key(i, "", nullptr, true, 2);
    }
}

bool Launcher::save_keys(const Keymap& before) {
    std::string error;
    if (keymap_.save(places_.keyboard(), &error)) {
        gtk_widget_set_visible(keys_error_, FALSE);
        keys_as_shown_ = true; // (the file is what is shown now)
        gtk_widget_set_visible(keys_note_, FALSE);
        return true;
    }
    // (What is shown is what the game has.)
    keymap_ = before;
    ui::set_text(keys_error_, "The keys cannot be saved: " + error);
    gtk_widget_set_visible(keys_error_, TRUE);
    show_keys();
    return false;
}

void Launcher::note_key(int input, const std::string& text, const char* classes, bool flash, guint seconds) {
    KeyRow& r = key_rows_[input];
    const int serial = ++r.serial;
    if (text.empty() && !flash) {
        gtk_widget_set_visible(r.note, FALSE);
        gtk_widget_remove_css_class(r.row, "flash");
        return;
    }
    ui::set_text(r.note, text);
    gtk_widget_remove_css_class(r.note, "error-text");
    gtk_widget_remove_css_class(r.note, "swapped-note");
    ui::add_classes(r.note, classes);
    gtk_widget_set_visible(r.note, !text.empty());
    if (flash) gtk_widget_add_css_class(r.row, "flash");
    struct Note {
        Launcher* self;
        int input, serial;
    };
    g_timeout_add_seconds_full(G_PRIORITY_DEFAULT, seconds, +[](gpointer data) -> gboolean {
        const auto* n = static_cast<Note*>(data);
        KeyRow& r = n->self->key_rows_[n->input];
        if (r.serial == n->serial) {
            gtk_widget_set_visible(r.note, FALSE);
            gtk_widget_remove_css_class(r.row, "flash");
        }
        return G_SOURCE_REMOVE;
    }, new Note{this, input, serial}, +[](gpointer data) { delete static_cast<Note*>(data); });
}

gboolean Launcher::on_key_pressed(GtkEventControllerKey* keys, guint keyval, guint keycode, GdkModifierType state,
                                  gpointer data) {
    std::optional<guint> layout;
    if (GdkEvent* event = gtk_event_controller_get_current_event(GTK_EVENT_CONTROLLER(keys))) {
        layout = gdk_key_event_get_layout(event);
    }
    return static_cast<Launcher*>(data)->key_down(keycode, keyval, state, layout);
}

void Launcher::on_key_released(GtkEventControllerKey*, guint, guint keycode, GdkModifierType, gpointer data) {
    static_cast<Launcher*>(data)->key_up(keycode);
}

bool Launcher::key_down(guint keycode, guint keyval, GdkModifierType state, std::optional<guint> layout) {
    const bool repeat = !held_.insert(keycode).second;
    if (layout) key_layout(keycode, *layout);
    if (picking_ < 0) {
        // Alt+Left goes back, as in a browser.
        const auto modifiers = state & gtk_accelerator_get_default_mod_mask();
        if (in_settings() && keyval == GDK_KEY_Left && modifiers == GDK_ALT_MASK) {
            close_settings();
            return true;
        }
        return false;
    }
    // (The key that clicked the button, held, repeats: it is not taken.)
    if (repeat) return true;
    const auto usage = [](guint code) {
        const Key* key = code >= 8 ? key_by_evdev(static_cast<int>(code) - 8) : nullptr;
        return key ? key->usage : 0;
    };
    // Ctrl, Shift, Alt or Super held with another key: a shortcut (Alt+Tab,
    // Ctrl+Q), the desktop's or the window's, not a key for the game.
    // Choosing stops, and the key goes on.
    if (std::any_of(held_.begin(), held_.end(), [&](guint code) {
            const int u = usage(code);
            return code != keycode && u >= 224 && u <= 231;
        })) {
        stop_picking();
        return false;
    }
    // A modifier alone is taken once it is let go (pressed first, it may be
    // the start of a shortcut).
    if (modifier_key(usage(keycode))) {
        modifier_ = keycode;
        return true;
    }
    take_key(keycode);
    return true;
}

void Launcher::key_up(guint keycode) {
    held_.erase(keycode);
    if (modifier_ != keycode) return;
    modifier_ = 0;
    if (picking_ >= 0) take_key(keycode);
}

} // namespace launcher
