# SC4NEON — Nex-gen Energy Operating System DLL for SimCity 4

[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.3.4-informational)
![Game](https://img.shields.io/badge/SimCity_4-1.1.641-success)
![Platform](https://img.shields.io/badge/platform-Windows_x86-lightgrey)

**SC4NEON.dll** is the native companion of **NEON** (Nex-gen Energy Operating System), the power-grid module of the
[Colossus Addon Mod](https://github.com/UlisseWolf/Colossus_Addon_Mod) for SimCity 4 Deluxe / Rush Hour.
It moves NEON's grid simulation out of Lua and into C++, checks power-plant exemplars as the game loads them, and
can make the game actually deliver only the power that the NEON grid is able to carry.

> **Status:** source release, version 0.3.4. The model is verified against the original Lua outside the game (see
> [Testing](#testing)); building with MSVC and in-game testing are the next steps.

---

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lua API](#lua-api)
- [Building](#building)
- [Testing](#testing)
- [Repository layout](#repository-layout)
- [Credits](#credits)
- [License](#license)

## Features

### Grid model in C++
- Replaces `run_grid_balance_variables()` from `NEON_LUA`, including the 1,183 `get_source_building_count` calls
  that every evaluation used to make.
- Tracks NEON buildings as they enter or leave the city (occupant inserted/removed messages 0x99EF1142 / 0x99EF1143)
  and recomputes only when something changed. Every 10 game seconds it resyncs with the city, in case a message was
  missed.
- Fills every field of `grid_logic_var` and `power_company_buildings`, so the existing rewards and LTEXT
  expressions keep working unchanged.
- Counts plants without NEON occupant groups separately, by their Maxis power-plant type
  (`UNS_COAL_COUNT`, `UNS_WIND_COUNT`, …), for the power-company office screens.

### Exemplar checks
- With [SC4ResourceLoadingHooks](https://github.com/0xC0000054/sc4-resource-loading-hooks) installed, every NEON
  power-plant exemplar is checked as it is loaded (after patches are applied):
  - missing **MWh** (power produced, 0x27812852) and **kVA** (2.5 × MWh) values are filled in;
  - inconsistent values are reported;
  - a missing or duplicated **load class** (Base 0x18E64EA5, Intermediate 0x0BADB9AC, Peak 0x7283DCD7) is reported.
- Reads building values from the type exemplar instead of `cISC4Occupant::GetOccupantGroups`. That call fills a
  `std::set` from the game's Visual C++ 2003 STL, which is not compatible with current compilers.

### Grid enforcement (optional)
- When enabled, the power NEON says cannot be delivered really does not reach the buildings: blocks remain
  unpowered as outages.
- **How:** `cSC4PowerSimulator::UpdatePowerGrid` (0x006EE110) distributes production × 1.1, using a single float
  constant. The DLL rewrites that constant so the game distributes `demand − blackout`. No game instruction is
  patched.
- **What limits delivery:** two limits, each of which can be turned on or off:
  - **load balance:** the Base, Intermediate and Peak shares the grid can serve;
  - **infrastructure capacity:** plants → transmission → distribution → transformers.
- **Phase-in:** the limit ramps in with residential population, so new cities can still grow.
- **Safe fallback:** the DLL refuses to touch anything on an executable other than 1.1.641, and restores the
  constant when the city closes.

### Tooling
- `lua/NEON_LUA_DLL_ONLY.txt`, generated from the full script by `tools/make_dll_only.py`. It is 2,324 lines instead
  of 3,509, and it is the script that ships in NEON V 0.1.2.
- `tools/neon_audit.py` applies the DLL's exemplar rules to `.dat` files, before you launch the game.
- `tools/mod/` holds the scripts used to maintain the mod's DBPF files, texts and Lua.

## Requirements

| Component | Required | Notes |
| --- | --- | --- |
| SimCity 4 Deluxe / Rush Hour **1.1.641** | yes | Windows. Grid enforcement stays off on other versions. |
| NEON (Colossus Addon Mod) **V 0.1.2** | yes | Its `NEON_LUA_DLL_ONLY` needs this DLL. |
| [sc4-lua-extensions](https://github.com/0xC0000054/sc4-lua-extensions) | yes | Some rating tables still read exemplars from Lua. |
| [SC4ResourceLoadingHooks](https://github.com/0xC0000054/sc4-resource-loading-hooks) | recommended | Needed for the load-time exemplar checks. |
| [SC4 System Integration Module](https://github.com/UlisseWolf/SC4-System-Integration-Module) | recommended | Provides `create_reward_utilities`. NEON defines a fallback if it is missing. |

## Installation

1. Build `SC4NEON.dll` (see [Building](#building)), or download it from the
   [Releases](../../releases) page when one is available.
2. Copy `SC4NEON.dll` to your SimCity 4 **Plugins** folder, next to the other DLL mods.
3. Install NEON V 0.1.2 and the dependencies listed above.
4. Start the game and open a city. `SC4NEON.log`, created next to the DLL, reports what was loaded and counted.

## Configuration

`SC4NEON.ini` is created next to the DLL on first start:

```ini
[Enforcement]
; 1 = undeliverable power really causes outages
Enabled=1
; limit by the Base / Intermediate / Peak shares the grid can serve
LoadBalance=1
; limit by transmission -> distribution -> transformer capacity (MWh = kVA / 2.5)
Infrastructure=1
; enforcement ramps from 0 at StartPopulation to full at FullPopulation residents
StartPopulation=3000
FullPopulation=15000
```

The resulting values are exposed in `grid_logic_var`: `NEON_DELIVERABLE_POWER`, `NEON_LOADBALANCE_POWER`,
`NEON_INFRASTRUCTURE_POWER`, `NEON_BLACKOUT_POWER`, `NEON_ENFORCE_STRENGTH` and `NEON_ENFORCE_FACTOR`.

## Lua API

The DLL registers a `neon` table in the advisor scripting context. `lua/neon_dll_bridge.lua` shows how NEON uses it.

| Function | Purpose |
| --- | --- |
| `neon.update(...)` | Passes the game values the Lua used to read and returns whether the grid changed. |
| `neon.export(grid_logic_var, power_company_buildings)` | Writes every computed field into the two Lua tables. |
| `neon.grid(name)` | Reads a single computed value. |
| `neon.count(group)` | Number of buildings of a NEON occupant group in the city. |
| `neon.installed(group)` | Whether a lot of that group is installed in Plugins. |
| `neon.version()` | DLL version string. |

## Building

**Visual Studio 2022 or later** with the *Desktop development with C++* workload. The project uses whichever v14x
toolset is installed, so no retargeting is needed.

1. Open `SC4NEON.sln`.
2. Build the only configuration, **Release | x86** (SimCity 4 is a 32-bit game).
3. The output is `bin\Release\SC4NEON.dll`.

**CMake** works as well:

```bat
cmake -S . -B build -A Win32
cmake --build build --config Release
```

All dependencies are vendored:
- `vendor/gzcom-dll`: headers and the five source files needed;
- `vendor/sc4-resource-loading-hooks/include`: the public headers.

The C runtime is linked statically, so players do not need the Visual C++ Redistributable.

## Testing

The tests run outside the game. They need Python 3 with [`lupa`](https://pypi.org/project/lupa/) and a C++20
compiler to build `tests/model_driver.cpp`:

```sh
g++ -std=c++20 tests/model_driver.cpp src/NeonGridModel.cpp -o model_driver
```

| Test | Result |
| --- | --- |
| `tests/compare_with_lua.py`: C++ model vs. original Lua, 300 random cities | 0 differences, apart from the intended geothermal fix |
| `tests/bridge_test.py`: Lua bridge, 40 cities, with and without the DLL | 0 differences |
| `tests/dll_only_test.py`: DLL-only script, 100 cities, the 69 reward conditions and all triggers | 0 differences, no errors without the DLL |
| `tests/rules_test.cpp`: exemplar rules | pass |
| `tests/enforcement_test.cpp`: grid enforcement calculation | pass |

**Intended differences from the Lua:**
- **Geothermal plants** now report their MWh and kVA; in the Lua they were always 0.
- **Tidal and microwave plants** are counted through their NEON groups.
- **Ratings** come from the patched exemplars rather than the hard-coded tables.

## Repository layout

```
src/        DLL sources (director, grid model, rules, enforcement, Lua bindings, log)
lua/        NEON_LUA (reference), NEON_LUA_DLL_ONLY (shipped) and the DLL bridge
tests/      Lua/C++ comparison tests and unit tests
tools/      exemplar audit, script generators and mod-maintenance scripts
vendor/     gzcom-dll and sc4-resource-loading-hooks headers
docs/       detailed notes (README.it.md: full Italian documentation and changelog)
```

The complete changelog and the open design questions are in [`docs/README.it.md`](docs/README.it.md), in Italian.

## Credits

- **Ulisse Wolf**: NEON and the Colossus Addon Mod.
- **RobertaME**: AMPS, the power system NEON is derived from.
- **nsgomez**: [gzcom-dll](https://github.com/nsgomez/gzcom-dll), the GZCOM headers for SimCity 4 DLL plugins.
- **null 45 (0xC0000054)**: [sc4-resource-loading-hooks](https://github.com/0xC0000054/sc4-resource-loading-hooks)
  and [sc4-lua-extensions](https://github.com/0xC0000054/sc4-lua-extensions).

## License

This project is licensed under the **GNU Lesser General Public License v3.0**. See [`LICENSE`](LICENSE). The
LGPL-3.0 supplements the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html).

Third-party code keeps its own license:
- `vendor/gzcom-dll`: LGPL 2.1;
- `vendor/sc4-resource-loading-hooks`: MIT.

SimCity 4 is a trademark of Electronic Arts Inc. This project is not affiliated with or endorsed by Electronic Arts.
