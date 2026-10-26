// NEON DLL - grid model. C++ port of run_grid_balance_variables() from NEON_LUA (RobertaME 2024, Ulisse Wolf 2026).
#include "NeonGridModel.h"
#include "NeonIds.h"
#include <algorithm>
#include <cmath>
#include <initializer_list>
#include <unordered_set>

enum class NeonSumKind { Count, Rating, Power, Stacks };
enum class NeonTable { Grid, Company };

namespace
{
	struct LegacySum
	{
		NeonTable table;
		const char* name;
		NeonSumKind kind;
		const char* extra;              // "", "PV_GENERATORS", "STEPUP_TRANSFORMERS" or "PV_S_SOLAR_UNITS"
		std::vector<uint32_t> groups;
	};

	const std::vector<LegacySum>& LegacySums()
	{
#define NEON_LEGACY_SUM(table, name, kind, extra, ...) LegacySum{ table, name, kind, extra, std::vector<uint32_t> __VA_ARGS__ },
		static const std::vector<LegacySum> sums = {
#include "NeonLegacyGroups.inc"
		};
#undef NEON_LEGACY_SUM
		return sums;
	}

	struct LegacyValue { double kva, mwh, stacks; };

	const std::unordered_map<uint32_t, LegacyValue>& LegacyValues()
	{
#define NEON_LEGACY_VALUE(og, kva, mwh, stacks) { og, LegacyValue{ kva, mwh, stacks } },
		static const std::unordered_map<uint32_t, LegacyValue> values = {
#include "NeonLegacyValues.inc"
		};
#undef NEON_LEGACY_VALUE
		return values;
	}

	const LegacySum* FindSum(std::string_view name)
	{
		for (const LegacySum& s : LegacySums())
		{
			if (name == s.name) return &s;
		}
		return nullptr;
	}

	// Default load class of each legacy count bucket, as grouped by the Lua (LARGE_I_POWER, SMALL_B_POWER, ...).
	const std::unordered_map<uint32_t, NeonLoadClass>& LegacyGroupClass()
	{
		static const std::unordered_map<uint32_t, NeonLoadClass> map = []
		{
			std::unordered_map<uint32_t, NeonLoadClass> m;
			auto add = [&](std::initializer_list<const char*> buckets, NeonLoadClass c)
			{
				for (const char* b : buckets)
				{
					if (const LegacySum* s = FindSum(b))
					{
						for (uint32_t og : s->groups) m.emplace(og, c);
					}
				}
			};
			add({ "PV_PANEL_SETS", "SOLAR_GENERAT_COUNT", "WIND_GENERATE_COUNT", "LARGE_SOLAR_COUNT", "LARGE_WIND_COUNT",
				  "SMALL_SOLAR_COUNT", "SMALL_WIND_COUNT" }, NeonLoadClass::Intermediate);
			add({ "BASE_GENERATE_COUNT", "LARGE_COAL_COUNT", "LARGE_BIO_COUNT", "LARGE_FISSION_COUNT", "LARGE_FUSION_COUNT",
				  "LARGE_GEO_COUNT", "LARGE_WASTE_COUNT", "LARGE_HYDRO_COUNT", "SMALL_COAL_COUNT", "SMALL_BIO_COUNT",
				  "SMALL_FISSION_COUNT", "SMALL_FUSION_COUNT", "SMALL_GEO_COUNT", "SMALL_WASTE_COUNT", "SMALL_HYDRO_COUNT" },
				NeonLoadClass::Base);
			add({ "OIL_GENERATOR_COUNT", "NG_GENERATOR_COUNT", "LARGE_OIL_COUNT", "LARGE_NAT_GAS_COUNT", "SMALL_OIL_COUNT",
				  "SMALL_NAT_GAS_COUNT" }, NeonLoadClass::Peak);
			return m;
		}();
		return map;
	}

	const std::unordered_set<uint32_t>& WasteToEnergyGroups()
	{
		static const std::unordered_set<uint32_t> set = []
		{
			std::unordered_set<uint32_t> s;
			for (const char* b : { "LARGE_WASTE_COUNT", "SMALL_WASTE_COUNT" })
			{
				if (const LegacySum* sum = FindSum(b)) s.insert(sum->groups.begin(), sum->groups.end());
			}
			return s;
		}();
		return set;
	}

	bool Has(const NeonBuildingRecord& r, uint32_t og)
	{
		return std::find(r.groups.begin(), r.groups.end(), og) != r.groups.end();
	}

	// Groups the building is counted under in the legacy sums.
	std::vector<uint32_t> EffectiveGroups(const NeonBuildingRecord& r)
	{
		std::vector<uint32_t> result;
		for (uint32_t og : r.groups)
		{
			if (NeonIds::IsLegacyGroup(og)) result.push_back(og);
		}
		if (result.empty())
		{
			const uint32_t v = NeonGridModel::VirtualLegacyGroup(r);
			if (v != 0) result.push_back(v);
		}
		return result;
	}

	double LuaRound(double v) { return std::floor(v + 0.5); }
}

NeonGridModel::NeonGridModel()
{
	Clear();
}

void NeonGridModel::Clear()
{
	buildings.clear();
	groupTotals.clear();
	iMPercent = 0.4; bMPercent = 0.6; pMPercent = 0.2;
	dirty = true;
	hasInputs = false;
}

uint32_t NeonGridModel::VirtualLegacyGroup(const NeonBuildingRecord& r)
{
	using namespace NeonIds;
	// Equipment.
	if (Has(r, kOgPowerStorage))   return 0xBB350040; // BATTERY_LOT
	if (Has(r, kOgHvTransformers)) return 0xBB350120; // TRANSMISSION   (assumed mapping, see README)
	if (Has(r, kOgMvTransformers)) return 0xBB350030; // DISTRIBUTE_A   (assumed mapping, see README)
	if (Has(r, kOgLvTransformers)) return 0xBB350022; // TRANSFORMER    (assumed mapping, see README)
	if (Has(r, kOgAuxiliary))      return 0xBB350140; // MISC_ELEC_F    (assumed mapping, see README)

	if (Has(r, kOgGenerators))
	{
		if (Has(r, kOgOil))        return 0xBB350000; // DIESEL / OIL_GENERATOR
		if (Has(r, kOgSolar))      return 0xBB350011; // SOLAR_GENERAT
		if (Has(r, kOgNaturalGas)) return 0xBB350100; // NG_GENERATOR
		if (Has(r, kOgWind))       return 0xBB350110; // WIND_GENERATE
		return 0xBB3500FF;                            // BASE_GENERATE
	}

	struct Fuel { uint32_t og, large, small; };
	static constexpr Fuel fuels[] = {
		{ kOgCoal,          0xBB3500C0, 0xBB3501C0 },
		{ kOgOil,           0xBB350090, 0xBB350190 },
		{ kOgBiomass,       0xBB3500B0, 0xBB3501B0 },
		{ kOgNaturalGas,    0xBB3500A0, 0xBB3501A0 },
		{ kOgFission,       0xBB350078, 0xBB350178 },
		{ kOgFusion,        0xBB350088, 0xBB350188 },
		{ kOgGeothermal,    0xBB350070, 0xBB350170 },
		{ kOgSolar,         0xBB350050, 0xBB350150 },
		{ kOgWind,          0xBB350060, 0xBB350160 },
		{ kOgWasteToEnergy, 0xBB3500D0, 0xBB3501D0 },
		{ kOgHydro,         0xBB3500E0, 0xBB3501E0 },
		// Tidal and Microwave have no bucket in the Lua: they only count in the load class totals.
	};
	for (const Fuel& f : fuels)
	{
		if (Has(r, f.og)) return r.largePlant ? f.large : f.small;
	}
	return 0;
}

bool NeonGridModel::LegacyFallback(uint32_t group, double& kva, double& mwh)
{
	auto it = LegacyValues().find(group);
	if (it == LegacyValues().end()) return false;
	kva = it->second.kva;
	mwh = it->second.mwh;
	return true;
}

NeonLoadClass NeonGridModel::DefaultLoadClass(const NeonBuildingRecord& r)
{
	using namespace NeonIds;
	for (uint32_t og : EffectiveGroups(r))
	{
		auto it = LegacyGroupClass().find(og);
		if (it != LegacyGroupClass().end()) return it->second;
	}
	if (Has(r, kOgTidal)) return NeonLoadClass::Intermediate;
	if (Has(r, kOgMicrowave)) return NeonLoadClass::Peak;
	return NeonLoadClass::None;
}

void NeonGridModel::AddToTotals(const NeonBuildingRecord& r, int sign)
{
	for (uint32_t og : EffectiveGroups(r))
	{
		GroupTotals& t = groupTotals[og];
		t.count += sign;
		t.kva += sign * r.kva;
		t.mwh += sign * r.mwh;
	}
}

void NeonGridModel::AddBuilding(uintptr_t key, NeonBuildingRecord record)
{
	RemoveBuilding(key);
	AddToTotals(record, +1);
	buildings.emplace(key, std::move(record));
	dirty = true;
}

void NeonGridModel::RemoveBuilding(uintptr_t key)
{
	auto it = buildings.find(key);
	if (it != buildings.end())
	{
		AddToTotals(it->second, -1);
		buildings.erase(it);
		dirty = true;
	}
}

std::vector<NeonGridModel::GroupRating> NeonGridModel::GroupRatings() const
{
	std::vector<GroupRating> result;
	for (const auto& [og, t] : groupTotals)
	{
		if (t.count == 0) continue;
		result.push_back({ og, t.kva / t.count, t.mwh / t.count, WasteToEnergyGroups().count(og) != 0 });
	}
	return result;
}

std::vector<uint32_t> NeonGridModel::GroupsOfSum(const char* name)
{
	const LegacySum* s = FindSum(name);
	return s ? s->groups : std::vector<uint32_t>{};
}

std::vector<uint32_t> NeonGridModel::CountedGroups(const NeonBuildingRecord& record)
{
	return EffectiveGroups(record);
}

uint32_t NeonGridModel::CountOfGroup(uint32_t group) const
{
	auto it = groupTotals.find(group);
	return it == groupTotals.end() ? 0 : it->second.count;
}

bool NeonGridModel::Update(const NeonGridInputs& inputs)
{
	if (!dirty && hasInputs && inputs == lastInputs)
	{
		return false;
	}
	Compute(inputs);
	lastInputs = inputs;
	hasInputs = true;
	dirty = false;
	return true;
}

bool NeonGridModel::TryGetValue(std::string_view name, double& value) const
{
	const std::string key(name);
	if (auto it = gridIndex.find(key); it != gridIndex.end()) { value = gridValues[it->second].second; return true; }
	if (auto it = companyIndex.find(key); it != companyIndex.end()) { value = companyValues[it->second].second; return true; }
	return false;
}

bool NeonGridModel::GridReturn(char retType, double& value) const
{
	double v = 0, imported = lastInputs.powerImported;
	switch (retType)
	{
	case 'T': TryGetValue("TRANSMIT_AVAILABLE", v); value = std::max(v, 0.0); return true;
	case 'D': TryGetValue("DISTRIB_AVAILABLE", v); value = std::max(v, 0.0); return true;
	case 'X': TryGetValue("TRANSFORM_AVAILABLE", v); value = std::max(v, 0.0); return true;
	case 'I': TryGetValue("ALL_I_POWER", v); value = v; return true;
	case 'B': TryGetValue("ALL_B_POWER", v); value = v; return true;
	case 'P': TryGetValue("ALL_P_POWER", v); value = v - imported; return true;
	default: return false;
	}
}

void NeonGridModel::Compute(const NeonGridInputs& in)
{
	gridValues.clear(); companyValues.clear(); gridIndex.clear(); companyIndex.clear();
	std::unordered_map<std::string, double> g;   // working copy of grid_logic_var

	auto set = [&](const char* name, double v)
	{
		g[name] = v;
		auto it = gridIndex.find(name);
		if (it == gridIndex.end()) { gridIndex.emplace(name, gridValues.size()); gridValues.emplace_back(name, v); }
		else gridValues[it->second].second = v;
	};
	auto get = [&](const char* name) { auto it = g.find(name); return it == g.end() ? 0.0 : it->second; };

	auto totals = [&](uint32_t og) { auto it = groupTotals.find(og); return it == groupTotals.end() ? GroupTotals{} : it->second; };
	auto pvPanelMwh = [&]
	{
		const GroupTotals t = totals(0xBB350010);
		if (t.count > 0) return t.mwh / t.count;
		auto it = LegacyValues().find(0xBB350010);
		return it == LegacyValues().end() ? 0.0 : it->second.mwh;
	};
	auto evalSum = [&](const LegacySum& s) -> double
	{
		double v = 0;
		for (uint32_t og : s.groups)
		{
			const GroupTotals t = totals(og);
			switch (s.kind)
			{
			case NeonSumKind::Count:  v += t.count; break;
			case NeonSumKind::Rating: v += t.kva; break;
			case NeonSumKind::Power:  v += t.mwh; break;
			case NeonSumKind::Stacks:
			{
				auto it = LegacyValues().find(og);
				v += t.count * (it == LegacyValues().end() ? 0.0 : it->second.stacks);
				break;
			}
			}
		}
		const std::string_view extra = s.extra;
		if (extra == "PV_GENERATORS")       v += (s.kind == NeonSumKind::Power) ? get("PV_GENERATORS") * pvPanelMwh() : get("PV_GENERATORS");
		else if (extra == "STEPUP_TRANSFORMERS") v += get("STEPUP_TRANSFORMERS");
		else if (extra == "PV_S_SOLAR_UNITS")    v += get("PV_S_SOLAR_UNITS") * pvPanelMwh();
		return v;
	};

	// ---- 1. plain sums (no extra term), then the PV split, then the sums that use it.
	for (const LegacySum& s : LegacySums())
	{
		if (*s.extra == '\0' && s.table == NeonTable::Grid) set(s.name, evalSum(s));
	}
	set("PV_S_SOLAR_UNITS", std::min(get("PV_PANEL_SETS"), get("STEPUP_TRANSFORMERS") * 128));
	set("PV_GENERATORS", get("PV_PANEL_SETS") - get("PV_S_SOLAR_UNITS"));
	for (const LegacySum& s : LegacySums())
	{
		if (*s.extra != '\0') set(s.name, evalSum(s));
	}
	for (const LegacySum& s : LegacySums())
	{
		if (s.table == NeonTable::Company)
		{
			companyIndex.emplace(s.name, companyValues.size());
			companyValues.emplace_back(s.name, evalSum(s));
		}
	}
	double company[5] = {};
	for (int i = 0; i < 5; i++)
	{
		static const char* names[] = { "FRONT_OFFICE_COUNT", "MAINT_BUILD_COUNT", "CENT_OFFICE_COUNT", "RES_FACILITY_COUNT", "CORP_HQ_COUNT" };
		auto it = companyIndex.find(names[i]);
		company[i] = it == companyIndex.end() ? 0 : companyValues[it->second].second;
	}
	const double maintCount = company[1], resFacilityCount = company[3];

	// ---- 2. Waste-to-energy: real output follows the garbage actually burned (Lua: mwh_rating.ID_BB35xxDx).
	{
		const double maxTotal = std::max(get("L_WASTE_MAX_POWER") + get("S_WASTE_MAX_POWER"), 1.0);
		double large = 0, small = 0;
		const LegacySum* l = FindSum("L_WASTE_POWER");
		const LegacySum* s = FindSum("S_WASTE_POWER");
		for (const auto& [key, r] : buildings)
		{
			for (uint32_t og : EffectiveGroups(r))
			{
				const double share = LuaRound(r.mwh / maxTotal * in.garbageToEnergy * 0.1);
				if (l && std::find(l->groups.begin(), l->groups.end(), og) != l->groups.end()) large += share;
				if (s && std::find(s->groups.begin(), s->groups.end(), og) != s->groups.end()) small += share;
			}
		}
		set("L_WASTE_POWER", large);
		set("S_WASTE_POWER", small);
	}

	// ---- 3. buckets the Lua never filled.
	//  * Geothermal: the Lua counted the plants but its rating / power names (LARGE_GEO_RATING, L_GEOTHERMAL_POWER ...)
	//    were always 0. The DLL fills them from the geothermal legacy groups.
	//  * Tidal and Microwave: no legacy group exists; the DLL counts buildings that carry the NEON fuel group.
	//  * Special plants: no group exists yet, they stay 0.
	{
		auto legacyTotals = [&](const char* countBucket)
		{
			GroupTotals sum{};
			if (const LegacySum* s = FindSum(countBucket))
			{
				for (uint32_t og : s->groups) { const GroupTotals t = totals(og); sum.count += t.count; sum.kva += t.kva; sum.mwh += t.mwh; }
			}
			return sum;
		};
		const GroupTotals lGeo = legacyTotals("LARGE_GEO_COUNT"), sGeo = legacyTotals("SMALL_GEO_COUNT");
		set("LARGE_GEO_RATING", lGeo.kva);   set("SMALL_GEO_RATING", sGeo.kva);
		set("L_GEOTHERMAL_POWER", lGeo.mwh); set("S_GEOTHERMAL_POWER", sGeo.mwh);
		set("L_GEO_POWER", lGeo.mwh);        set("S_GEO_POWER", sGeo.mwh);

		GroupTotals tidal[2]{}, micro[2]{};   // [0] large, [1] small
		for (const auto& [key, r] : buildings)
		{
			if (!EffectiveGroups(r).empty()) continue;
			GroupTotals* t = Has(r, NeonIds::kOgTidal) ? tidal : Has(r, NeonIds::kOgMicrowave) ? micro : nullptr;
			if (!t) continue;
			GroupTotals& b = t[r.largePlant ? 0 : 1];
			b.count++; b.kva += r.kva; b.mwh += r.mwh;
		}
		set("LARGE_TIDAL_COUNT", tidal[0].count); set("SMALL_TIDAL_COUNT", tidal[1].count);
		set("LARGE_TIDAL_RATING", tidal[0].kva);  set("SMALL_TIDAL_RATING", tidal[1].kva);
		set("L_TIDAL_POWER", tidal[0].mwh);       set("S_TIDAL_POWER", tidal[1].mwh);
		set("LARGE_MICRO_COUNT", micro[0].count); set("SMALL_MICRO_COUNT", micro[1].count);
		set("LARGE_MICRO_RATING", micro[0].kva);  set("SMALL_MICRO_RATING", micro[1].kva);
		set("L_MICRO_POWER", micro[0].mwh);       set("S_MICRO_POWER", micro[1].mwh);
	}
	for (const char* z : { "LARGE_SPECIAL_I_COUNT", "LARGE_SPECIAL_B_COUNT", "LARGE_SPECIAL_P_COUNT", "SMALL_SPECIAL_I_COUNT",
		"SMALL_SPECIAL_B_COUNT", "SMALL_SPECIAL_P_COUNT", "LARGE_SPECIAL_I_RATING", "LARGE_SPECIAL_B_RATING",
		"LARGE_SPECIAL_P_RATING", "SMALL_SPECIAL_I_RATING", "SMALL_SPECIAL_B_RATING", "SMALL_SPECIAL_P_RATING",
		"L_SPECIAL_I_POWER", "L_SPECIAL_B_POWER", "L_SPECIAL_P_POWER", "S_SPECIAL_I_POWER", "S_SPECIAL_B_POWER", "S_SPECIAL_P_POWER",
		// declared in the Lua grid_logic_var table but never assigned by the Lua (spelling variants)
		"LARGE_FISSION_RATING", "SMALL_FISSION_RATING", "LARGE_NAT_GAS_RATING", "SMALL_NAT_GAS_RATING" })
	{
		set(z, 0);
	}

	// ---- 4. counts
	set("DISTRIBUTION_COUNT", get("DISTRIBUTE_COUNT_A") + get("DISTRIBUTE_COUNT_B"));
	set("I_GENERATOR_COUNT", get("SOLAR_GENERAT_COUNT") + get("WIND_GENERATE_COUNT"));
	set("B_GENERATOR_COUNT", get("BASE_GENERATE_COUNT"));
	set("P_GENERATOR_COUNT", get("OIL_GENERATOR_COUNT") + get("NG_GENERATOR_COUNT"));
	set("LARGE_INTERM_COUNT", get("LARGE_SOLAR_COUNT") + get("LARGE_WIND_COUNT") + get("LARGE_TIDAL_COUNT") + get("LARGE_SPECIAL_I_COUNT"));
	set("LARGE_BASE_COUNT", get("LARGE_GEO_COUNT") + get("LARGE_BIO_COUNT") + get("LARGE_FISSION_COUNT") + get("LARGE_FUSION_COUNT")
		+ get("LARGE_COAL_COUNT") + get("LARGE_WASTE_COUNT") + get("LARGE_HYDRO_COUNT") + get("LARGE_SPECIAL_B_COUNT"));
	set("LARGE_PEAK_COUNT", get("LARGE_MICRO_COUNT") + get("LARGE_OIL_COUNT") + get("LARGE_NAT_GAS_COUNT") + get("LARGE_SPECIAL_P_COUNT"));
	set("SMALL_INTERM_COUNT", get("SMALL_SOLAR_COUNT") + get("SMALL_WIND_COUNT") + get("SMALL_TIDAL_COUNT") + get("SMALL_SPECIAL_I_COUNT"));
	set("SMALL_BASE_COUNT", get("SMALL_GEO_COUNT") + get("SMALL_BIO_COUNT") + get("SMALL_FISSION_COUNT") + get("SMALL_FUSION_COUNT")
		+ get("SMALL_COAL_COUNT") + get("SMALL_WASTE_COUNT") + get("SMALL_HYDRO_COUNT") + get("SMALL_SPECIAL_B_COUNT"));
	set("SMALL_PEAK_COUNT", get("SMALL_MICRO_COUNT") + get("SMALL_OIL_COUNT") + get("SMALL_NAT_GAS_COUNT") + get("SMALL_SPECIAL_P_COUNT"));
	set("LARGE_POWER_COUNT", get("LARGE_INTERM_COUNT") + get("LARGE_BASE_COUNT") + get("LARGE_PEAK_COUNT"));
	set("SMALL_POWER_COUNT", get("SMALL_INTERM_COUNT") + get("SMALL_BASE_COUNT") + get("SMALL_PEAK_COUNT"));
	set("TOTAL_POWER_COUNT", get("SMALL_POWER_COUNT") + get("LARGE_POWER_COUNT"));

	// ---- 5. kVA
	set("DISTRIBUTION_RATING", get("DISTRIBUTE_RATING_A") + get("DISTRIBUTE_RATING_B"));
	set("DISTRIB_RATING_CAP", std::min(get("DISTRIBUTION_RATING"), get("TRANSFORMER_RATING")));
	set("LARGE_I_RATING", get("LARGE_SOLAR_RATING") + get("LARGE_WIND_RATING") + get("LARGE_TIDAL_RATING") + get("LARGE_SPECIAL_I_RATING"));
	set("LARGE_B_RATING", get("LARGE_COAL_RATING") + get("LARGE_BIO_RATING") + get("LARGE_FUSION_RATING") + get("LARGE_FISION_RATING")
		+ get("LARGE_GEO_RATING") + get("LARGE_WASTE_RATING") + get("LARGE_HYDRO_RATING") + get("LARGE_SPECIAL_B_RATING"));
	set("LARGE_P_RATING", get("LARGE_OIL_RATING") + get("LARGE_NATGAS_RATING") + get("LARGE_MICRO_RATING") + get("LARGE_SPECIAL_P_RATING"));
	set("SMALL_I_RATING", get("SMALL_SOLAR_RATING") + get("SMALL_WIND_RATING") + get("SMALL_TIDAL_RATING") + get("SMALL_SPECIAL_I_RATING"));
	set("SMALL_B_RATING", get("SMALL_COAL_RATING") + get("SMALL_BIO_RATING") + get("SMALL_FUSION_RATING") + get("SMALL_FISION_RATING")
		+ get("SMALL_GEO_RATING") + get("SMALL_WASTE_RATING") + get("SMALL_HYDRO_RATING") + get("SMALL_SPECIAL_B_RATING"));
	set("SMALL_P_RATING", get("SMALL_OIL_RATING") + get("SMALL_NATGAS_RATING") + get("SMALL_MICRO_RATING") + get("SMALL_SPECIAL_P_RATING"));
	set("LARGE_PLANTS_RATING", get("LARGE_I_RATING") + get("LARGE_B_RATING") + get("LARGE_P_RATING"));
	set("SMALL_PLANTS_RATING", get("SMALL_I_RATING") + get("SMALL_B_RATING") + get("SMALL_P_RATING") + get("MISC_ELEC_F_RATING"));
	set("LARGE_POWER_RATING", get("LARGE_PLANTS_RATING") + std::fabs(in.powerImported - in.powerExported) / 0.584);
	set("TRANSMIT_AVAILABLE", std::min({ get("TRANSMISSION_RATING"),
		get("DISTRIBUTION_RATING") - get("SMALL_PLANTS_RATING"),
		get("TRANSFORMER_RATING") - get("SMALL_PLANTS_RATING") }) - get("LARGE_POWER_RATING"));
	set("DISTRIB_AVAILABLE", get("DISTRIB_RATING_CAP") - (get("TRANSMISSION_RATING") + get("SMALL_PLANTS_RATING")));
	set("TRANSFORM_AVAILABLE", get("TRANSFORMER_RATING") - get("DISTRIBUTION_RATING"));
	set("AVERAGE_PRODUCTION_CAPACITY", in.powerConsumed / std::max(in.productionCapacity, 1.0));

	// ---- 6. MWh by bucket (display values, same as the Lua)
	set("GENERATOR_I_POWER", get("SOLAR_GENERAT_POWER") + get("WIND_GENERATE_POWER"));
	set("GENERATOR_B_POWER", get("BASE_GENERATE_POWER"));
	set("GENERATOR_P_POWER", get("DIESEL_GENER_POWER") + get("NG_GENERATOR_POWER"));
	set("LARGE_I_POWER", get("L_SOLAR_POWER") + get("L_WIND_POWER") + get("L_TIDAL_POWER") + get("L_SPECIAL_I_POWER"));
	set("LARGE_B_POWER", get("L_COAL_POWER") + get("L_BIO_POWER") + get("L_FISSION_POWER") + get("L_FUSION_POWER")
		+ get("L_GEOTHERMAL_POWER") + get("L_WASTE_POWER") + get("L_HYDRO_POWER") + get("L_SPECIAL_B_POWER"));
	set("LARGE_P_POWER", get("L_OIL_POWER") + get("L_NAT_GAS_POWER") + get("L_MICRO_POWER") + get("L_SPECIAL_P_POWER"));
	set("SMALL_I_POWER", get("S_SOLAR_POWER") + get("S_WIND_POWER") + get("S_TIDAL_POWER") + get("S_SPECIAL_I_POWER"));
	set("SMALL_B_POWER", get("S_COAL_POWER") + get("S_BIO_POWER") + get("S_FISSION_POWER") + get("S_FUSION_POWER")
		+ get("S_GEOTHERMAL_POWER") + get("S_WASTE_POWER") + get("S_HYDRO_POWER") + get("S_SPECIAL_B_POWER"));
	set("SMALL_P_POWER", get("S_OIL_POWER") + get("S_NAT_GAS_POWER") + get("S_MICRO_POWER") + get("S_SPECIAL_P_POWER"));

	// ---- 7. Supported generation by load class. NEON rule: the class written in the exemplar decides.
	//      Buildings without a class fall back to the Lua grouping (and are reported by the exemplar check).
	{
		const double wasteMax = std::max(get("L_WASTE_MAX_POWER") + get("S_WASTE_MAX_POWER"), 1.0);
		double sup[4] = {};
		for (const auto& [key, r] : buildings)
		{
			NeonLoadClass c = r.loadClass != NeonLoadClass::None ? r.loadClass : DefaultLoadClass(r);
			if (c == NeonLoadClass::None) continue;
			// Equipment (storage, transformers, auxiliary) never produces supported generation.
			const uint32_t v = VirtualLegacyGroup(r);
			if (v == 0xBB350040 || v == 0xBB350120 || v == 0xBB350030 || v == 0xBB350022 || v == 0xBB350140) continue;

			double mwh = r.mwh;
			bool isWaste = Has(r, NeonIds::kOgWasteToEnergy);
			for (uint32_t og : EffectiveGroups(r)) isWaste = isWaste || WasteToEnergyGroups().count(og) != 0;
			if (isWaste) mwh = LuaRound(r.mwh / wasteMax * in.garbageToEnergy * 0.1);
			sup[static_cast<int>(c)] += mwh;
		}
		set("SUP_GEN_I_POWER", sup[static_cast<int>(NeonLoadClass::Intermediate)]);
		set("SUP_GEN_B_POWER", sup[static_cast<int>(NeonLoadClass::Base)]);
		set("SUP_GEN_P_POWER", sup[static_cast<int>(NeonLoadClass::Peak)]);
	}

	const double supI = get("SUP_GEN_I_POWER"), supB = get("SUP_GEN_B_POWER"), supP = get("SUP_GEN_P_POWER");
	const double supAll = supI + supB + supP;
	set("POWER_DEVIATION", in.powerProduced - supAll);
	if (supAll == 0)
	{
		set("DEV_I_POWER", 0); set("DEV_B_POWER", 0); set("DEV_P_POWER", get("POWER_DEVIATION"));
	}
	else
	{
		set("DEV_I_POWER", get("POWER_DEVIATION") * (supI / supAll));
		set("DEV_B_POWER", get("POWER_DEVIATION") * (supB / supAll));
		set("DEV_P_POWER", get("POWER_DEVIATION") * (supP / supAll));
	}
	const double devI = get("DEV_I_POWER"), devB = get("DEV_B_POWER"), devP = get("DEV_P_POWER");
	set("GEN_I_POWER", supI + devI);
	set("GEN_B_POWER", supB + devB);
	set("GEN_P_POWER", supP + devP);
	set("GENERATOR_I_D_POWER", get("GENERATOR_I_POWER") + devI * (get("GENERATOR_I_POWER") / std::max(supI, 1.0)));
	set("GENERATOR_B_D_POWER", get("GENERATOR_B_POWER") + devB * (get("GENERATOR_B_POWER") / std::max(supB, 1.0)));
	set("GENERATOR_P_D_POWER", get("GENERATOR_P_POWER") + devP * (get("GENERATOR_P_POWER") / std::max(supP, 1.0)));

	auto dPower = [&](const char* name, const char* l, const char* s, double dev, double sup)
	{
		const double both = get(l) + get(s);
		set(name, both + dev * (both / std::max(sup, 1.0)));
	};
	dPower("D_SOLAR_POWER", "L_SOLAR_POWER", "S_SOLAR_POWER", devI, supI);
	dPower("D_WIND_POWER", "L_WIND_POWER", "S_WIND_POWER", devI, supI);
	dPower("D_TIDAL_POWER", "L_TIDAL_POWER", "S_TIDAL_POWER", devI, supI);
	dPower("D_SPECIAL_I_POWER", "L_SPECIAL_I_POWER", "S_SPECIAL_I_POWER", devI, supI);
	dPower("D_COAL_POWER", "L_COAL_POWER", "S_COAL_POWER", devB, supB);
	dPower("D_BIO_POWER", "L_BIO_POWER", "S_BIO_POWER", devB, supB);
	dPower("D_FISSION_POWER", "L_FISSION_POWER", "S_FISSION_POWER", devB, supB);
	dPower("D_FUSION_POWER", "L_FUSION_POWER", "S_FUSION_POWER", devP, supP); // as in the Lua (uses the Peak deviation)
	dPower("D_GEOTHERMAL_POWER", "L_GEOTHERMAL_POWER", "S_GEOTHERMAL_POWER", devB, supB);
	set("D_GEO_POWER", get("D_GEOTHERMAL_POWER"));
	dPower("D_WASTE_POWER", "L_WASTE_POWER", "S_WASTE_POWER", devB, supB);
	dPower("D_HYDRO_POWER", "L_HYDRO_POWER", "S_HYDRO_POWER", devB, supB);
	dPower("D_SPECIAL_B_POWER", "L_SPECIAL_B_POWER", "S_SPECIAL_B_POWER", devB, supB);
	dPower("D_OIL_POWER", "L_OIL_POWER", "S_OIL_POWER", devP, supP);
	dPower("D_NAT_GAS_POWER", "L_NAT_GAS_POWER", "S_NAT_GAS_POWER", devP, supP);
	dPower("D_MICRO_POWER", "L_MICRO_POWER", "S_MICRO_POWER", devP, supP);
	dPower("D_SPECIAL_P_POWER", "L_SPECIAL_P_POWER", "S_SPECIAL_P_POWER", devP, supP);

	// ---- 8. batteries
	const double genI = get("GEN_I_POWER"), genB = get("GEN_B_POWER"), genP = get("GEN_P_POWER");
	const double battery = get("BATTERY_P_POWER");
	if (battery <= genI)
	{
		set("ALL_I_POWER", genI - battery); set("ALL_B_POWER", genB);
		set("ALL_P_POWER", genP + battery + in.powerImported); set("BAT_UNUSED", 0);
	}
	else if ((battery - genI) <= genB)
	{
		set("ALL_I_POWER", 0); set("ALL_B_POWER", genB - (battery - genI));
		set("ALL_P_POWER", genP + battery + in.powerImported); set("BAT_UNUSED", 0);
	}
	else
	{
		set("ALL_I_POWER", 0); set("ALL_B_POWER", 0);
		set("ALL_P_POWER", genP + genB + genI + in.powerImported); set("BAT_UNUSED", battery - (genI + genB));
	}

	// ---- 9. grid limits by difficulty and power company buildings
	if (in.difficulty == 0)
	{
		iMPercent = 0.4; bMPercent = 0.6; pMPercent = 0.2;
	}
	else if (in.difficulty == 1)
	{
		if (maintCount < 1) { iMPercent = 0.3; bMPercent = 0.5; pMPercent = 0.3; }
		else { iMPercent = 0.4; bMPercent = 0.6; pMPercent = 0.2; }
	}
	else if (in.difficulty == 2)
	{
		const double n = maintCount + resFacilityCount;
		if (n < 1) { iMPercent = 0.2; bMPercent = 0.4; pMPercent = 0.4; }
		else if (n < 2) { iMPercent = 0.3; bMPercent = 0.5; pMPercent = 0.3; }
		else { iMPercent = 0.4; bMPercent = 0.6; pMPercent = 0.2; }
	}
	set("I_MPERCENT", iMPercent); set("B_MPERCENT", bMPercent); set("P_MPERCENT", pMPercent);

	// ---- 9b. power plants NEON does not support (no NEON or legacy group), by Maxis power plant type.
	{
		double uns[10] = {}, largeOther = 0, smallOther = 0, otherMwh = 0;
		for (const auto& [key, r] : buildings)
		{
			if (r.unsupportedPlantType < 0) continue;
			const int type = r.unsupportedPlantType;
			if (type >= 0 && type < 10) uns[type] += 1;
			(r.largePlant ? largeOther : smallOther) += 1;
			otherMwh += r.mwh;
		}
		// 0x27812853 values used by the Maxis plants: 1 coal, 2 hydrogen/fusion, 3 natural gas, 5 nuclear,
		// 6 oil, 7 solar, 8 waste to energy, 9 wind.
		set("UNS_COAL_COUNT", uns[1]);
		set("UNS_FUSION_COUNT", uns[2]);
		set("UNS_NAT_GAS_COUNT", uns[3]);
		set("UNS_FISSION_COUNT", uns[5]);
		set("UNS_OIL_COUNT", uns[6]);
		set("UNS_SOLAR_COUNT", uns[7]);
		set("UNS_WASTE_COUNT", uns[8]);
		set("UNS_WIND_COUNT", uns[9]);
		set("UNS_OTHER_COUNT", uns[0] + uns[4]);
		set("LARGE_OTHER_COUNT", largeOther);
		set("SMALL_OTHER_COUNT", smallOther);
		set("D_OTHER_POWER", otherMwh);
	}

	// ---- 10. load balancing
	const double demand = in.powerDemanded, exported = in.powerExported;
	set("MWH_DEMAND_TOTAL", demand + exported);
	set("MIN_P_POWER", std::ceil(demand * pMPercent + exported));
	set("MAX_I_POWER_A", demand * iMPercent);
	set("MAX_I_POWER_B", demand - get("MIN_P_POWER"));
	set("MAX_I_POWER", std::floor(std::min(get("MAX_I_POWER_A"), get("MAX_I_POWER_B"))));
	set("USED_I_POWER", std::min(get("MAX_I_POWER"), get("ALL_I_POWER")));
	set("UNUSED_I_POWER", LuaRound(get("ALL_I_POWER") - get("USED_I_POWER")));
	set("MAX_B_POWER_A", demand * bMPercent);
	set("MAX_B_POWER_B", demand - (get("MIN_P_POWER") + get("USED_I_POWER")));
	set("MAX_B_POWER", std::floor(std::min(get("MAX_B_POWER_A"), get("MAX_B_POWER_B"))));
	set("USED_B_POWER", std::min(get("MAX_B_POWER"), get("ALL_B_POWER")));
	set("UNUSED_B_POWER", LuaRound(get("ALL_B_POWER") - get("USED_B_POWER")));
	set("USED_P_POWER_A", get("MWH_DEMAND_TOTAL") - (get("USED_I_POWER") + get("USED_B_POWER")));
	set("USED_P_POWER_B", std::max(get("USED_P_POWER_A"), get("MIN_P_POWER")));
	set("USED_P_POWER", std::min(get("USED_P_POWER_B"), get("ALL_P_POWER")));
	set("UNUSED_P_POWER", LuaRound(get("ALL_P_POWER") - get("USED_P_POWER")));
	set("SHORT_P_POWER", std::max(get("MIN_P_POWER") - get("USED_P_POWER"), 0.0));
	set("I_PERCENT", get("USED_I_POWER") / std::max(get("ALL_I_POWER"), 1.0));
	set("B_PERCENT", get("USED_B_POWER") / std::max(get("ALL_B_POWER"), 1.0));
	set("P_PERCENT", get("USED_P_POWER") / std::max(get("ALL_P_POWER"), 1.0));
	set("DEMAND_PERCENT", (get("UNUSED_I_POWER") + get("UNUSED_B_POWER") + get("SHORT_P_POWER") + demand) / std::max(demand, 1.0));
}
