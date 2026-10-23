// The launcher's logic without its window: the JSON reader, the progress
// lines, the install's state and folders, the PC checks' parsing, the test
// actions, and uninstalling (in a folder of its own, made and deleted here).

#include "json.h"
#include "paths.h"
#include "protocol.h"
#include "status.h"
#include "system.h"
#include "test_actions.h"
#include "uninstall.h"

#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <thread>

namespace {

using namespace launcher;

int g_failures = 0;

void check(bool ok, const std::string& what) {
    if (!ok) {
        std::printf("FAIL %s\n", what.c_str());
        ++g_failures;
    }
}

void write(const fs::path& file, const std::string& text) {
    std::error_code ec;
    fs::create_directories(file.parent_path(), ec);
    std::ofstream(file) << text;
}

bool there(const fs::path& path) {
    std::error_code ec;
    return fs::exists(fs::symlink_status(path, ec));
}

// A program that runs until it is killed, made at `program` as the game's
// program would be (a copy of sleep: a script would show as its shell in
// /proc/<pid>/exe). Its pid once it runs from there, or 0.
pid_t run_program(const fs::path& program) {
    std::error_code ec;
    fs::create_directories(program.parent_path(), ec);
    fs::copy_file("/bin/sleep", program, fs::copy_options::overwrite_existing, ec);
    fs::permissions(program, fs::perms::owner_all, ec);
    if (ec) return 0;
    const pid_t pid = ::fork();
    if (pid == 0) {
        // (argv[0] "sleep": a multi-call coreutils picks its tool by it.)
        ::execl(program.c_str(), "sleep", "60", static_cast<char*>(nullptr));
        ::_exit(127);
    }
    const std::string exe = "/proc/" + std::to_string(pid) + "/exe";
    for (int i = 0; i < 200; ++i) {
        if (fs::read_symlink(exe, ec) == program) return pid;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return pid;
}

void stop_program(pid_t pid) {
    if (pid <= 0) return;
    ::kill(pid, SIGKILL);
    ::waitpid(pid, nullptr, 0);
}

void test_json() {
    const auto doc = json::parse(R"( {"a": [1, -2.5e3, true, false, null], "s": "x\"\\\/\b\f\n\r\t\u00e9\ud83d\ude00",
                                     "o": {"k": "v"}, "a2": [], "o2": {}, "k": 1, "k": 2} )");
    check(doc.has_value(), "json: a valid document");
    if (!doc) return;
    const json::Value& d = *doc;
    check(d["a"].items().size() == 5, "json: array items");
    check(d["a"][0].number() == 1 && d["a"][1].number() == -2500, "json: numbers");
    check(d["a"][2].boolean() && !d["a"][3].boolean(true) && d["a"][4].is_null(), "json: literals");
    check(d["s"].string() == "x\"\\/\b\f\n\r\t\xC3\xA9\xF0\x9F\x98\x80", "json: escapes and UTF-16 pairs");
    check(d["o"]["k"].string() == "v", "json: nested object");
    check(d["a2"].is_array() && d["a2"].items().empty() && d["o2"].is_object(), "json: empty containers");
    check(d["k"].number() == 2, "json: the last of repeated members");
    check(d["missing"]["deeper"][3].string("fallback") == "fallback", "json: missing members give the fallback");
    check(d["a"].string("x") == "x" && d["s"].number(7) == 7 && d["s"].items().empty(), "json: wrong types too");
    check(json::parse("\"\\ud800\"")->string() == "\xEF\xBF\xBD", "json: a lone surrogate");
    check(json::parse("0")->number() == 0 && json::parse("-0.5")->number() == -0.5, "json: plain numbers");

    for (const char* bad : {"", "{", "[1,]", "{\"a\":1,}", "{\"a\" 1}", "\"open", "\"a\tb\"", "01", "1.", "1e",
                            "-", "nul", "[1] 2", "{1: 2}", "\"\\x\"", "\"\\u12G4\"", "+1", ".5", "1e999"}) {
        std::string error;
        check(!json::parse(bad, &error) && !error.empty(), std::string("json: rejects ") + bad);
    }
    check(!json::parse(std::string(100, '[') + std::string(100, ']')), "json: nesting too deep");
    check(json::parse(std::string(60, '[') + std::string(60, ']')).has_value(), "json: nesting within the limit");
}

void test_status() {
    const char* text = R"({"python": {"version": "3.14.0", "numpy": true, "pillow": false},
        "tools": {"gamescope": "/usr/bin/gamescope", "pactl": null, "helper": "prebuilt"},
        "steam": {"installed": true, "running": false},
        "tekken7": {"found": true, "path": "/s/steamapps/common/TEKKEN 7", "error": null},
        "packs_folder": "/d/ttt2/characters", "future": {"x": 1},
        "movesets": {"folder": "/m", "heihachi": false}, "game": {"path": null, "error": "not a game"},
        "fighters": [{"name": "kazumi", "display": "Kazumi Mishima", "dlc": null, "installed": true,
                      "moveset_saved": true},
                     {"name": "eliza", "display": "Eliza", "dlc": 592370, "installed": false, "moveset_saved": false},
                     {"name": "chloe", "display": "Lucky Chloe", "dlc": null, "installed": true, "outdated": true,
                      "moveset_saved": true},
                     {"name": "geese", "display": "Geese Howard", "dlc": 592373, "installed": true,
                      "outdated": false, "moveset_saved": false},
                     {"name": "noctis", "display": "Noctis", "dlc": 592374, "installed": false, "outdated": true},
                     {"name": "josie", "display": "Josie Rizal", "dlc": null, "installed": true, "outdated": false,
                      "newer": true},
                     {"name": "akuma", "display": "Akuma", "dlc": null, "installed": false, "newer": true},
                     {"display": "nameless"}]})";
    std::string error;
    const auto s = parse_status(text, &error);
    check(s.has_value(), "status: parses (" + error + ")");
    if (!s) return;
    check(s->python_version == "3.14.0" && s->numpy && !s->pillow, "status: python");
    check(s->gamescope == "/usr/bin/gamescope" && s->pactl.empty() && s->helper == "prebuilt", "status: tools");
    check(s->steam_installed && !s->steam_running, "status: steam");
    check(s->tekken7_usable() && s->tekken7_path == "/s/steamapps/common/TEKKEN 7", "status: tekken 7");
    check(s->packs_folder == "/d/ttt2/characters", "status: packs folder");
    check(!s->heihachi_saved && s->game_error == "not a game", "status: heihachi and the game");
    check(s->fighters.size() == 7, "status: fighters without a name are left out");
    if (s->fighters.size() == 7) {
        const Fighter &josie = s->fighters[5], &akuma = s->fighters[6];
        check(josie.installed && josie.newer && !josie.outdated && !josie.added(), "status: a newer pack is not added");
        check(!akuma.installed && !akuma.newer && !akuma.added(), "status: newer without a pack is not");
        check(!s->fighters[0].newer && !s->fighters[2].newer, "status: no \"newer\": not newer");
        const Fighter &kazumi = s->fighters[0], &eliza = s->fighters[1], &chloe = s->fighters[2],
                      &geese = s->fighters[3], &noctis = s->fighters[4];
        check(kazumi.name == "kazumi" && kazumi.dlc == 0 && kazumi.installed, "status: kazumi");
        check(!kazumi.outdated && kazumi.added(), "status: no \"outdated\": a pack the game loads");
        check(eliza.dlc == 592370 && !eliza.installed && !eliza.outdated && !eliza.added(), "status: eliza");
        check(chloe.installed && chloe.outdated && !chloe.added(), "status: an outdated pack is not in the game");
        check(geese.installed && !geese.outdated && geese.added(), "status: a current pack");
        check(!noctis.installed && !noctis.outdated && !noctis.added(), "status: outdated without a pack is not");
    }
    const auto missing =
        parse_status(R"({"tekken7": {"found": false, "path": null, "error": "Steam is not installed"}})");
    check(missing && !missing->tekken7_usable() && missing->tekken7_error == "Steam is not installed",
          "status: tekken 7 missing");
    check(missing && missing->heihachi_saved && missing->game_error.empty(), "status: optional fields' defaults");
    check(!parse_status("[1]") && !parse_status("not json"), "status: not an object");

    const Ownership owned = parse_owned(R"({"owned": {"eliza": true, "geese": false}})");
    check(owned.error.empty() && owned.owned.size() == 2 && owned.owned.at("eliza") && !owned.owned.at("geese"),
          "owned: answer");
    check(parse_owned(R"({"error": "Steam is not running"})").error == "Steam is not running", "owned: error");
    check(!parse_owned("garbage").error.empty() && !parse_owned("{}").error.empty(), "owned: malformed");
}

void test_saved_ownership(const fs::path& root) {
    const fs::path file = root / "cache/ttt2/dlc-owned.json";
    check(!saved_ownership(file), "saved owned: none at first");
    check(!save_ownership(file, R"({"error": "Steam is not running"})") && !there(file), "saved owned: not an error");
    check(save_ownership(file, R"({"owned": {"eliza": true, "geese": false}})"), "saved owned: saved");
    const auto saved = saved_ownership(file);
    check(saved && saved->owned.size() == 2 && saved->owned.at("eliza") && !saved->owned.at("geese"),
          "saved owned: read back");
    check(!there(fs::path(file.string() + ".part")), "saved owned: no part file left");
    write(file, "{\"owned\": ");
    check(!saved_ownership(file), "saved owned: a broken file is none");
}

void test_protocol() {
    Line l = parse_line("@step compile Compiling the game program\n");
    check(l.kind == Line::Kind::kStep && l.word == "compile" && l.text == "Compiling the game program", "line: step");
    l = parse_line("@progress 412 1203");
    check(l.kind == Line::Kind::kProgress && l.done == 412 && l.total == 1203, "line: progress");
    check(parse_line("@progress 4x 10").kind == Line::Kind::kText, "line: bad progress is text");
    l = parse_line("@folder /home/u/Games/Tekken Tag Tournament 2");
    check(l.kind == Line::Kind::kFolder && l.text == "/home/u/Games/Tekken Tag Tournament 2", "line: folder");
    l = parse_line("@error not enough free space");
    check(l.kind == Line::Kind::kError && l.text == "not enough free space", "line: error");
    check(parse_line("@done").kind == Line::Kind::kDone && parse_line("@ok").kind == Line::Kind::kOk, "line: done, ok");
    l = parse_line("@skipped geese its DLC is not owned");
    check(l.kind == Line::Kind::kSkipped && l.word == "geese" && l.text == "its DLC is not owned", "line: skipped");
    l = parse_line("@added kazumi");
    check(l.kind == Line::Kind::kAdded && l.word == "kazumi", "line: added");
    l = parse_line("@removed chloe");
    check(l.kind == Line::Kind::kRemoved && l.word == "chloe", "line: removed");
    l = parse_line("[ 12%] Building CXX object");
    check(l.kind == Line::Kind::kText && l.text == "[ 12%] Building CXX object", "line: text");
    check(parse_line("@unknown x").kind == Line::Kind::kText && parse_line("@done now").kind == Line::Kind::kText,
          "line: unknown words are text");

    Progress build(Progress::Kind::kBuild);
    check(build.fraction() < 0, "progress: unknown at first");
    build.feed(parse_line("@step check Checking the game"));
    check(build.fraction() == 0 && build.step() == "Checking the game", "progress: first step");
    build.feed(parse_line("@step compile"));
    const double compile_start = build.fraction();
    check(build.step() == "Compiling the game program" && compile_start > 0.05, "progress: compile, own text");
    build.feed(parse_line("@progress 500 1000"));
    check(build.fraction() > compile_start && build.detail() == "500 of 1,000 files", "progress: compile files");
    build.feed(parse_line("@step copy Copying the game"));
    build.feed(parse_line("@progress 4200000000 15900000000"));
    check(build.detail() == "4.2 of 15.9 GB", "progress: copy bytes (" + build.detail() + ")");
    const double copying = build.fraction();
    build.feed(parse_line("@step finish Finishing"));
    check(build.fraction() > copying && build.detail().empty(), "progress: finish");
    build.feed(parse_line("@done"));
    check(build.fraction() == 1, "progress: done");

    Progress import(Progress::Kind::kImport);
    import.set_names({{"kazumi", "Kazumi Mishima"}});
    import.feed(parse_line("@step dump Saving movesets"));
    check(import.fraction() < 0 && import.step() == "Saving movesets", "progress: dump has no fraction");
    import.feed(parse_line("@step fighter kazumi 1 2"));
    check(import.step() == "Adding Kazumi Mishima" && import.detail() == "1 of 2" && import.fraction() == 0,
          "progress: first fighter");
    import.feed(parse_line("@added kazumi"));
    check(std::fabs(import.fraction() - 0.475) < 1e-9, "progress: a fighter added");
    import.feed(parse_line("@step fighter chloe 2 2"));
    check(import.step() == "Adding chloe" && std::fabs(import.fraction() - 0.475) < 1e-9, "progress: second fighter");
    import.feed(parse_line("@step shared"));
    check(import.fraction() == 0.95, "progress: shared");

    check(thousands(0) == "0" && thousands(999) == "999" && thousands(1000) == "1,000" &&
              thousands(1234567) == "1,234,567",
          "thousands");
    check(gigabytes(15'900'000'000) == "15.9 GB", "gigabytes");
}

void test_paths(const fs::path& root) {
    // Menu entries as install.cpp writes them.
    auto program = desktop_program("[Desktop Entry]\nType=Application\nName=Tekken Tag Tournament 2\n"
                                   "Exec=\"/home/u/Games/Tekken Tag Tournament 2/Tekken Tag Tournament 2\"\n");
    check(program && *program == "/home/u/Games/Tekken Tag Tournament 2/Tekken Tag Tournament 2", "desktop: quoted");
    program = desktop_program("[Desktop Entry]\nExec=\"/a \\\\\"b\\\\\" 100%% \\\\$x\\\\\\\\y/p\" --flag\n");
    check(program && *program == "/a \"b\" 100% $x\\y/p", "desktop: escapes (" + program.value_or("").string() + ")");
    program = desktop_program("[Desktop Entry]\nExec=/usr/bin/ttt2 %f\n");
    check(program && *program == "/usr/bin/ttt2", "desktop: unquoted");
    check(!desktop_program("[Other]\nExec=/x\n") && !desktop_program("[Desktop Entry]\nName=x\n") &&
              !desktop_program("[Desktop Entry]\nExec=\"/open\n"),
          "desktop: no program");
    program = desktop_program("[Desktop Entry]\nExecutable=/no\nExec = /yes\n[Desktop Action x]\nExec=/action\n");
    check(program && *program == "/yes", "desktop: the main group's Exec key");

    check(inside("/a/b/c", "/a/b") && inside("/a/b", "/a/b/") && !inside("/a/bc", "/a/b") && !inside("/a", "/a/b"),
          "inside");
    check(normal("/a/./b/../c/") == "/a/c" && normal("/") == "/", "normal");

    // Where an install into a chosen folder goes.
    const fs::path games = root / "Games";
    fs::create_directories(games / "full");
    write(games / "full/other.txt", "x");
    fs::create_directories(games / "empty");
    write(games / "done/.ttt2-install", "x");
    check(install_target(games / "new") == games / "new", "target: a new folder");
    check(install_target(games / "empty") == games / "empty", "target: an empty folder");
    check(install_target(games / "done/") == games / "done", "target: an earlier install");
    check(install_target(games / "full") == games / "full" / kProgramName, "target: a folder in use gets one inside");
    write(games / "full" / kProgramName / "mine.txt", "x");
    std::string error;
    check(!install_target(games / "full", &error) &&
              error == "holds a \"Tekken Tag Tournament 2\" that is not an install of the game",
          "target: taken twice (" + error + ")");
    check(!install_target(games / "full/other.txt", &error) && error == "is not a folder", "target: a file");

    // The install's state.
    Places places;
    places.home = root / "home";
    places.config = root / "config";
    places.data = root / "data";
    check(find_install(places).state == InstallState::kNone, "state: nothing");
    write(places.record(), (games / "done").string() + "\n");
    Install install = find_install(places);
    check(install.state == InstallState::kInstalled && install.folder == games / "done", "state: installed");
    write(games / "half/.ttt2-installing", "x");
    check(write_started_record(places, games / "half", "/x/game.wua"), "state: started record");
    install = find_install(places);
    check(install.state == InstallState::kUnfinished && install.folder == games / "half" &&
              install.game == "/x/game.wua",
          "state: an unfinished install started by the launcher");
    write(games / "half/.ttt2-install", "x");
    check(find_install(places).folder == games / "done", "state: a finished one's start record is stale");
    fs::remove(places.started_record());
    write(games / "done/.ttt2-installing", "x");
    fs::remove(games / "done/.ttt2-install");
    install = find_install(places);
    check(install.state == InstallState::kUnfinished && install.folder == games / "done" && install.game.empty(),
          "state: an install over the recorded one stopped");

    write(root / "kit/VERSION", "0.3.0-abc1234\n");
    check(kit_version(root / "kit") == "0.3.0-abc1234" && kit_version(root / "nokit").empty(), "kit version");
    write(games / "done/.ttt2-build", "compiler clang++ 21\nkit 0.2.0-0000000\n");
    check(built_version(games / "done") == "0.2.0-0000000" && built_version(games / "new").empty(), "built version");
    check(find_in_path("sh").has_value() && !find_in_path("no-such-program-ttt2").has_value(), "find in PATH");
}

// The game's program running, as started from anywhere.
void test_running(const fs::path& root) {
    const fs::path folder = root / "disk/Tekken Tag Tournament 2";
    const fs::path program = folder / kProgramName;
    fs::create_directories(folder);
    check(!program_running(folder), "running: nothing runs");
    const pid_t pid = run_program(program);
    check(pid > 0 && program_running(folder), "running: the program");
    check(program_running(folder.string() + "/"), "running: the folder with a trailing slash");
    std::error_code ec;
    fs::create_directories(root / "Games");
    fs::create_directory_symlink(folder, root / "Games/TTT2", ec);
    check(program_running(root / "Games/TTT2"), "running: the folder through a link");
    check(!program_running(root / "disk"), "running: another folder's program");
    write(root / "disk/other/x", "x");
    check(!program_running(root / "disk/other"), "running: a folder without it");
    fs::remove(program);
    check(program_running(folder), "running: the program deleted while it runs");
    stop_program(pid);
    check(!program_running(folder), "running: it ended");
}

void test_system() {
    const auto none = missing_cpu_features("processor : 0\nflags : fpu sse2 cx16 lahf_lm popcnt pni ssse3 sse4_1 "
                                           "sse4_2 avx avx2 bmi1 bmi2 f16c fma abm movbe xsave\n");
    check(none.empty(), "cpu: x86-64-v3");
    const auto some = missing_cpu_features("flags\t\t: fpu sse2 cx16 lahf_lm popcnt pni ssse3 sse4_1 sse4_2 avx\n");
    check(some.size() == 8 && some[0] == "AVX2", "cpu: x86-64-v2 lacks AVX2 and more");
    check(missing_cpu_features("Features : fp asimd\n").size() == 16, "cpu: not x86");

    Distro d = parse_os_release("NAME=\"Example Linux\"\nID=example\nID_LIKE=arch\n");
    check(d.name == "Example Linux" && d.like.size() == 2 && d.like[1] == "arch", "os-release: like arch");
    check(install_command(d, {Package::kCompiler}) == "sudo pacman -S --needed clang", "command: arch");
    d = parse_os_release("ID=linuxmint\nID_LIKE=\"ubuntu debian\"\n");
    check(install_command(d, {Package::kNumpy, Package::kPillow}) == "sudo apt install python3-numpy python3-pil",
          "command: mint");
    d = parse_os_release("ID=\"opensuse-tumbleweed\"\nID_LIKE=\"opensuse suse\"\n");
    check(install_command(d, {Package::kPactl}) == "sudo zypper install pulseaudio-utils", "command: suse");
    d = parse_os_release("ID=fedora\n");
    check(install_command(d, {Package::kCompiler, Package::kCompiler}) == "sudo dnf install clang gcc-c++",
          "command: fedora");
    check(install_command(parse_os_release("ID=plan9\n"), {Package::kCompiler}).empty(), "command: unknown");

    // Systems whose own files come as one image.
    const auto image = [](const char* os_release, bool ostree = false) {
        Distro distro = parse_os_release(os_release);
        distro.ostree = ostree;
        return image_based(distro) && install_command(distro, {Package::kCompiler}).empty();
    };
    check(image("ID=steamos\nID_LIKE=arch\nVARIANT_ID=steamdeck\n"), "image: SteamOS");
    check(image("ID=fedora\nVARIANT_ID=silverblue\n") && image("ID=fedora\nVARIANT_ID=kinoite\n") &&
              image("ID=fedora\nVARIANT_ID=sericea\n") && image("ID=fedora\nVARIANT_ID=onyx\n") &&
              image("ID=fedora\nVARIANT_ID=atomic\n") && image("ID=fedora\nVARIANT_ID=iot\n") &&
              image("ID=fedora\nVARIANT_ID=coreos\n"),
          "image: Fedora's atomic variants");
    check(image("ID=fedora\nVARIANT_ID=cosmic-atomic\n", true), "image: any OSTree system");
    check(image("NAME=\"Bazzite\"\nID=bazzite\nID_LIKE=\"fedora\"\nVARIANT_ID=bazzite-deck\n"), "image: Bazzite");
    check(image("ID=\"opensuse-microos\"\nID_LIKE=\"suse opensuse opensuse-tumbleweed\"\n") &&
              image("ID=opensuse-tumbleweed\nID_LIKE=\"opensuse suse aeon\"\n") && image("ID=\"opensuse-kalpa\"\n"),
          "image: openSUSE MicroOS, Aeon, Kalpa");
    check(image("ID=nixos\n") && image("ID=guix\n"), "image: NixOS and Guix");
    check(!image_based(parse_os_release("ID=fedora\nVARIANT_ID=workstation\n")) &&
              !image_based(parse_os_release("ID=cachyos\nID_LIKE=arch\n")) &&
              !image_based(parse_os_release("ID=opensuse-tumbleweed\nID_LIKE=\"opensuse suse\"\n")) &&
              !image_based(parse_os_release("ID=ubuntu\nID_LIKE=debian\nVARIANT_ID=atomicish\n")),
          "image: package-managed systems are not");
    check(image_based_hint("a C++ compiler") ==
              "This system's own files cannot be changed with a package manager: a C++ compiler must come from a "
              "toolbox or distrobox container, or from the system's own way of adding software.",
          "image: the hint, as the builder's");

    check(run_output({"sh", "-c", "echo hello"}) == std::optional<std::string>("hello\n"), "run: output");
    check(!run_output({"sh", "-c", "exit 3"}) && !run_output({"no-such-program-ttt2"}), "run: failures");
}

// The compiler as the builder chooses it, with compilers that only say their
// version in a PATH of their own.
void test_compiler(const fs::path& root) {
    const auto compiler = [&](const char* name, const char* version) {
        const fs::path file = root / name;
        write(file, std::string("#!/bin/sh\necho ") + version + "\n");
        fs::permissions(file, fs::perms::owner_all);
    };
    const char* path = std::getenv("PATH");
    const char* cxx = std::getenv("CXX");
    const std::string saved_path = path ? path : "", saved_cxx = cxx ? cxx : "";
    ::unsetenv("CXX");
    ::setenv("PATH", root.c_str(), 1); // (not the PC's own compilers)
    std::string why;
    check(!find_compiler(&why) && why == "no C++ compiler is installed", "compiler: none");
    compiler("g++", "13.2.0");
    check(!find_compiler(&why) && why == "g++ 13.2.0 is too old (15 or newer is needed)", "compiler: GCC too old");
    compiler("clang++-12", "12.0.1");
    compiler("clang++-18", "18.1.3");
    const auto found = find_compiler();
    check(found && found->path == root / "clang++-18" && found->name == "clang++-18 18.1.3",
          "compiler: a versioned Clang, the newest that will do");
    ::setenv("PATH", saved_path.c_str(), 1);
    if (cxx) ::setenv("CXX", saved_cxx.c_str(), 1);
}

void test_actions() {
    std::string error;
    const auto actions = parse_test_actions(
        "install:/g/TEKKEN (EU).wua:/i/x ; update;add:kazumi, chloe;add-all-base;add-all-owned;remove:kazumi;"
        "uninstall:keep;uninstall:all;play;expand-dlc;expand-log;show-uninstall;wait:1.5;quit;focus:add:kazumi;"
        "refresh",
        &error);
    check(actions.has_value(), "actions: parse (" + error + ")");
    if (!actions) return;
    check(actions->size() == 16, "actions: count");
    check((*actions)[14].name == "focus" && (*actions)[14].args.size() == 1 && (*actions)[14].args[0] == "add:kazumi" &&
              (*actions)[14].label() == "focus-add_kazumi",
          "actions: focus");
    check((*actions)[15].name == "refresh" && (*actions)[15].args.empty(), "actions: refresh");
    check((*actions)[0].name == "install" && (*actions)[0].args.size() == 2 &&
              (*actions)[0].args[0] == "/g/TEKKEN (EU).wua" && (*actions)[0].args[1] == "/i/x",
          "actions: install");
    check((*actions)[0].label() == "install", "actions: no paths in labels");
    check((*actions)[2].args.size() == 2 && (*actions)[2].args[1] == "chloe" &&
              (*actions)[2].label() == "add-kazumi-chloe",
          "actions: add");
    check((*actions)[7].label() == "uninstall-all", "actions: uninstall label");
    const auto settings =
        parse_test_actions("settings; bind:face_bottom:38 ;bind:plus:9;reset-keys;back;bind:zl:64+23", &error);
    check(settings && settings->size() == 6, "actions: settings (" + error + ")");
    if (settings && settings->size() == 6) {
        const TestAction& chord = (*settings)[5];
        check(chord.args.size() == 2 && chord.args[1] == "64+23" && chord.label() == "bind-zl-64_23",
              "actions: bind, keys together");
        const TestAction& bind = (*settings)[1];
        check(bind.name == "bind" && bind.args.size() == 2 && bind.args[0] == "face_bottom" && bind.args[1] == "38" &&
                  bind.label() == "bind-face_bottom-38",
              "actions: bind");
        check((*settings)[0].name == "settings" && (*settings)[3].name == "reset-keys" && (*settings)[4].name == "back",
              "actions: settings, reset-keys, back");
    }
    for (const char* bad : {"install:/only", "uninstall:some", "add:", "dance", "play:now", "wait:x", "focus:", "focus",
                            "refresh:now", "bind", "bind:face_bottom", "bind:face_bottom:", "bind:nope:38",
                            "bind:face_bottom:x", "bind:face_bottom:0", "settings:now", "reset-keys:all",
                            "bind:zl:64+", "bind:zl:+64", "bind:zl:64++23", "bind:zl:64+x", "bind:zl:-1"}) {
        check(!parse_test_actions(bad), std::string("actions: rejects ") + bad);
    }
}

void test_uninstall(const fs::path& root) {
    Places places;
    places.home = root / "home";
    places.config = root / "config";
    places.data = root / "data";
    places.cache = root / "cache";
    places.saves = root / "home/.local/share/ttt2/save";
    places.packs = root / "data/ttt2/characters";
    places.tekken7_data = root / "home/.local/share/ttt2/tekken7";
    const fs::path folder = root / "Games/Tekken Tag Tournament 2";
    const fs::path outside = root / "outside";

    const auto make = [&] {
        write(folder / kProgramName, "program");
        write(folder / "icon.png", "png");
        write(folder / "game/code/Tekken.rpx", "rpx");
        write(folder / "game/content/hdd/data005.bin", "data");
        write(folder / "game/content/hdd/data006.bin.part", "half");
        write(folder / (std::string(kProgramName) + ".part"), "half");
        write(folder / (std::string(kBuildRecord) + ".part"), "half");
        write(folder / kMarker, "done");
        write(folder / kBuildRecord, "kit 1\n");
        write(folder / "my notes.txt", "keep me");
        fs::create_directories(folder / "icon.png.d");
        write(outside / "precious.txt", "keep me");
        std::error_code ec;
        fs::create_directory_symlink(outside, folder / "game/content/link", ec);
        fs::create_symlink(outside / "precious.txt", folder / "game/file-link", ec);
        write(places.desktop_entry(), "[Desktop Entry]\nExec=\"" + (folder / kProgramName).string() + "\"\n");
        write(places.record(), folder.string() + "\n");
        write(places.keyboard(), "face_top = 22\n");
        write(places.cache / "ttt2/pipelines.bin", "p");
        write(places.cache / "ttt2/spirv/1.spv", "s");
        write(places.cache / "ttt2/build/gen/a.cpp", "w");
        write(places.cache / "ttt2/tekken7/t7helper.exe", "h");
        write(places.home / ".cache/ttt2/tekken7/run/helper.log", "h"); // (an importer before $XDG_CACHE_HOME)
        write(places.owned_cache(), R"({"owned": {"eliza": true}})");
        write(places.saves / "80000001/save.dat", "save");
        write(places.saves / "common/x.dat", "save");
        write(places.packs / "kzm/character.ini", "pack");
        write(places.packs / "shared/x.bin", "shared");
        write(places.packs / "shared.part/keys/y.bin", "half"); // (an importer killed while it made shared/)
        write(places.packs / "shared.old/keys/z.bin", "old");
        // (An importer killed while it made a pack again: the new one, its
        // character.ini not written yet, and the earlier one.)
        write(places.packs / ".kzm.part/kzm.nud", "half");
        write(places.packs / ".dnc.old/dnc.nud", "old");
        write(places.packs / "notapack/readme.txt", "user");
        for (const char* name : {".kzm.tmp", ".kazumi.part", ".KZM.part", "kzm.part", ".kzm.part.bak", ".k.old"}) {
            write(places.packs / name / "readme.txt", "user");
        }
        write(places.tekken7_data / "movesets/T7_kazumi.tkmvst", "m");
    };
    make();

    UninstallReport r = uninstall(places, folder, {});
    check(r.refused.empty() && r.problems.empty(),
          "uninstall: ran (" + (r.problems.empty() ? r.refused : r.problems[0].text()) + ")");
    check(!r.folder_removed && r.left.size() == 2 && r.left[0] == "icon.png.d" && r.left[1] == "my notes.txt",
          "uninstall: the user's files are left");
    check(!there(folder / kProgramName) && !there(folder / "game") && !there(folder / kMarker) &&
              !there(folder / "icon.png") && !there(folder / kBuildRecord) &&
              !there(folder / (std::string(kProgramName) + ".part")) &&
              !there(folder / (std::string(kBuildRecord) + ".part")),
          "uninstall: the install's entries are gone");
    check(there(outside / "precious.txt") && there(outside), "uninstall: links are not followed");
    check(!there(places.desktop_entry()) && !there(places.record()), "uninstall: menu entry and record");
    check(!there(places.cache / "ttt2/pipelines.bin") && !there(places.cache / "ttt2/spirv") &&
              !there(places.cache / "ttt2/build") && !there(places.owned_cache()),
          "uninstall: shader caches, work folder and the DLC answer");
    check(there(places.saves / "80000001/save.dat") && there(places.packs / "kzm/character.ini") &&
              there(places.packs / ".kzm.part") && there(places.packs / ".dnc.old") &&
              there(places.tekken7_data) && there(places.cache / "ttt2/tekken7") &&
              there(places.home / ".cache/ttt2/tekken7"),
          "uninstall: saves and characters kept");
    check(there(places.keyboard()), "uninstall: the keyboard's keys kept (a setting)");

    // Everything, and a folder left empty goes too.
    fs::remove_all(folder);
    make();
    fs::remove(folder / "my notes.txt");
    fs::remove(folder / "icon.png.d");
    // A menu entry and record of another install stay.
    write(places.desktop_entry(), "[Desktop Entry]\nExec=\"/elsewhere/Tekken Tag Tournament 2\"\n");
    write(places.record(), "/elsewhere\n");
    r = uninstall(places, folder, {.saves = true, .characters = true});
    check(r.refused.empty() && r.problems.empty() && r.folder_removed && r.left.empty(), "uninstall all: ran");
    check(!there(folder) && there(outside / "precious.txt"), "uninstall all: the folder is gone, links not followed");
    check(there(places.desktop_entry()) && there(places.record()), "uninstall all: another install's entries stay");
    check(!there(places.saves) && !there(places.tekken7_data) && !there(places.cache / "ttt2") &&
              !there(places.home / ".cache/ttt2"),
          "uninstall all: data, the default save folder and both helper caches");
    check(!there(places.packs / "kzm") && !there(places.packs / "shared") && !there(places.packs / "shared.part") &&
              !there(places.packs / "shared.old") && there(places.packs / "notapack"),
          "uninstall all: only packs and what they share");
    check(!there(places.packs / ".kzm.part") && !there(places.packs / ".dnc.old"),
          "uninstall all: the packs a killed importer was making");
    for (const char* name : {".kzm.tmp", ".kazumi.part", ".KZM.part", "kzm.part", ".kzm.part.bak", ".k.old"}) {
        check(there(places.packs / name / "readme.txt"), std::string("uninstall all: not the importer's: ") + name);
    }
    check(there(places.keyboard()), "uninstall all: the keyboard's keys kept");

    // Not an install: nothing happens.
    write(root / "Games/other/file.txt", "x");
    r = uninstall(places, root / "Games/other", {});
    check(!r.refused.empty() && there(root / "Games/other/file.txt"), "uninstall: refuses a folder without markers");
    write(places.home / kMarker, "x");
    r = uninstall(places, places.home, {});
    check(!r.refused.empty(), "uninstall: refuses the home folder");
    check(!uninstall(places, "relative/folder", {}).refused.empty() && !uninstall(places, "/", {}).refused.empty(),
          "uninstall: refuses relative paths and the root");

    // A save folder of the player's ($TTT2_SAVE_DIR): only what the game
    // wrote goes, and the folder stays.
    const fs::path documents = root / "home/Documents";
    places.saves = documents;
    write(documents / "80000001/SAVE.DAT", "save");
    write(documents / "8000000a/SAVE.DAT", "save");
    write(documents / "common/x.dat", "save");
    write(documents / "notes.txt", "mine");
    write(documents / "8000000/mine.txt", "mine");
    write(documents / "8000000g/mine.txt", "mine");
    write(documents / "800000012/mine.txt", "mine");
    write(documents / "ABCDEF12", "a file of mine");
    write(outside / "common.txt", "mine");
    std::error_code ec;
    fs::create_directory_symlink(outside, documents / "12345678", ec);
    write(folder / kStarted, "x");
    r = uninstall(places, folder, {.saves = true});
    check(r.refused.empty() && r.problems.empty() && r.folder_removed, "uninstall saves: ran");
    check(!there(documents / "80000001") && !there(documents / "8000000a") && !there(documents / "common"),
          "uninstall saves: the game's");
    check(there(documents / "notes.txt") && there(documents / "8000000/mine.txt") &&
              there(documents / "8000000g/mine.txt") && there(documents / "800000012/mine.txt") &&
              there(documents / "ABCDEF12") && there(documents / "12345678") && there(outside / "common.txt"),
          "uninstall saves: nothing else");
    fs::remove_all(documents);
    fs::create_directories(documents / "80000001");
    write(folder / kStarted, "x");
    r = uninstall(places, folder, {.saves = true});
    check(r.problems.empty() && !there(documents / "80000001") && there(documents),
          "uninstall saves: the player's save folder stays when empty");

    places.saves = "";
    write(folder / kStarted, "x");
    r = uninstall(places, folder, {.saves = true});
    check(r.folder_removed && r.problems.size() == 1, "uninstall: no saves folder without its full path");
    places.saves = root / "home/.local/share/ttt2/save";

    // At the top of the folder only the install's own ".part" files go: a
    // download beside it, and lib/ (nothing makes it yet), are the user's.
    write(folder / kStarted, "x");
    write(folder / (std::string(kProgramName) + ".part"), "half");
    write(folder / "Movie.mkv.part", "a download");
    write(folder / "lib/libx.so", "theirs");
    r = uninstall(places, folder, {});
    check(r.problems.empty() && !r.folder_removed && r.left.size() == 2 && r.left[0] == "Movie.mkv.part" &&
              r.left[1] == "lib" && !there(folder / (std::string(kProgramName) + ".part")),
          "uninstall: other part files and lib/ stay");
    fs::remove_all(folder);

    // An install folder reached through a link: the folder and the link go.
    const fs::path real = root / "disk/TTT2", link = root / "Games/TTT2 link";
    fs::create_directories(real);
    fs::create_directory_symlink(real, link, ec);
    write(link / kProgramName, "program");
    write(link / "game/code/Tekken.rpx", "rpx");
    write(link / kMarker, "done");
    r = uninstall(places, link, {});
    check(r.refused.empty() && r.problems.empty() && r.folder_removed && !there(real) && !there(link),
          "uninstall: a linked folder (" + (r.problems.empty() ? r.refused : r.problems[0].text()) + ")");
    check(there(root / "disk") && there(root / "Games"), "uninstall: a linked folder's parents stay");

    // Not while the game runs from it: nothing is deleted.
    make();
    const pid_t pid = run_program(folder / kProgramName);
    r = uninstall(places, folder, {.saves = true, .characters = true});
    check(!r.refused.empty() && there(folder / "game/code/Tekken.rpx") && there(folder / kMarker) &&
              there(places.saves / "80000001/save.dat") && there(places.packs / "kzm/character.ini"),
          "uninstall: refused while the game runs (" + r.refused + ")");
    stop_program(pid);
    r = uninstall(places, folder, {});
    check(r.refused.empty() && !there(folder / "game"), "uninstall: once the game has ended");
}

} // namespace

int main(int argc, char** argv) {
    const fs::path base = fs::absolute(argc > 1 ? fs::path(argv[1]) : fs::temp_directory_path()).lexically_normal();
    fs::create_directories(base);
    std::string pattern = (base / "launcher_core_test.XXXXXX").string();
    if (!mkdtemp(pattern.data())) {
        std::printf("FAIL cannot make a folder in %s\n", base.c_str());
        return 1;
    }
    const fs::path root = pattern;
    test_json();
    test_status();
    test_protocol();
    test_saved_ownership(root / "owned");
    test_paths(root / "paths");
    test_running(root / "running");
    test_system();
    test_compiler(root / "compiler");
    test_actions();
    test_uninstall(root / "uninstall");
    std::error_code ec;
    fs::remove_all(root, ec);
    if (g_failures == 0) std::printf("launcher_core_test: all passed\n");
    return g_failures == 0 ? 0 : 1;
}
