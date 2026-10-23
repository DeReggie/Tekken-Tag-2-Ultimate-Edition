#pragma once

// The launcher's window: the game (install from the player's .wua, play,
// update, uninstall) above the characters (Tekken 7's, added through the
// importer), with the task that runs (one at a time) at the bottom; and its
// Settings, a page of its own (the game's keyboard keys).
//
// launcher.cpp   the window, finding things, refreshing the state, tests
// game.cpp       the game's section and its tasks
// characters.cpp the characters' section and its tasks
// settings.cpp   the Settings page: the game's keyboard keys
// task.cpp       the task panel: progress, Cancel, the log

#include "keymap.h"
#include "paths.h"
#include "process.h"
#include "protocol.h"
#include "status.h"
#include "test_actions.h"
#include "uninstall.h"

#include <gtk/gtk.h>

#include <array>
#include <chrono>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>

namespace launcher {

// The content's width at most: lines stay readable in a wide window.
inline constexpr int kColumn = 760;

// One thing checked before an install: what, how it is, and the command
// that installs what is missing.
struct Check {
    bool ok = true;
    std::string title, detail, command;
};

struct Options {
    fs::path game;       // a .wua given on the command line: chosen already
    fs::path screenshot; // --screenshot: the window's picture once it is idle, then quit
};

class Launcher {
public:
    Launcher(GtkApplication* app, Options options);
    ~Launcher();
    void present();
    void open_game(const fs::path& game);

private:
    // ------------------------------------------------ launcher.cpp
    void build_window();
    void refresh();                 // the install's state, and the importer's status
    void check_again();             // the window's button: refresh(), and ask Steam again after a failure
    void load_status();
    void check_ownership();
    void show_all();                // both sections, from the state
    bool busy() const;              // a task, a status or an ownership check under way
    void settled();                 // something ended: tests and the screenshot go on
    void run_next_test();
    void test_done(bool ok, const std::string& text);
    // The window's picture (once its next frame is drawn), then `done`.
    void picture(GtkWidget* window, const fs::path& file, std::function<void()> done);
    void save_shot(GtkWidget* window, const std::string& label, std::function<void()> done = {});
    // Calls `action` when the button is clicked.
    void clicked(GtkWidget* button, void (*action)(Launcher*));
    Process::Environment importer_environment() const;
    std::vector<std::string> importer_command(const std::string& script) const;
    static gboolean on_close(GtkWindow* window, gpointer self);
    static void stop_and_quit(GObject* dialog, GAsyncResult* result, gpointer self);
    static void on_active(GObject* window, GParamSpec*, gpointer self);

    // ------------------------------------------------ game.cpp
    struct Preflight {
        fs::path game, folder;
        bool running = false;
        std::vector<Check> checks;
    };
    void show_game();
    // Whether the installed program runs: started here, or anywhere else
    // (the menu entry, an earlier launcher). While one started elsewhere
    // runs, the card is shown again once it ends.
    bool game_running() const;
    void watch_game();
    void game_installed(GtkWidget* card);
    void game_unfinished(GtkWidget* card);
    void game_not_installed(GtkWidget* card);
    void game_installing(GtkWidget* card);
    void show_preflight(GtkWidget* card);
    void choose_game(std::function<void(const fs::path&)> then);
    void choose_folder();
    void start_install(const fs::path& game, const fs::path& chosen);
    void run_preflight();
    void preflight_done();
    void begin_install();
    void start_update();
    void ask_uninstall();
    static void uninstall_confirmed(GtkWidget* button, gpointer self);
    void start_uninstall(UninstallOptions options);
    void play();
    void resume();
    // Shows why something cannot be done (as a task's result).
    void refuse(const std::string& title, const std::string& why);

    // ------------------------------------------------ characters.cpp
    enum class Owned { kUnknown, kChecking, kKnown, kFailed };
    void show_characters();
    GtkWidget* fighter_row(const Fighter& fighter, bool usable);
    void start_import(const std::vector<std::string>& names);
    void start_remove(const std::vector<std::string>& names);
    bool addable(const Fighter& fighter) const;
    std::vector<std::string> base_to_add() const;
    std::vector<std::string> owned_to_add() const;
    bool can_import(std::string* why = nullptr) const;
    std::optional<bool> owns(const Fighter& fighter) const;

    // ------------------------------------------------ settings.cpp
    GtkWidget* build_settings(); // the page (in the window's stack)
    void open_settings();
    void close_settings();
    bool in_settings() const;
    void show_keys(); // each input's key, named as the user's keyboard layout names it
    std::string key_label(int usage) const;
    // The keyboard layout the labels name: the keyboard's (GTK 4.18 on), and
    // the one a key pressed was typed in, when that key tells.
    void watch_layout();
    void set_layout(guint layout);
    void key_layout(guint keycode, guint layout);
    // A key button clicked: the next key pressed (on the window) is that
    // input's; clicked again, or Esc, it is not.
    void pick_key(int input);
    void stop_picking();
    // That key pressed (an XKB keycode) while picking: given to the input
    // (swapped with the one that had it, saved), refused (picking goes on),
    // or Esc. What happened, for tests.
    struct Taken {
        bool ok = false;
        std::string text;
    };
    Taken take_key(guint keycode);
    // A key pressed and let go on the window (an XKB keycode; its layout when
    // an event tells it): while a key is chosen, the key taken (a modifier
    // once it is let go, without another key), refused or a shortcut, which
    // stops choosing; else Alt+Left goes back. Whether it was used.
    bool key_down(guint keycode, guint keyval, GdkModifierType state, std::optional<guint> layout);
    void key_up(guint keycode);
    void restore_keys();
    bool save_keys(const Keymap& before);
    // A row's message under its name (and its highlight), for a while.
    void note_key(int input, const std::string& text, const char* classes, bool flash, guint seconds);
    static gboolean on_key_pressed(GtkEventControllerKey* keys, guint keyval, guint keycode, GdkModifierType state,
                                   gpointer self);
    static void on_key_released(GtkEventControllerKey* keys, guint keyval, guint keycode, GdkModifierType state,
                                gpointer self);

    // ------------------------------------------------ task.cpp
    enum class Kind { kInstall, kUpdate, kImport, kRemove, kUninstall };
    struct Task {
        Kind kind;
        std::string title;
        std::string subject; // who it is for: "Kazumi Mishima", "3 characters"
        Progress progress{Progress::Kind::kBuild};
        std::shared_ptr<Process> process;
        bool cancelled = false;
        std::string error;                // from @error
        std::vector<std::string> added;   // @added, @removed: the fighters done
        std::vector<std::string> skipped; // @skipped: "<fighter>: <why>"
        std::function<void(Task&, int code)> ended; // before the task's result is shown
        bool shot_running = false;      // the test picture half-way is taken
    };
    void build_task_panel(GtkWidget* parent);
    bool start_task(Kind kind, std::string title, const std::vector<std::string>& argv,
                    const Process::Environment& environment, std::function<void(Task&, int)> ended);
    void begin_task(Kind kind, std::string title);
    void task_line(const std::string& line, bool error);
    void task_exited(int code);
    // The task's result in the panel: red unless ok or `cancelled`.
    void finish_task(bool ok, const std::string& result, const std::string& detail, bool cancelled = false);
    void show_task();
    void log(const std::string& line);
    void cancel_task();
    void close_task_panel();

    GtkApplication* app_;
    Options options_;
    Places places_ = Places::from_environment();
    fs::path kit_, importer_, python_;
    std::string kit_version_;

    Install install_;
    fs::path chosen_game_; // the .wua chosen (or given) last
    std::optional<Preflight> preflight_;
    fs::path installing_; // the folder the install that runs goes to
    std::shared_ptr<Process> game_process_;
    std::string game_error_; // why the game could not start, or stopped with an error
    guint game_watch_ = 0;   // looks whether a game started elsewhere still runs

    std::optional<ImporterStatus> status_;
    std::string status_error_;
    bool status_loading_ = false, status_again_ = false;
    std::chrono::steady_clock::time_point status_time_{};
    Owned owned_state_ = Owned::kUnknown; // asking Steam since it last started: not yet, under way, done, failed
    std::map<std::string, bool> owned_;   // its last answer: this time's, or the one kept from before
    bool owned_answer_ = false;           // owned_ holds one
    std::string owned_error_;             // why asking failed
    bool dlc_expanded_ = false;

    std::unique_ptr<Task> task_;
    bool quit_after_task_ = false;
    int result_serial_ = 0; // the result shown: a newer one keeps the panel open

    std::vector<TestAction> tests_;
    size_t next_test_ = 0;
    bool testing_ = false, test_running_ = false, test_reported_ = false;
    fs::path shots_;
    int shot_number_ = 0;
    bool screenshot_taken_ = false;
    GtkWidget* shot_window_ = nullptr; // a dialog the test's picture is of
    int frames_ = 0;                   // the window's first frames drawn
    bool settle_pending_ = false;

    Keymap keymap_;
    bool keys_as_shown_ = true; // keyboard.ini holds the keys shown (else a note says why not)
    int picking_ = -1;      // the input whose key is chosen
    guint modifier_ = 0;    // Ctrl, Shift or Alt pressed while choosing: taken once let go alone
    std::optional<Taken> taken_; // the last key taken or refused (tests)
    guint layout_ = 0;      // the keyboard layout the labels name
    std::set<guint> held_;  // the keys down (a key held repeats its press: not a new one)
    struct KeyRow {
        GtkWidget* row = nullptr;
        GtkWidget* button = nullptr;
        GtkWidget* face = nullptr;  // the button's: its key, or that it waits for one
        GtkWidget* label = nullptr; // the key
        GtkWidget* note = nullptr;
        int serial = 0; // of its message: a newer one is not hidden by an older one's time
    };
    std::array<KeyRow, kInputs> key_rows_{};
    GtkWidget* restore_button_ = nullptr;
    GtkWidget* keys_error_ = nullptr;
    GtkWidget* keys_note_ = nullptr; // why keyboard.ini is not what is shown

    GtkWidget* window_ = nullptr;
    GtkWidget* stack_ = nullptr;   // the main page, and Settings
    GtkWidget* content_ = nullptr; // what scrolls
    GtkWidget* settings_content_ = nullptr;
    GtkWidget* title_ = nullptr; // the header bar's
    GtkWidget* back_button_ = nullptr;
    GtkWidget* refresh_button_ = nullptr;
    GtkWidget* banner_icon_ = nullptr;
    GtkWidget* game_card_ = nullptr;
    GtkWidget* characters_card_ = nullptr;
    GtkWidget* task_revealer_ = nullptr;
    GtkWidget* task_title_ = nullptr;
    GtkWidget* task_detail_ = nullptr;
    GtkWidget* task_progress_ = nullptr;
    GtkWidget* task_button_ = nullptr;
    GtkWidget* task_spinner_ = nullptr;
    GtkWidget* log_expander_ = nullptr;
    GtkWidget* log_view_ = nullptr;
    GtkTextBuffer* log_buffer_ = nullptr;
    guint pulse_source_ = 0;
};

} // namespace launcher
