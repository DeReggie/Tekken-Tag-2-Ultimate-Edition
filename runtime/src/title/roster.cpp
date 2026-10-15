#include "title/roster.h"

#include "cafe/ppc_ops.h"
#include "cafe/runtime.h"
#include "cafe/sysmem.h"
#include "cafe/vfs.h"
#include "title/archive.h"

#include <zlib.h>

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace cafe::title {
namespace {

namespace fs = std::filesystem;

// ------------------------------------------------------------------ the title's tables (EU v16)

constexpr uint32_t kCodes = 0x107C57F4;       // 63 x char*: each fighter's three-letter code
constexpr uint32_t kRecords = 0x107B4220;     // 139 x 84 bytes: a fighter in one costume slot
constexpr uint32_t kRecordSize = 84;
constexpr uint32_t kRecordLists = 0x10873B78; // 63 x {list, count}: each fighter's records, built at start
constexpr uint32_t kRowRecords = 0x10873A68;  // 68 x the record of each motion row, built at start
constexpr uint32_t kMotionRows = 0x105A51C4;  // 68 x keys of {motion pack, moveset, movelist}
constexpr uint32_t kGrids = 0x1015F8E8;       // 6 x {cells, count}: the select screens' grids
constexpr uint32_t kGrid = 0x107B7668;        // grid 1, the one the title uses: 32-byte cells
constexpr uint32_t kSoundBanks[2] = {0x105C5084, 0x105C527C}; // 63 x a bank's key, by fighter
constexpr uint32_t kSpacerRight = 0x105314CC; // "spacer_right": the grille over the grid's right end
// Two more lists of every fighter's code, as string literals: the one the
// character loader's command `loadPlayer` searches (made by sub_065CCD24),
// and another of the loader's (sub_065C3128). The fighter's code in them.
constexpr uint32_t kCodeLiterals[] = {0x10492C54, 0x10492B44};
constexpr int kArchives = 56;                 // data000-data055, then the update's data100

// Record fields.
enum : uint32_t { kRecId = 0, kRecSlot = 4, kRecUiPosition = 8, kRecRow = 12, kRecSex = 16, kRecInit = 20, kRecInUse = 80 };
// Cell fields (s32): the fighter (63: random), the cells the cursor moves to, its place.
enum : uint32_t { kCellId = 0, kCellUp = 8, kCellDown = 12, kCellLeft = 16, kCellRight = 20, kCellColumn = 24, kCellRow = 28 };

// What the new fighter takes.
constexpr uint32_t kId = 61;         // ZAKO A's select id
constexpr uint32_t kRecord = 122;    // and 123: records the title skips
constexpr uint32_t kUiPosition = 59; // after the 59 fighters'
constexpr uint32_t kRow = 58;        // a motion row no record has
constexpr uint32_t kCell = 62;       // after grid 1's last cell: over the unused grid 2's first
// Its neighbours: Violet to the left, Unknown (round the end) to the right,
// Eddy below and Christie at the bottom (round the top).
constexpr uint32_t kLeftCell = 61, kRightCell = 46, kBelowCell = 19, kBottomCell = 42;
constexpr uint32_t kColumn = 19, kTopRow = 0;

// The files every fighter has, after its code. The title finds a fighter's
// body files (`<code>.xml` .. `<code>.havok.xml`) by keys compiled in for
// each code (sub_065C3128): the added fighter's are ZAKO A's. Its movelist,
// moveset and motions are found by the keys in its motion row, which name
// them after its own code.
constexpr const char* kSlotCode = "zka";
constexpr const char* kBodySuffixes[] = {".xml", ".nud", ".nut", ".bon", ".mop", ".havok.xml"};
constexpr const char* kMotionName = ".motion", *kMovesetName = ".moveset", *kMovelistName = ".mvl";
// The packs its item database takes costume parts from (attributes mi, ti,
// bi, pi), ZAKO A's (which has none in them): a part is the pack's key
// extended by its index. In a pack: `parts/<kind>/<index>.<extension>`.
struct PartPack {
    const char* kind;
    uint32_t key;
};
constexpr PartPack kPartPacks[] = {
    {"model", 0x07B445FE}, {"texture", 0x1A03559A}, {"bone", 0x5E56AF5F}, {"mop", 0xAF05D501}};

bool g_active = false;
uint32_t g_donor = 0; // the donor's select id

uint32_t load(uint32_t address) {
    uint32_t v;
    std::memcpy(&v, guest_pointer(address), 4);
    return __builtin_bswap32(v);
}
void store(uint32_t address, uint32_t value) {
    const uint32_t v = __builtin_bswap32(value);
    std::memcpy(guest_pointer(address), &v, 4);
}

// An entry's key: CRC-32 of its name, the register starting from zero.
uint32_t key_of(const std::string& name) {
    return static_cast<uint32_t>(crc32(0xFFFFFFFFul, reinterpret_cast<const Bytef*>(name.data()),
                                       static_cast<uInt>(name.size())));
}

// The key of member `index` of a pack: the CRC continued over the index's
// base-4 digits, least significant first, a byte each.
uint32_t member_key(uint32_t pack, uint32_t index) {
    uint8_t digits[16];
    uInt n = 0;
    for (; index != 0; index >>= 2) digits[n++] = static_cast<uint8_t>(index & 3);
    return n == 0 ? pack : static_cast<uint32_t>(crc32(pack, digits, n));
}

// The key of an entry a pack names by key (`keys/6ccdfc60.bin`: a changed
// copy of one of the title's own entries), if it is one.
std::optional<uint32_t> named_key(const std::string& path) {
    if (path.size() < 13 || path.compare(0, 5, "keys/") != 0) return std::nullopt;
    const std::string hex = path.substr(5, 8);
    if (hex.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos) return std::nullopt;
    return static_cast<uint32_t>(std::stoul(hex, nullptr, 16));
}

// A part's key from its path in a pack (`parts/model/7.nud`), if it is one.
std::optional<uint32_t> part_key(const std::string& path) {
    for (const PartPack& p : kPartPacks) {
        const std::string prefix = std::string("parts/") + p.kind + "/";
        if (path.compare(0, prefix.size(), prefix) != 0) continue;
        const std::string rest = path.substr(prefix.size());
        const size_t digits = rest.find_first_not_of("0123456789");
        if (digits == 0 || digits == std::string::npos || rest.find('/') != std::string::npos) return std::nullopt;
        return member_key(p.key, static_cast<uint32_t>(std::stoul(rest.substr(0, digits))));
    }
    return std::nullopt;
}

// ------------------------------------------------------------------ packs

struct Pack {
    fs::path directory;
    std::string code;  // three lower-case letters
    std::string donor; // a fighter's code
    bool female = true;
};

fs::path packs_directory() {
    if (const char* dir = std::getenv("TTT2_CHARACTERS"); dir && *dir) return dir;
    if (const char* data = std::getenv("XDG_DATA_HOME"); data && *data) return fs::path(data) / "ttt2/characters";
    const char* home = std::getenv("HOME");
    return fs::path(home ? home : ".") / ".local/share/ttt2/characters";
}

std::string trim(const std::string& s) {
    const size_t first = s.find_first_not_of(" \t\r");
    if (first == std::string::npos) return {};
    return s.substr(first, s.find_last_not_of(" \t\r") - first + 1);
}

std::optional<Pack> read_pack(const fs::path& directory) {
    std::ifstream in(directory / "character.ini");
    if (!in) return std::nullopt;
    Pack pack;
    pack.directory = directory;
    std::string line;
    while (std::getline(in, line)) {
        line = line.substr(0, line.find('#'));
        const size_t equals = line.find('=');
        if (equals == std::string::npos) continue;
        const std::string key = trim(line.substr(0, equals)), value = trim(line.substr(equals + 1));
        if (key == "code") pack.code = value;
        else if (key == "donor") pack.donor = value;
        else if (key == "sex") pack.female = value != "male";
    }
    const bool code_ok = pack.code.size() == 3 &&
                         std::all_of(pack.code.begin(), pack.code.end(), [](char c) { return c >= 'a' && c <= 'z'; });
    if (!code_ok || pack.donor.empty()) {
        std::fprintf(stderr, "ttt2: warning: %s needs a three-letter `code` and a `donor`; skipped\n",
                     (directory / "character.ini").c_str());
        return std::nullopt;
    }
    return pack;
}

// ------------------------------------------------------------------ the title's files

struct Located {
    std::string archive;
    archive::Entry entry;
};

// Every entry of the title's archives by key, as the title finds them: the
// last archive read (data100) wins.
std::map<uint32_t, Located> locate_entries() {
    std::map<uint32_t, Located> found;
    for (int i = 0; i <= kArchives; ++i) {
        char name[32];
        std::snprintf(name, sizeof name, "content/hdd/data%03d", i == kArchives ? 100 : i);
        const auto ofs = vfs::read_whole(std::string("/vol/") + name + ".ofs");
        const auto index = ofs ? archive::parse_index(*ofs) : std::nullopt;
        if (!index) continue;
        for (const archive::Entry& e : index->entries) found[e.hash] = Located{name, e};
    }
    return found;
}

std::optional<std::vector<uint8_t>> read_stored(const Located& at) {
    int32_t handle = 0;
    if (vfs::open_file("/vol/" + at.archive + ".bin", "r", handle) != vfs::kOk) return std::nullopt;
    std::vector<uint8_t> stored(at.entry.size);
    uint64_t transferred = 0;
    vfs::read_file(handle, stored.data(), stored.size(), archive::kPayload + at.entry.offset, transferred);
    vfs::close_file(handle);
    if (transferred != stored.size()) return std::nullopt;
    return stored;
}

std::optional<std::vector<uint8_t>> read_file(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return std::nullopt;
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(in), {});
}

// ------------------------------------------------------------------ the new fighter

// The select id of the fighter with `code`, if any.
std::optional<uint32_t> fighter_id(const std::string& code) {
    for (uint32_t id = 0; id < 63; ++id) {
        const char* name = reinterpret_cast<const char*>(guest_pointer(load(kCodes + 4 * id)));
        if (code == name) return id;
    }
    return std::nullopt;
}

uint32_t record_address(uint32_t record) { return kRecords + kRecordSize * record; }

// The motion row of a fighter's first costume slot.
std::optional<uint32_t> motion_row(uint32_t id) {
    for (uint32_t r = 0; r < 139; ++r) {
        if (load(record_address(r) + kRecId) == id && load(record_address(r) + kRecSlot) == 0 &&
            load(record_address(r) + kRecInUse) == 1) {
            return load(record_address(r) + kRecRow);
        }
    }
    return std::nullopt;
}

// The pack's files as archive entries, the donor's where the pack has none.
// Each is stored with the NRCZ flags of the donor's matching entry.
bool add_entries(const Pack& pack, uint32_t donor_row) {
    const auto located = locate_entries();
    auto donor_entry = [&](uint32_t key) -> std::optional<std::pair<std::vector<uint8_t>, std::array<uint8_t, 8>>> {
        const auto it = located.find(key);
        if (it == located.end()) return std::nullopt;
        auto stored = read_stored(it->second);
        if (!stored) return std::nullopt;
        std::array<uint8_t, 8> flags{};
        uint8_t raw[8];
        archive::stored_flags(*stored, key, raw);
        std::copy(std::begin(raw), std::end(raw), flags.begin());
        return std::make_pair(std::move(*stored), flags);
    };
    struct File {
        std::string name;   // in the pack
        uint32_t key;       // the entry's
        uint32_t donor_key; // its counterpart's
    };
    std::vector<File> files;
    for (const char* suffix : kBodySuffixes) {
        files.push_back({pack.code + suffix, key_of(std::string(kSlotCode) + suffix), key_of(pack.donor + suffix)});
    }
    files.push_back({pack.code + kMovelistName, key_of(pack.code + kMovelistName), key_of(pack.donor + kMovelistName)});
    files.push_back({pack.code + kMotionName, key_of(pack.code + kMotionName), load(kMotionRows + 12 * donor_row)});
    files.push_back({pack.code + kMovesetName, key_of(pack.code + kMovesetName), load(kMotionRows + 12 * donor_row + 4)});

    std::map<uint32_t, std::vector<uint8_t>> entries;
    size_t own = 0;
    for (const File& f : files) {
        const auto donor = donor_entry(f.donor_key);
        const uint32_t key = f.key;
        uint8_t flags[8] = {};
        if (donor) std::copy(donor->second.begin(), donor->second.end(), flags);
        if (const auto contents = read_file(pack.directory / f.name)) {
            entries[key] = archive::pack(*contents, key, flags);
            ++own;
        } else if (donor) {
            auto contents = archive::unpack(donor->first, f.donor_key);
            if (!contents) return false;
            entries[key] = archive::pack(*contents, key, flags);
        } else if (f.name != pack.code + ".mop" && f.name != pack.code + ".havok.xml") {
            std::fprintf(stderr, "ttt2: warning: neither %s nor its donor has %s\n", pack.directory.c_str(),
                         f.name.c_str());
            return false;
        }
    }
    // Costume parts, changed copies of the title's entries (`keys/`), and
    // anything else (effects: `<code>/alo/...`) as an entry named by its path.
    std::error_code ec;
    for (const auto& item : fs::recursive_directory_iterator(pack.directory, ec)) {
        if (!item.is_regular_file()) continue;
        const std::string name = fs::relative(item.path(), pack.directory).generic_string();
        const bool known = name == "character.ini" ||
                           std::any_of(files.begin(), files.end(), [&](const File& f) { return f.name == name; });
        if (known) continue;
        const auto contents = read_file(item.path());
        if (!contents) continue;
        const auto replaced = named_key(name);
        const uint32_t key = replaced ? *replaced : part_key(name).value_or(key_of(name));
        uint8_t flags[8] = {};
        if (replaced) {
            if (const auto original = donor_entry(key)) std::copy(original->second.begin(), original->second.end(), flags);
        }
        entries[key] = archive::pack(*contents, key, flags);
        ++own;
    }
    if (!vfs::set_archive_entries("content/hdd/data100", entries)) return false;
    if (std::getenv("TTT2_TRACE_ROSTER")) {
        std::fprintf(stderr, "ttt2: roster: %s (donor %s): %zu entries, %zu from the pack\n", pack.code.c_str(),
                     pack.donor.c_str(), entries.size(), own);
    }
    return true;
}

void patch_title(const Pack& pack, uint32_t donor) {
    // The fighter's code, in place of ZAKO A's (each code has four bytes).
    std::memcpy(guest_pointer(load(kCodes + 4 * kId)), pack.code.c_str(), 4);
    for (uint32_t literal : kCodeLiterals) {
        if (std::memcmp(guest_pointer(literal), "zka", 4) == 0) std::memcpy(guest_pointer(literal), pack.code.c_str(), 4);
    }
    // Its two costume slots.
    for (uint32_t slot = 0; slot < 2; ++slot) {
        const uint32_t at = record_address(kRecord + slot);
        std::memset(guest_pointer(at), 0, kRecordSize);
        store(at + kRecId, kId);
        store(at + kRecSlot, slot);
        store(at + kRecUiPosition, kUiPosition);
        store(at + kRecRow, kRow);
        store(at + kRecSex, pack.female ? 1 : 2);
        store(at + kRecInit, load(record_address(0) + kRecInit));
        store(at + kRecInUse, 1);
    }
    // Its moveset, motions and movelist.
    store(kMotionRows + 12 * kRow, key_of(pack.code + kMotionName));
    store(kMotionRows + 12 * kRow + 4, key_of(pack.code + kMovesetName));
    store(kMotionRows + 12 * kRow + 8, key_of(pack.code + kMovelistName));
    // A cell in the grid's top row, at the free place over Eddy.
    const uint32_t cell = kGrid + 32 * kCell;
    store(cell + kCellId, kId);
    store(cell + kCellUp, kBottomCell);
    store(cell + kCellDown, kBelowCell);
    store(cell + kCellLeft, kLeftCell);
    store(cell + kCellRight, kRightCell);
    store(cell + kCellColumn, kColumn);
    store(cell + kCellRow, kTopRow);
    store(kGrid + 32 * kLeftCell + kCellRight, kCell);
    store(kGrid + 32 * kRightCell + kCellLeft, kCell);
    store(kGrid + 32 * kBelowCell + kCellUp, kCell);
    store(kGrid + 32 * kBottomCell + kCellDown, kCell);
    store(kGrids + 8 * 1 + 4, kCell + 1);
    // The donor's sounds.
    for (uint32_t table : kSoundBanks) store(table + 4 * kId, load(table + 4 * donor));
}

} // namespace

void prepare_roster() {
    const fs::path directory = packs_directory();
    std::error_code ec;
    if (!fs::is_directory(directory, ec)) return;
    std::vector<fs::path> candidates;
    for (const auto& item : fs::directory_iterator(directory, ec)) {
        if (item.is_directory() && fs::is_regular_file(item.path() / "character.ini", ec)) {
            candidates.push_back(item.path());
        }
    }
    std::sort(candidates.begin(), candidates.end());
    for (const fs::path& candidate : candidates) {
        const auto pack = read_pack(candidate);
        if (!pack) continue;
        const auto donor = fighter_id(pack->donor);
        const auto donor_row = donor ? motion_row(*donor) : std::nullopt;
        if (!donor || *donor >= 59 || !donor_row) {
            std::fprintf(stderr, "ttt2: warning: %s: no fighter `%s` to borrow from; skipped\n", candidate.c_str(),
                         pack->donor.c_str());
            continue;
        }
        if (fighter_id(pack->code)) {
            std::fprintf(stderr, "ttt2: warning: %s: the code `%s` is a fighter's already; skipped\n",
                         candidate.c_str(), pack->code.c_str());
            continue;
        }
        if (!add_entries(*pack, *donor_row)) {
            std::fprintf(stderr, "ttt2: warning: %s could not be added\n", candidate.c_str());
            continue;
        }
        patch_title(*pack, *donor);
        g_active = true;
        g_donor = *donor;
        std::fprintf(stderr, "ttt2: added the fighter %s from %s\n", pack->code.c_str(), candidate.c_str());
        if (candidates.size() > 1) {
            std::fprintf(stderr, "ttt2: warning: the title has room for one added fighter; other packs ignored\n");
        }
        return;
    }
}

} // namespace cafe::title

using namespace cafe;
using namespace cafe::title;

// Builds each fighter's list of records and each motion row's record; the
// added fighter's two records are among the ones it skips.
PPC_FUNC(sub_033D512C_orig);
PPC_FUNC(sub_033D512C) {
    sub_033D512C_orig(ctx, base);
    if (!g_active) return;
    const uint32_t list = system_alloc(8);
    store(list, kRecord);
    store(list + 4, kRecord + 1);
    store(kRecordLists + 8 * kId, list);
    store(kRecordLists + 8 * kId + 4, 2);
    store(kRowRecords + 4 * kRow, kRecord);
}

// Whether a fighter can be picked; never for ids above 58.
PPC_FUNC(sub_033D52B4_orig);
PPC_FUNC(sub_033D52B4) {
    if (g_active && ctx.r[3] == kId) {
        ctx.r[3] = 1;
        return;
    }
    sub_033D52B4_orig(ctx, base);
}

// A fighter's voice and hit-sound banks: the added one has the donor's.
PPC_FUNC(sub_07A5CAC8_orig);
PPC_FUNC(sub_07A5CAC8) {
    if (g_active && ctx.r[3] == kId) ctx.r[3] = g_donor;
    sub_07A5CAC8_orig(ctx, base);
}
PPC_FUNC(sub_07A5CAA4_orig);
PPC_FUNC(sub_07A5CAA4) {
    if (g_active && ctx.r[4] == kId) ctx.r[4] = g_donor;
    sub_07A5CAA4_orig(ctx, base);
}

// Shows the select grid's portraits and the grilles over its empty ends;
// the right grille, which covers the added fighter's cell, is hidden again
// after every call.
PPC_FUNC(sub_06EF9C4C);
PPC_FUNC(sub_06F4D7B8_orig);
PPC_FUNC(sub_06F4D7B8) {
    const uint32_t ui = ctx.r[3];
    sub_06F4D7B8_orig(ctx, base);
    if (!g_active) return;
    ctx.r[3] = ui;
    ctx.r[4] = kSpacerRight;
    ctx.r[5] = 0;
    sub_06EF9C4C(ctx, base);
}
