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
constexpr uint32_t kIntroBanks[2] = {0x105C5084, 0x105C527C}; // 63 x the key of a fighter's rm_Dst bank
// 63 x the key of a fighter's rm_Dwi bank: the long win quote one win pose
// streams (sub_077CC6EC); a fighter with none (key 0) streams from a file
// with no name, which the title reports as an error (a pause).
constexpr uint32_t kWinStreams = 0x105C5180;
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

// A fighter's sound banks (NUS3BANKs, stored raw in the sound archives):
// shouts and damage voices `se_Chr_<code>`, win quotes `se_Dwi_<code>` and
// intro lines `rm_Dst_<code>`. The first two are found through bank ids
// (sub_07A5CAC8, sub_07A5CAA4) whose keys sub_07A5D01C gives; ids 122 and 233
// have no bank, so the added fighter's own banks take them. The third's key
// is in a table by fighter. A pack without a bank has the donor's.
constexpr const char* kVoiceBanks[] = {"se_Chr_", "se_Dwi_", "rm_Dst_", "rm_Dwi_"};
constexpr uint32_t kVoiceBankIds[2] = {122, 233};
constexpr const char* kSoundArchive = "content/hdd/data028";
// Moves play voices by sound id: a fighter's voice list (kVoiceLists, by
// select id, copied to the run-time lists by sub_0796F300 at start-up) holds
// the sound ids of its shouts and damage voices, and the sound table
// (sub_079E5B1C) gives each id's {tone, bank id, group, flags}. ZAKO A's list
// is a placeholder (Paul's tone 0), so the added fighter gets the donor's
// list, its ids pointing at copies of the donor's sound table entries that
// play the same tones of the added fighter's banks. New ids start above the
// ones sub_079E5CD0 remaps (0x213B-0x221D).
constexpr uint32_t kVoiceLists = 0x107D44EC;   // 63 x {u32 entries, u32 count, u32 fighter}; entry 16 B
constexpr uint32_t kItemSounds = 0x107D4044;   // 63 x {u32 sound ids, u32 count}
constexpr uint32_t kSoundTable = 0x107D4AC0;   // 8506 x {u32 tone, u32 bank id, u32 group, u32 flags}
constexpr uint32_t kSoundCount = 8506;
constexpr uint32_t kFirstNewSound = 0x221E;
constexpr uint32_t kChrBankIds = 0x105F2C7C;   // u8 se_Chr bank ids (sub_07A5CAC8's ranges)
constexpr uint32_t kDwiBankIds = 0x105F2C40;   // u8 se_Dwi bank ids by fighter (sub_07A5CAA4)
// A fighter's two name calls come from sub_079E5D64(id, kind) (-1 above 58):
// kind 0 its se_Chr bank's, kind 1 the select screen's from the shared bank
// se_Slt_StartChar, whose link tone `sel_syvo_name_<code>` plays the call. A
// pack adds the fighter's to a changed copy of that bank (keys/).
constexpr const char* kSelectBank = "se_Slt_StartChar.nus3bank";

// The archives whose entries are stored raw (no scrambling, no NRCZ): the
// sound banks and the movies.
bool raw_archive(const std::string& name) {
    const int n = std::atoi(name.c_str() + name.size() - 3);
    return (n >= 20 && n <= 24) || (n >= 27 && n <= 50);
}

// The index of the tone named `name` in a NUS3BANK (see
// tools/characters/ttt2char/ttt2/nus3bank.py), if any.
std::optional<uint32_t> tone_index(const std::vector<uint8_t>& bank, const std::string& name) {
    auto le32 = [&](size_t at) -> uint32_t {
        return at + 4 <= bank.size() ? uint32_t(bank[at]) | uint32_t(bank[at + 1]) << 8 | uint32_t(bank[at + 2]) << 16 |
                                           uint32_t(bank[at + 3]) << 24
                                     : 0;
    };
    if (bank.size() < 24 || std::memcmp(bank.data(), "NUS3", 4) != 0) return std::nullopt;
    const uint32_t chunks = le32(20);
    size_t at = 0x14 + le32(16);
    for (uint32_t c = 0; c < chunks && at + 8 <= bank.size(); ++c) {
        const uint32_t size = le32(at + 4);
        if (std::memcmp(&bank[at], "TONE", 4) == 0) {
            const size_t tone = at + 8;
            const uint32_t count = le32(tone);
            for (uint32_t i = 0; i < count; ++i) {
                const size_t entry = tone + le32(tone + 4 + 8 * i);
                if (le32(tone + 8 + 8 * i) <= 16 || entry + 16 > bank.size()) continue;
                const size_t length = entry + (bank[entry + 4] == 0x7F ? 8 : 12); // a link tone's header is shorter
                const size_t n = bank[length];
                if (n == name.size() + 1 && length + n <= bank.size() &&
                    std::memcmp(&bank[length + 1], name.data(), name.size()) == 0) {
                    return i;
                }
            }
            return std::nullopt;
        }
        at += 8 + size;
    }
    return std::nullopt;
}

bool g_active = false;
uint32_t g_donor = 0;                  // the donor's select id
uint32_t g_voice_keys[4] = {0, 0, 0, 0}; // the pack's own banks' keys (0: the donor's)
uint32_t g_sound_table = 0, g_sound_count = 0; // the extended sound table (0: the title's)
std::map<uint32_t, uint32_t> g_moved;  // the donor's sound ids -> the added fighter's copies
std::optional<uint32_t> g_name_tone;   // the select screen's call of its name: the tone in se_Slt_StartChar
uint32_t g_name_sound = 0;             // and its sound id (its entry is made on first use)
bool g_name_made = false;

uint32_t load(uint32_t address) {
    uint32_t v;
    std::memcpy(&v, guest_pointer(address), 4);
    return __builtin_bswap32(v);
}
void store(uint32_t address, uint32_t value) {
    const uint32_t v = __builtin_bswap32(value);
    std::memcpy(guest_pointer(address), &v, 4);
}
uint8_t load8(uint32_t address) { return *guest_pointer(address); }
void store8(uint32_t address, uint8_t value) { *guest_pointer(address) = value; }

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

// A texture container (NTP3: "NTP3", u16 version, u16 count at 6, then the
// textures from 16 on, each starting with its u32 total size) with the
// textures of `add`, another one, after its own. The 2D layouts take their
// texture pages from the container after them by id, so a pack adds pages to
// one instead of replacing all of it.
std::optional<std::vector<uint8_t>> with_textures(std::vector<uint8_t> nut, const std::vector<uint8_t>& add) {
    auto end_of = [](const std::vector<uint8_t>& d) -> std::optional<size_t> {
        if (d.size() < 16 || std::memcmp(d.data(), "NTP3", 4) != 0) return std::nullopt;
        size_t at = 16;
        for (uint32_t i = 0, n = uint32_t(d[6]) << 8 | d[7]; i < n; ++i) {
            if (at + 4 > d.size()) return std::nullopt;
            const uint32_t total = uint32_t(d[at]) << 24 | uint32_t(d[at + 1]) << 16 | uint32_t(d[at + 2]) << 8 | d[at + 3];
            if (total < 16 || at + total > d.size()) return std::nullopt;
            at += total;
        }
        return at;
    };
    const auto own = end_of(nut), added = end_of(add);
    if (!own || !added) return std::nullopt;
    const uint32_t count = (uint32_t(nut[6]) << 8 | nut[7]) + (uint32_t(add[6]) << 8 | add[7]);
    if (count > 0xFFFF) return std::nullopt;
    nut.insert(nut.begin() + static_cast<std::ptrdiff_t>(*own), add.begin() + 16, add.begin() + static_cast<std::ptrdiff_t>(*added));
    nut[6] = static_cast<uint8_t>(count >> 8);
    nut[7] = static_cast<uint8_t>(count);
    return nut;
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
    // Its own sound banks: raw entries of a sound archive.
    std::map<std::string, std::map<uint32_t, std::vector<uint8_t>>> raw; // archive -> raw entries
    std::vector<std::string> bank_files;
    for (size_t b = 0; b < std::size(kVoiceBanks); ++b) {
        const std::string name = std::string(kVoiceBanks[b]) + pack.code + ".nus3bank";
        auto contents = read_file(pack.directory / name);
        if (!contents || contents->size() < 4 || std::memcmp(contents->data(), "NUS3", 4) != 0) continue;
        g_voice_keys[b] = key_of(name);
        raw[kSoundArchive][g_voice_keys[b]] = std::move(*contents);
        bank_files.push_back(name);
        ++own;
    }
    // Costume parts, changed copies of the title's entries (`keys/`), and
    // anything else (effects: `<code>/alo/...`) as an entry named by its path.
    std::error_code ec;
    for (const auto& item : fs::recursive_directory_iterator(pack.directory, ec)) {
        if (!item.is_regular_file()) continue;
        const std::string name = fs::relative(item.path(), pack.directory).generic_string();
        const bool known = name == "character.ini" ||
                           std::any_of(files.begin(), files.end(), [&](const File& f) { return f.name == name; }) ||
                           std::find(bank_files.begin(), bank_files.end(), name) != bank_files.end();
        if (known) continue;
        auto contents = read_file(item.path());
        if (!contents) continue;
        const auto replaced = named_key(name);
        const uint32_t key = replaced ? *replaced : part_key(name).value_or(key_of(name));
        ++own;
        // Textures to add to one of the title's texture containers (`keys/<key>.add`, see with_textures).
        if (replaced && name.size() > 4 && name.compare(name.size() - 4, 4, ".add") == 0) {
            const auto original = donor_entry(key);
            auto unpacked = original ? archive::unpack(original->first, key) : std::nullopt;
            auto joined = unpacked ? with_textures(std::move(*unpacked), *contents) : std::nullopt;
            if (!joined) {
                std::fprintf(stderr, "ttt2: warning: %s: %s does not fit the title's entry; left out\n",
                             pack.directory.c_str(), name.c_str());
                continue;
            }
            uint8_t flags[8];
            std::copy(original->second.begin(), original->second.end(), flags);
            entries[key] = archive::pack(*joined, key, flags);
            continue;
        }
        // A changed copy of a raw entry (a sound bank) stays raw, in the original's archive.
        const auto original = replaced ? located.find(key) : located.end();
        if (original != located.end() && raw_archive(original->second.archive)) {
            if (key == key_of(kSelectBank)) g_name_tone = tone_index(*contents, "sel_syvo_name_" + pack.code);
            raw[original->second.archive][key] = *contents;
            continue;
        }
        uint8_t flags[8] = {};
        if (replaced) {
            if (const auto donor = donor_entry(key)) std::copy(donor->second.begin(), donor->second.end(), flags);
        }
        entries[key] = archive::pack(*contents, key, flags);
    }
    if (!vfs::set_archive_entries("content/hdd/data100", entries)) return false;
    for (auto& [name, map] : raw) {
        if (vfs::set_archive_entries(name, map)) continue;
        std::fprintf(stderr, "ttt2: warning: %s: its entries of %s could not be added\n", pack.directory.c_str(),
                     name.c_str());
        if (name == kSoundArchive) std::fill(std::begin(g_voice_keys), std::end(g_voice_keys), 0u);
        g_name_tone.reset();
    }
    if (std::getenv("TTT2_TRACE_ROSTER")) {
        std::fprintf(stderr, "ttt2: roster: %s (donor %s): %zu entries, %zu from the pack\n", pack.code.c_str(),
                     pack.donor.c_str(), entries.size(), own);
    }
    return true;
}

// The se_Chr bank id of fighter `id` (what sub_07A5CAC8 computes).
uint32_t chr_bank(uint32_t id) {
    const uint32_t index = id <= 17 ? id : id <= 44 ? id + 1 : id + 3;
    return *reinterpret_cast<const uint8_t*>(guest_pointer(kChrBankIds + index));
}

// The added fighter's voice list and item sounds: the donor's, pointing at
// the added fighter's own banks where the pack has them (see kVoiceLists).
void patch_voice(uint32_t donor) {
    std::vector<uint32_t> extra; // the donor's sound ids copied onto the added fighter's banks
    const uint32_t banks[2][2] = {{chr_bank(donor), kVoiceBankIds[0]},
                                  {*reinterpret_cast<const uint8_t*>(guest_pointer(kDwiBankIds + donor)),
                                   kVoiceBankIds[1]}};
    for (uint32_t sid = 0; sid < kSoundCount; ++sid) {
        const uint32_t bank = load(kSoundTable + 16 * sid + 4);
        for (int b = 0; b < 2; ++b) {
            if (g_voice_keys[b] && bank == banks[b][0]) extra.push_back(sid);
        }
    }
    if (!extra.empty() || g_name_tone) {
        g_sound_count = kFirstNewSound + static_cast<uint32_t>(extra.size()) + (g_name_tone ? 1 : 0);
        g_sound_table = system_alloc(16 * g_sound_count);
        std::memset(guest_pointer(g_sound_table), 0, 16 * g_sound_count);
        std::memcpy(guest_pointer(g_sound_table), guest_pointer(kSoundTable), 16 * kSoundCount);
        for (size_t k = 0; k < extra.size(); ++k) {
            const uint32_t to = g_sound_table + 16 * (kFirstNewSound + static_cast<uint32_t>(k));
            std::memcpy(guest_pointer(to), guest_pointer(kSoundTable + 16 * extra[k]), 16);
            store(to + 4, load(to + 4) == banks[0][0] && g_voice_keys[0] ? banks[0][1] : banks[1][1]);
            g_moved[extra[k]] = kFirstNewSound + static_cast<uint32_t>(k);
        }
        if (g_name_tone) g_name_sound = g_sound_count - 1;
    }
    auto moved_id = [&](uint32_t sid) {
        const auto it = g_moved.find(sid);
        return it == g_moved.end() ? sid : it->second;
    };
    // The voice list.
    const uint32_t from = kVoiceLists + 12 * donor, to = kVoiceLists + 12 * kId;
    const uint32_t count = load(from + 4);
    const uint32_t entries = system_alloc(16 * std::max(count, 1u));
    std::memcpy(guest_pointer(entries), guest_pointer(load(from)), 16 * count);
    for (uint32_t k = 0; k < count; ++k) store(entries + 16 * k + 4, moved_id(load(entries + 16 * k + 4)));
    store(to, entries);
    store(to + 4, count);
    store(to + 8, kId);
    // The item sounds.
    const uint32_t items = load(kItemSounds + 8 * donor + 4);
    if (items != 0) {
        const uint32_t ids = system_alloc(4 * items);
        for (uint32_t k = 0; k < items; ++k) store(ids + 4 * k, moved_id(load(load(kItemSounds + 8 * donor) + 4 * k)));
        store(kItemSounds + 8 * kId, ids);
        store(kItemSounds + 8 * kId + 4, items);
    }
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
    // Its intro lines and its streamed win quote: its own or the donor's.
    for (uint32_t table : kIntroBanks) store(table + 4 * kId, g_voice_keys[2] ? g_voice_keys[2] : load(table + 4 * donor));
    store(kWinStreams + 4 * kId, g_voice_keys[3] ? g_voice_keys[3] : load(kWinStreams + 4 * donor));
    patch_voice(donor);
}

// ------------------------------------------------------------------ art

// The added fighter's pictures and names on the 2D screens. Their code finds
// a fighter's pictures by its UI position, its row in tables of 59, from the
// select id (sub_06F0A484 -> sub_033D5524: the first record with the id,
// ZAKO A's own record 120: UI position 0, Paul's) or from the record
// (sub_06F0A4A4 -> sub_033D555C: record 122's 59, which this code takes for
// "nobody"). The added fighter has no row of its own, so it gets Paul's from
// both, and while the code works on it Paul's row of every table holds the
// added fighter's entries (show_added): the labels of its pictures in the
// layouts (the pack's changed layouts have `chara_face_yoko_kzm` beside
// `chara_face_yoko_pau`), the keys of its textures, its frames of the big
// select portraits. The functions that ask for UI positions put Paul's row
// back when they return. A pack has pictures if it has a folder `art/`.

// Tables of label names (char*) by UI position, `per` entries a fighter.
struct LabelTable {
    uint32_t address, per;
};
constexpr LabelTable kLabelTables[] = {
    {0x107D1114, 1}, // chara_face_<code> (loading screen)
    {0x107D1200, 1}, // chara_name_s_<code>
    {0x107D159C, 1}, // face_<code>
    {0x107B2130, 2}, // face_p1_<code>, face_p2_<code> (select screen thumbnails)
};
// Label names as the title's string objects, built at start-up, by UI
// position: 32 bytes, the text at +4 while the capacity (+28) is under 16,
// else at the pointer at +20; the length at +24.
struct StringArray {
    uint32_t address, stride, per;
};
constexpr StringArray kLabelStrings[] = {
    {0x108EC990, 32, 1}, // chara_face_yoko_<code> (select screen, the bars of the team)
    {0x108ED0F0, 64, 2}, // p1_chara_waku_<code>, p2_chara_waku_<code> (select screen, the name over the portrait)
    {0x108E8B50, 64, 2}, // the same (loading and VS screens)
};
constexpr uint32_t kStringSize = 32, kStringText = 4, kStringPointer = 20, kStringLength = 24, kStringCapacity = 28;
// Keys of portrait textures by UI position (8 bytes a fighter: player 1's
// and 2's, or one and 0), and the pack's file that replaces Paul's.
struct KeyTable {
    uint32_t address;
    const char* file;
};
constexpr KeyTable kKeyTables[] = {
    {0x10529004, "art/portrait_1p.nut"},    // loading and VS screens, red frame
    {0x10529008, "art/portrait_2p.nut"},    // blue frame
    {0x105291DC, "art/portrait_mono.nut"},  // black and white (sub_06F033B0's other kinds)
    {0x105293B4, "art/portrait_green.nut"}, // green frame
    {0x1052958C, "art/portrait_green2.nut"},
};
// The labels of the select screen's strip (`face_<code>`) by select id: 63
// records of 20 bytes, the last four empty.
constexpr uint32_t kProfiles = 0x107B078C, kProfileSize = 20;
// The big select portraits: container 6ccdfc60, two frames a UI position
// (player 1, 2; a pack's copy has the added fighter's two after the 118),
// which sub_06F0449C lists for each player, by UI position, in two vectors
// of its object ({+4 first, +8 end}, at +4 and +20; the resources at +36).
constexpr uint32_t kPortraits = 0x6CCDFC60, kPortraitFrames = 118;
constexpr uint32_t kPortraitLists[2] = {4 + 4, 20 + 4}, kPortraitResources = 36;

struct Swap {
    uint32_t address;
    std::vector<uint8_t> ours;   // the added fighter's
    std::vector<uint8_t> theirs; // what they replaced
};
bool g_art = false;    // the pack has pictures
bool g_hud = false;    // the pack has the HUD's pictures (kHud)
bool g_shown = false;  // Paul's rows hold the added fighter's entries
std::vector<Swap> g_swaps;
bool g_swaps_made = false;
std::string g_code;    // the added fighter's
fs::path g_pack;       // its pack
// The big portraits' object as last listed, and per player {Paul's frame, the added fighter's}.
uint32_t g_portrait_owner = 0;
uint32_t g_portrait_frames[2][2] = {};

uint32_t guest_string(const std::string& text) {
    const uint32_t at = system_alloc(static_cast<uint32_t>(text.size()) + 1);
    std::memcpy(guest_pointer(at), text.c_str(), text.size() + 1);
    return at;
}

// A label of Paul's with the added fighter's code: "face_pau_lose" -> "face_kzm_lose".
std::string with_code(std::string label) {
    const std::string paul = reinterpret_cast<const char*>(guest_pointer(load(kCodes)));
    for (size_t at = label.find(paul); at != std::string::npos; at = label.find(paul, at + 1)) {
        const size_t end = at + paul.size();
        if ((at == 0 || label[at - 1] == '_') && (end == label.size() || label[end] == '_')) {
            return label.replace(at, paul.size(), g_code);
        }
    }
    return label;
}

// Paul's rows, and what replaces them: made on first use, when the title has
// built its string objects.
void make_swaps() {
    g_swaps_made = true;
    auto be = [](uint32_t value) {
        std::vector<uint8_t> v(4);
        const uint32_t b = __builtin_bswap32(value);
        std::memcpy(v.data(), &b, 4);
        return v;
    };
    for (const LabelTable& t : kLabelTables) {
        for (uint32_t k = 0; k < t.per; ++k) {
            const uint32_t at = t.address + 4 * k;
            const std::string paul = reinterpret_cast<const char*>(guest_pointer(load(at)));
            g_swaps.push_back({at, be(guest_string(with_code(paul))), {}});
        }
    }
    for (const StringArray& a : kLabelStrings) {
        for (uint32_t k = 0; k < a.per; ++k) {
            const uint32_t at = a.address + kStringSize * k;
            const bool inline_text = load(at + kStringCapacity) < 16;
            const uint32_t text = inline_text ? at + kStringText : load(at + kStringPointer);
            const std::string label = with_code(reinterpret_cast<const char*>(guest_pointer(text)));
            std::vector<uint8_t> object(guest_pointer(at), guest_pointer(at) + kStringSize);
            auto put = [&](uint32_t offset, uint32_t value) {
                const uint32_t b = __builtin_bswap32(value);
                std::memcpy(&object[offset], &b, 4);
            };
            const uint32_t length = static_cast<uint32_t>(label.size());
            put(kStringPointer, guest_string(label));
            put(kStringLength, length);
            put(kStringCapacity, std::max<uint32_t>(length, 16)); // the text at the pointer
            g_swaps.push_back({at, std::move(object), {}});
        }
    }
    std::error_code ec;
    for (const KeyTable& t : kKeyTables) {
        if (fs::is_regular_file(g_pack / t.file, ec)) g_swaps.push_back({t.address, be(key_of(t.file)), {}});
    }
}

// Paul's rows hold the added fighter's entries (on) or Paul's (off).
void show_added(bool on) {
    if (!g_art || on == g_shown) return;
    if (on && !g_swaps_made) make_swaps();
    for (Swap& s : g_swaps) {
        uint8_t* at = guest_pointer(s.address);
        if (on) {
            s.theirs.assign(at, at + s.ours.size());
            std::memcpy(at, s.ours.data(), s.ours.size());
        } else {
            std::memcpy(at, s.theirs.data(), s.theirs.size());
        }
    }
    g_shown = on;
}

void prepare_art(const Pack& pack) {
    std::error_code ec;
    if (!fs::is_directory(pack.directory / "art", ec)) return;
    g_art = true;
    g_code = pack.code;
    g_pack = pack.directory;
    store(kProfiles + kProfileSize * kId, guest_string("face_" + pack.code));
    g_hud = fs::is_regular_file(pack.directory / "keys" / "7c476bde.add", ec);
}

// ------------------------------------------------------------------ costume chooser

// The select screen's costume chooser (CHANGE COSTUME) lists a fighter's
// costumes (sub_0580D690, from rows {entries, count} at kCostumeLists by
// select id: 59 rows, none for the added fighter) with a picture each, from a
// texture container whose key is in kCostumePreviews (59 keys by select id;
// the added fighter's place is past the table, in a string the title does
// not read there), then five customisation slots. The added fighter has one
// costume: its list is the donor's first costume (costume 1), its pictures
// the pack's (kCostumeFile, else the donor's), its key lent to the table's
// place only while the chooser's functions run, and the chooser leaves out
// the customisation slots (customisation is made per fighter in a mode the
// added fighter is not in; loading a slot's items would read past tables).
constexpr uint32_t kCostumeLists = 0x103B4B84, kCostumePreviews = 0x10161590;
constexpr const char* kCostumeFile = "art/costumes.nut";
constexpr uint32_t kCostumeOne = 0;                          // the type of costume 1 in a list
constexpr uint32_t kChooserPending = 324, kChooserCount = 88, kChooserEntries = 92, kChooserEntrySize = 16;
constexpr uint32_t kChooserSlot = 5;                         // an entry's kind: a customisation slot
uint32_t g_costume_entries = 0; // the added fighter's list: one entry {type, u16 value, u16 0}
uint32_t g_costume_key = 0;     // the key of its pictures

void prepare_costumes(const Pack& pack, uint32_t donor) {
    std::error_code ec;
    g_costume_key = fs::is_regular_file(pack.directory / kCostumeFile, ec) ? key_of(kCostumeFile)
                                                                          : load(kCostumePreviews + 4 * donor);
    // the donor's costume 1 (its first entry of that type), else a costume 1 of no value
    const uint32_t entries = load(kCostumeLists + 8 * donor), count = load(kCostumeLists + 8 * donor + 4);
    g_costume_entries = system_alloc(8);
    store(g_costume_entries, kCostumeOne);
    store(g_costume_entries + 4, 0);
    for (uint32_t i = 0; i < count; ++i) {
        if (load(entries + 8 * i) == kCostumeOne) {
            store(g_costume_entries + 4, load(entries + 8 * i + 4));
            break;
        }
    }
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
        prepare_art(*pack);
        prepare_costumes(*pack, *donor);
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

// A fighter's bank ids: shouts (se_Chr) and win quotes (sub_07A5CAA4(2, id):
// se_Dwi). The added fighter's own banks, else the donor's.
PPC_FUNC(sub_07A5CAC8_orig);
PPC_FUNC(sub_07A5CAC8) {
    if (g_active && ctx.r[3] == kId) {
        if (g_voice_keys[0]) {
            ctx.r[3] = kVoiceBankIds[0];
            return;
        }
        ctx.r[3] = g_donor;
    }
    sub_07A5CAC8_orig(ctx, base);
}
PPC_FUNC(sub_07A5CAA4_orig);
PPC_FUNC(sub_07A5CAA4) {
    if (g_active && ctx.r[4] == kId) {
        if (ctx.r[3] == 2 && g_voice_keys[1]) {
            ctx.r[3] = kVoiceBankIds[1];
            return;
        }
        ctx.r[4] = g_donor;
    }
    sub_07A5CAA4_orig(ctx, base);
}
// The sound table (and its count): the extended one when the added fighter
// has banks of its own.
PPC_FUNC(sub_079E5B1C_orig);
PPC_FUNC(sub_079E5B1C) {
    if (g_sound_table == 0) {
        sub_079E5B1C_orig(ctx, base);
        return;
    }
    if (ctx.r[3] != 0) store(ctx.r[3], g_sound_count);
    ctx.r[3] = g_sound_table;
}

// A fighter's name calls (see kSelectBank): the added fighter's are the
// donor's moved to its own se_Chr bank, and the select screen's call its own
// tone in the changed se_Slt_StartChar, or none (not the donor's name).
PPC_FUNC(sub_079E5D64_orig);
PPC_FUNC(sub_079E5D64) {
    if (!g_active || ctx.r[3] != kId) {
        sub_079E5D64_orig(ctx, base);
        return;
    }
    const uint32_t kind = ctx.r[4];
    ctx.r[3] = g_donor;
    sub_079E5D64_orig(ctx, base);
    const uint32_t sid = ctx.r[3];
    if (sid == 0xFFFFFFFF) return;
    if (kind == 0) {
        const auto it = g_moved.find(sid);
        if (it != g_moved.end()) ctx.r[3] = it->second;
        return;
    }
    if (g_name_sound == 0) {
        ctx.r[3] = 0xFFFFFFFF;
        return;
    }
    if (!g_name_made && sid < kSoundCount) {
        // the donor's call's entry (bank, group, flags) with the added fighter's tone
        std::memcpy(guest_pointer(g_sound_table + 16 * g_name_sound), guest_pointer(kSoundTable + 16 * sid), 16);
        store(g_sound_table + 16 * g_name_sound, *g_name_tone);
        g_name_made = true;
    }
    ctx.r[3] = g_name_made ? g_name_sound : 0xFFFFFFFF;
}

// A bank id's key.
PPC_FUNC(sub_07A5D01C_orig);
PPC_FUNC(sub_07A5D01C) {
    if (g_active) {
        for (size_t b = 0; b < std::size(kVoiceBankIds); ++b) {
            if (ctx.r[3] == kVoiceBankIds[b] && g_voice_keys[b]) {
                ctx.r[3] = g_voice_keys[b];
                return;
            }
        }
    }
    sub_07A5D01C_orig(ctx, base);
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

// ------------------------------------------------------------------ art (see show_added)

// The select screen's cursors (sub_06F4C480, r19 the player, r30 its object)
// ask for both team members' UI positions first and set their pictures
// after, so Paul's rows cannot follow one question: each member's pictures
// show the added fighter's entries if its question was about the added
// fighter (by the call sites of the questions and of the jumps to labels).
// A member's pictures change only when its UI position does (kept at +172,
// +188 for the first member, +180, +196 for the second): moving between
// Paul and the added fighter, both 0, resets them to 59 ("nobody").
struct SelectSite {
    uint32_t lr;
    uint32_t member;
};
constexpr SelectSite kSelectQueries[] = {
    {0x06F4CE0C, 0}, {0x06F4CE2C, 0}, {0x06F4CEC4, 0}, {0x06F4CF00, 0},
    {0x06F4CE4C, 1}, {0x06F4CE70, 1}, {0x06F4CED0, 1}, {0x06F4CF40, 1},
};
constexpr SelectSite kSelectLabels[] = {
    {0x06F4D068, 0}, {0x06F4D150, 0}, {0x06F4D290, 0}, // chara_face_yoko, p<n>_chara_waku (main)
    {0x06F4D0B4, 1}, {0x06F4D430, 1},                  // chara_face_yoko, p<n>_chara_waku (sub)
};
constexpr uint32_t kSelectPositions[2][2] = {{172, 188}, {180, 196}};
constexpr uint32_t kNobody = 59;
bool g_select_added[2][2] = {};

void note_select_question(uint32_t lr, const PPCContext& ctx, bool added) {
    for (const SelectSite& s : kSelectQueries) {
        if (s.lr != lr) continue;
        const uint32_t player = ctx.r[19] & 1;
        bool& member = g_select_added[player][s.member];
        if (member != added) {
            for (uint32_t offset : kSelectPositions[s.member]) store(ctx.r[30] + offset + 4 * player, kNobody);
            member = added;
        }
        return;
    }
}

// A fighter's UI position from its select id, for the 2D screens: the added
// fighter's is Paul's (record 120's), with its entries in Paul's rows.
PPC_FUNC(sub_06F0A484_orig);
PPC_FUNC(sub_06F0A484) {
    const bool added = g_art && ctx.r[3] == kId;
    const uint32_t lr = ctx.lr;
    sub_06F0A484_orig(ctx, base);
    show_added(added);
    if (g_art) note_select_question(lr, ctx, added);
}

// A fighter's UI position from a record: Paul's, not 59 ("nobody"), for the
// added fighter's records, with its entries in Paul's rows.
PPC_FUNC(sub_06F0A4A4_orig);
PPC_FUNC(sub_06F0A4A4) {
    const uint32_t lr = ctx.lr;
    const bool added = g_art && (ctx.r[3] == kRecord || ctx.r[3] == kRecord + 1);
    if (added) {
        ctx.r[3] = 0;
    } else {
        sub_06F0A4A4_orig(ctx, base);
    }
    show_added(added);
    if (g_art) note_select_question(lr, ctx, added);
}

// Jumps to a label: on the select screen, with the entries of the member the
// label is for (see kSelectLabels).
PPC_FUNC(sub_06EFA17C_orig);
PPC_FUNC(sub_06EFA17C) {
    if (g_art) {
        for (const SelectSite& s : kSelectLabels) {
            if (s.lr != ctx.lr) continue;
            const bool shown = g_shown;
            show_added(g_select_added[ctx.r[19] & 1][s.member]);
            sub_06EFA17C_orig(ctx, base);
            show_added(shown);
            return;
        }
    }
    sub_06EFA17C_orig(ctx, base);
}

// The functions that ask for UI positions leave Paul's rows as they found
// them: select screen (sub_06F4C480 the cursors, sub_06F4C07C the picked
// fighters), loading screen (sub_06F039E0 and sub_06F033B0 the portraits,
// sub_06F0B740 and sub_06F0C90C the names and faces), and the others.
#define ART_SCOPE(name)                                                                                          \
    PPC_FUNC(name##_orig);                                                                                       \
    PPC_FUNC(name) {                                                                                             \
        const bool shown = g_shown;                                                                              \
        name##_orig(ctx, base);                                                                                  \
        show_added(shown);                                                                                       \
    }
ART_SCOPE(sub_06F033B0)
ART_SCOPE(sub_06F039E0)
ART_SCOPE(sub_06F0B740)
ART_SCOPE(sub_06F0C90C)
ART_SCOPE(sub_06F23B10)
ART_SCOPE(sub_06F248CC)
ART_SCOPE(sub_06F24960)
ART_SCOPE(sub_06F25788)
ART_SCOPE(sub_06F33D8C)
ART_SCOPE(sub_06F3B734)
ART_SCOPE(sub_06F4391C)
ART_SCOPE(sub_06F4C07C)
ART_SCOPE(sub_06F4C480)
ART_SCOPE(sub_074AB214)
#undef ART_SCOPE

// The fights' HUD draws a fighter's name and faces from its texture
// container (7c476bde, resource 176) by numbers from a table by UI position
// ({name, face of player 1, of player 2}; Paul's 30, 105, 164), the UI
// position from the fighter's record (sub_033D555C: 59, "nobody", for the
// added fighter's records, which the HUD skips). The pack adds the added
// fighter's three after the container's 259 (keys/7c476bde.add): while the
// HUD works on the added fighter, its records give Paul's row and Paul's
// numbers become its own. The HUD's code accepts numbers under 259 only, the
// container's own draw and lookup (sub_052EA7D8, sub_04C98550) any it has.
constexpr uint32_t kHudResource = 176, kHudTextures = 259;
constexpr uint32_t kHudPaul[3] = {30, 105, 164};
constexpr uint32_t kHudQuestions[] = {0x04A28E2C, 0x052F9C00, 0x052FA01C};
bool g_hud_added = false; // the HUD works on the added fighter

uint32_t hud_number(uint32_t resource, uint32_t number) {
    if (!g_hud_added || resource != kHudResource) return number;
    for (uint32_t k = 0; k < 3; ++k) {
        if (number == kHudPaul[k]) return kHudTextures + k;
    }
    return number;
}

// A fighter's UI position from its record.
PPC_FUNC(sub_033D555C_orig);
PPC_FUNC(sub_033D555C) {
    if (g_hud && std::find(std::begin(kHudQuestions), std::end(kHudQuestions), ctx.lr) != std::end(kHudQuestions)) {
        g_hud_added = ctx.r[3] == kRecord || ctx.r[3] == kRecord + 1;
        if (g_hud_added) {
            ctx.r[3] = 0;
            return;
        }
    }
    sub_033D555C_orig(ctx, base);
}

PPC_FUNC(sub_052EA7D8_orig);
PPC_FUNC(sub_052EA7D8) {
    ctx.r[5] = hud_number(ctx.r[4], ctx.r[5]);
    sub_052EA7D8_orig(ctx, base);
}

PPC_FUNC(sub_04C98550_orig);
PPC_FUNC(sub_04C98550) {
    ctx.r[4] = hud_number(ctx.r[3], ctx.r[4]);
    sub_04C98550_orig(ctx, base);
}

// The HUD's functions that ask (kHudQuestions) end the added fighter's turn.
#define HUD_SCOPE(name)                                                                                          \
    PPC_FUNC(name##_orig);                                                                                       \
    PPC_FUNC(name) {                                                                                             \
        name##_orig(ctx, base);                                                                                  \
        g_hud_added = false;                                                                                     \
    }
HUD_SCOPE(sub_04A28840)
HUD_SCOPE(sub_052F9B34)
HUD_SCOPE(sub_052F9E34)
#undef HUD_SCOPE

// Lists the big select portraits' frames (see kPortraits); notes where the
// added fighter's are when the pack's container has them.
PPC_FUNC(sub_08B07B24);
PPC_FUNC(sub_06F0449C_orig);
PPC_FUNC(sub_06F0449C) {
    const uint32_t object = ctx.r[3];
    sub_06F0449C_orig(ctx, base);
    g_portrait_owner = 0;
    if (!g_art) return;
    // The container, found the way sub_06F0449C finds it: the entry of its key among the screen's resources.
    static const uint32_t key_slot = system_alloc(4);
    const PPCContext saved = ctx;
    store(key_slot, kPortraits);
    ctx.r[3] = load(object + kPortraitResources);
    ctx.r[4] = key_slot;
    sub_08B07B24(ctx, base);
    const uint32_t container = ctx.r[3] != 0 ? load(ctx.r[3]) : 0;
    ctx = saved;
    if (container == 0 || load(container) < kPortraitFrames + 2) return;
    for (uint32_t p = 0; p < 2; ++p) {
        const uint32_t first = load(object + kPortraitLists[p]);
        if (first == 0) return;
        g_portrait_frames[p][0] = load(first);
        g_portrait_frames[p][1] = container + load(container + 4 + 8 * (kPortraitFrames + p));
    }
    g_portrait_owner = object;
}

// Shows a big select portrait (object, UI position, slot): the added
// fighter's frames are in Paul's place of the lists meanwhile.
PPC_FUNC(sub_06F046D4_orig);
PPC_FUNC(sub_06F046D4) {
    const uint32_t object = ctx.r[3];
    if (!g_shown || object != g_portrait_owner || ctx.r[4] != 0) {
        sub_06F046D4_orig(ctx, base);
        return;
    }
    uint32_t first[2];
    for (uint32_t p = 0; p < 2; ++p) {
        first[p] = load(object + kPortraitLists[p]);
        if (load(first[p]) == g_portrait_frames[p][0]) store(first[p], g_portrait_frames[p][1]);
    }
    sub_06F046D4_orig(ctx, base);
    for (uint32_t p = 0; p < 2; ++p) {
        if (load(first[p]) == g_portrait_frames[p][1]) store(first[p], g_portrait_frames[p][0]);
    }
}

// A fighter's list of costumes: the added fighter's (see kCostumeLists), in
// the place of Paul's row while the function reads it.
PPC_FUNC(sub_0580D690_orig);
PPC_FUNC(sub_0580D690) {
    if (g_costume_entries == 0 || ctx.r[4] != kId) {
        sub_0580D690_orig(ctx, base);
        return;
    }
    const uint32_t paul[2] = {load(kCostumeLists), load(kCostumeLists + 4)};
    store(kCostumeLists, g_costume_entries);
    store(kCostumeLists + 4, 1);
    ctx.r[4] = 0;
    sub_0580D690_orig(ctx, base);
    store(kCostumeLists, paul[0]);
    store(kCostumeLists + 4, paul[1]);
}

// The chooser's functions that read kCostumePreviews: the added fighter's key
// in its place while they run (they may call each other).
int g_costume_lent = 0;
uint32_t g_costume_place = 0; // what the place held

void lend_costume_key(bool on) {
    if (g_costume_key == 0) return;
    const uint32_t place = kCostumePreviews + 4 * kId;
    if (on && g_costume_lent++ == 0) {
        g_costume_place = load(place);
        store(place, g_costume_key);
    } else if (!on && --g_costume_lent == 0) {
        store(place, g_costume_place);
    }
}

#define COSTUME_SCOPE(name)                                                                                      \
    PPC_FUNC(name##_orig);                                                                                       \
    PPC_FUNC(name) {                                                                                             \
        lend_costume_key(true);                                                                                  \
        name##_orig(ctx, base);                                                                                  \
        lend_costume_key(false);                                                                                 \
    }
COSTUME_SCOPE(sub_033E233C) // requests the pictures (CHANGE COSTUME pressed)
COSTUME_SCOPE(sub_033E265C) // the same for a pick with a remembered costume
#undef COSTUME_SCOPE

// Builds the chooser's entries (cursor r3, select id r4) once the pictures
// are there: for the added fighter without the customisation slots.
PPC_FUNC(sub_033E3460_orig);
PPC_FUNC(sub_033E3460) {
    const uint32_t cursor = ctx.r[3];
    const bool added = g_costume_key != 0 && ctx.r[4] == kId;
    const bool pending = load8(cursor + kChooserPending) != 0;
    lend_costume_key(true);
    sub_033E3460_orig(ctx, base);
    lend_costume_key(false);
    if (!added || !pending || load8(cursor + kChooserPending) != 0) return; // not built this time
    const uint32_t count = load8(cursor + kChooserCount);
    uint32_t kept = 0;
    while (kept < count && load(cursor + kChooserEntries + kChooserEntrySize * kept) != kChooserSlot) ++kept;
    store8(cursor + kChooserCount, static_cast<uint8_t>(kept));
}
