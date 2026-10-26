// NEON DLL - grid model.
//
// Pure C++ (no game headers) so it can be unit-tested on any machine against the original NEON Lua.
// The game glue (NeonOccupantReader) turns each cISC4Occupant into a BuildingRecord.
#pragma once
#include <cstdint>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

enum class NeonLoadClass : uint8_t { None = 0, Intermediate, Base, Peak };

struct NeonBuildingRecord
{
	std::vector<uint32_t> groups;   // occupant groups as the building carries them
	double kva = 0.0;               // KVA Rating (0xE652E51F), or derived
	double mwh = 0.0;               // MWh Rating (0x09A44AC9), or derived
	NeonLoadClass loadClass = NeonLoadClass::None; // from the exemplar (Base/Intermediate/Peak group)
	bool largePlant = true;         // only used for NEON fuel groups without a legacy 0xBB35xxxx group
	int unsupportedPlantType = -1;  // >= 0: power plant with no NEON/legacy group (0x27812853 power plant type)
};

// Values the Lua shim reads from the game every call, so the DLL works on exactly the same numbers
// as the original run_grid_balance_variables().
struct NeonGridInputs
{
	double powerDemanded = 0;    // game.trend_value(G_POWER_DEMANDED, 0)
	double powerExported = 0;    // game.trend_value(G_POWER_EXPORTED, 0)
	double powerImported = 0;    // game.trend_value(G_POWER_IMPORTED, 0)
	double powerProduced = 0;    // game.trend_value(G_POWER_PRODUCED, 0)
	double garbageToEnergy = 0;  // game.trend_value(G_GARBAGE_TO_ENERGY, 0)
	double powerConsumed = 0;    // game.g_power_consumed
	double productionCapacity = 0; // game.g_power_production_capacity
	int difficulty = 0;          // 0 easy, 1 medium, 2 hard
	double population = 0;       // game.g_city_r_population (only used by the enforcement ramp)

	bool operator==(const NeonGridInputs&) const = default;
};

class NeonGridModel
{
public:
	NeonGridModel();

	void Clear();
	void AddBuilding(uintptr_t key, NeonBuildingRecord record);
	void RemoveBuilding(uintptr_t key);
	size_t BuildingCount() const { return buildings.size(); }
	std::vector<uintptr_t> BuildingKeys() const { std::vector<uintptr_t> k; for (const auto& b : buildings) k.push_back(b.first); return k; }

	// Recomputes when the buildings or the inputs changed. Returns true when the published values changed.
	bool Update(const NeonGridInputs& inputs);

	// All values, by Lua name, for grid_logic_var and power_company_buildings.
	const std::vector<std::pair<std::string, double>>& GridValues() const { return gridValues; }
	const std::vector<std::pair<std::string, double>>& CompanyValues() const { return companyValues; }
	bool TryGetValue(std::string_view name, double& value) const;

	// Same contract as run_grid_balance_variables(ret_type): "T", "D", "X", "I", "B", "P".
	bool GridReturn(char retType, double& value) const;

	uint32_t CountOfGroup(uint32_t group) const;

	// Occupant groups of a legacy sum (for example "TRANSMISSION_RATING").
	static std::vector<uint32_t> GroupsOfSum(const char* name);
	// Groups a building is counted under (its 0xBB35xxxx groups, or the group derived from its NEON groups).
	static std::vector<uint32_t> CountedGroups(const NeonBuildingRecord& record);

	// Average kVA / MWh of the buildings in the city under each legacy group, from their exemplars.
	// neon.export writes them into kva_rating / mwh_rating, so query texts show the real lot values.
	struct GroupRating { uint32_t group; double kva; double mwh; bool wasteToEnergy; };
	std::vector<GroupRating> GroupRatings() const;

	// Representative legacy group used to count a building that only has a NEON fuel group.
	static uint32_t VirtualLegacyGroup(const NeonBuildingRecord& record);
	static NeonLoadClass DefaultLoadClass(const NeonBuildingRecord& record);

	// kVA / MWh the original Lua tables give a legacy group (kva_rating / mwh_rating), if any.
	static bool LegacyFallback(uint32_t group, double& kva, double& mwh);

private:
	struct GroupTotals { uint32_t count = 0; double kva = 0; double mwh = 0; };

	void AddToTotals(const NeonBuildingRecord& record, int sign);
	void Compute(const NeonGridInputs& in);

	std::unordered_map<uintptr_t, NeonBuildingRecord> buildings;
	std::unordered_map<uint32_t, GroupTotals> groupTotals;

	std::vector<std::pair<std::string, double>> gridValues;
	std::vector<std::pair<std::string, double>> companyValues;
	std::unordered_map<std::string, size_t> gridIndex;
	std::unordered_map<std::string, size_t> companyIndex;

	// Persist across calls exactly like the Lua globals (initial values 0.4 / 0.6 / 0.2).
	double iMPercent = 0.4, bMPercent = 0.6, pMPercent = 0.2;

	bool dirty = true;
	bool hasInputs = false;
	NeonGridInputs lastInputs;
};
