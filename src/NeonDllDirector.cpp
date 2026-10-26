// NEON DLL - plugin entry point.
//
//  * Exemplar check (needs SC4ResourceLoadingHooks.dll): when a NEON generating plant's exemplar is loaded,
//    missing MWh / kVA ratings are filled (MWh = power produced, kVA = 2.5 x MWh) and every problem is logged,
//    including a missing load class group, which NEON requires in the exemplar.
//  * Grid model: every building with a NEON or legacy 0xBB35xxxx occupant group is tracked as it enters or
//    leaves the city, so the Lua no longer calls sc4game.automata.get_source_building_count 1,183 times.
//  * Lua bridge: the "neon" table used by NEON_LUA (see NeonLua.h).
#include "NeonEnforcement.h"
#include "NeonGridModel.h"
#include "NeonIds.h"
#include "NeonLog.h"
#include "NeonLua.h"
#include "NeonRules.h"
#include "version.h"

#include "cIExemplarLoadHookServer.h"
#include "cIExemplarLoadHookTarget.h"
#include "cIGZCOM.h"
#include "cIGZFrameWork.h"
#include "cIGZMessage2Standard.h"
#include "cIGZMessageServer2.h"
#include "cIGZMessageTarget2.h"
#include "cIGZVariant.h"
#include "cISC4AdvisorSystem.h"
#include "cISC4BuildingOccupant.h"
#include "cISC4City.h"
#include "cISC4Occupant.h"
#include "cISC4OccupantManager.h"
#include "cISCProperty.h"
#include "cISCPropertyHolder.h"
#include "cISCResExemplar.h"
#include "cRZAutoRefCount.h"
#include "cRZBaseString.h"
#include "cRZCOMDllDirector.h"
#include "GZCLSIDDefs.h"
#include "GZServPtrs.h"
#include "SCPropertyUtil.h"

#include <Windows.h>
#include <algorithm>
#include <cstdio>
#include <optional>
#include <unordered_map>
#include <unordered_set>
#include <string>

// Random, never reuse.
static constexpr uint32_t kNeonDirectorID = 0x4E30E2B1;
static constexpr uint32_t kOccupantTypeBuilding = 0x278128A0;

namespace
{
	std::optional<double> ReadNumber(const cISCPropertyHolder* holder, uint32_t id)
	{
		uint32_t value = 0;
		if (holder && SCPropertyUtil::GetPropertyValue(holder, id, value)) return static_cast<double>(value);
		float f = 0;
		if (holder && SCPropertyUtil::GetPropertyValue(holder, id, f)) return static_cast<double>(f);
		return std::nullopt;
	}

	std::vector<uint32_t> ReadGroups(const cISCPropertyHolder* holder)
	{
		std::vector<uint32_t> groups;
		const cISCProperty* property = holder ? holder->GetProperty(NeonIds::kOccupantGroups) : nullptr;
		const cIGZVariant* value = property ? property->GetPropertyValue() : nullptr;
		if (value && value->GetType() == cIGZVariant::Type::Uint32Array)
		{
			const uint32_t* data = value->RefUint32();
			groups.assign(data, data + value->GetCount());
		}
		else if (value && value->GetType() == cIGZVariant::Type::Uint32)
		{
			groups.push_back(value->GetValUint32());
		}
		return groups;
	}

	std::string ExemplarName(const cISCPropertyHolder* holder)
	{
		cRZBaseString name;
		if (holder && holder->GetProperty(NeonIds::kExemplarName, name)) return name.ToChar();
		return {};
	}
}

class NeonDllDirector final : public cRZCOMDllDirector, public cIGZMessageTarget2, public cIExemplarLoadHookTarget
{
public:
	uint32_t GetDirectorID() const override { return kNeonDirectorID; }

	bool QueryInterface(uint32_t riid, void** ppvObj) override
	{
		if (riid == GZCLSID::kcIGZMessageTarget2)
		{
			*ppvObj = static_cast<cIGZMessageTarget2*>(this);
			AddRef();
			return true;
		}
		if (riid == GZIID_cIExemplarLoadHookTarget)
		{
			*ppvObj = static_cast<cIExemplarLoadHookTarget*>(this);
			AddRef();
			return true;
		}
		return cRZCOMDllDirector::QueryInterface(riid, ppvObj);
	}
	uint32_t AddRef() override { return cRZCOMDllDirector::AddRef(); }
	uint32_t Release() override { return cRZCOMDllDirector::Release(); }

	bool OnStart(cIGZCOM* pCOM) override
	{
		NeonLog::Open();
		NeonLog::Write(NeonLog::Level::Info, "NEON DLL " NEON_DLL_VERSION_STR);
		NeonEnforcement::LoadSettings();
		cIGZFrameWork* const framework = pCOM->FrameWork();
		if (framework->GetState() < cIGZFrameWork::kStatePreAppInit) framework->AddHook(this);
		else PreAppInit();
		return true;
	}

	bool PreAppInit() override
	{
		// The exemplar load callback must be registered before the game loads the building exemplars.
		cRZAutoRefCount<cIExemplarLoadHookServer> server;
		if (GZCOM()->GetClassObject(GZCLSID_cIExemplarLoadHookServer, GZIID_cIExemplarLoadHookServer, server.AsPPVoid()))
		{
			server->AddLoadNotification(this);
			NeonLog::Write(NeonLog::Level::Info, "Exemplar check enabled.");
		}
		else
		{
			NeonLog::Write(NeonLog::Level::Warning,
				"SC4ResourceLoadingHooks.dll not found: exemplars are not checked, ratings are derived at runtime only.");
		}
		return true;
	}

	bool PostAppInit() override
	{
		NeonEnforcement::InstallPatch();
		cIGZMessageServer2Ptr ms2;
		if (ms2)
		{
			for (uint32_t id : { NeonIds::kMsgPostCityInit, NeonIds::kMsgPreCityShutdown,
				NeonIds::kMsgOccupantInserted, NeonIds::kMsgOccupantRemoved })
			{
				ms2->AddNotification(this, id);
			}
		}
		return true;
	}

	bool DoMessage(cIGZMessage2* message) override
	{
		auto* standard = static_cast<cIGZMessage2Standard*>(message);
		switch (message->GetType())
		{
		case NeonIds::kMsgPostCityInit: PostCityInit(static_cast<cISC4City*>(standard->GetVoid1())); break;
		case NeonIds::kMsgPreCityShutdown: model.Clear(); NeonEnforcement::Reset(); city = nullptr; break;
		case NeonIds::kMsgOccupantInserted: AddOccupant(static_cast<cISC4Occupant*>(standard->GetVoid1())); break;
		case NeonIds::kMsgOccupantRemoved:
			model.RemoveBuilding(reinterpret_cast<uintptr_t>(standard->GetVoid1()));
			break;
		}
		return true;
	}

	// cIExemplarLoadHookTarget: runs after SC4ResourceLoadingHooks has applied the exemplar patches.
	void ExemplarLoaded(const char* const, const cGZPersistResourceKey& key, cISCResExemplar* exemplar) override
	{
		cISCPropertyHolder* holder = exemplar ? exemplar->AsISCPropertyHolder() : nullptr;
		if (!holder) return;

		NeonRules::ExemplarFacts facts;
		facts.groups = ReadGroups(holder);
		facts.powerProduced = ReadNumber(holder, NeonIds::kPowerProduced);
		const bool neon = NeonRules::HasAnyNeonGroup(facts.groups);
		if (!neon && !(facts.powerProduced && *facts.powerProduced > 0)) return;
		facts.kva = ReadNumber(holder, NeonIds::kKvaRating);
		facts.mwh = ReadNumber(holder, NeonIds::kMwhRating);
		facts.plantType = ReadNumber(holder, NeonIds::kPowerPlantType);

		NeonRules::Fill fill;
		std::vector<std::string> problems;
		if (NeonRules::IsGeneratingPlant(facts.groups))
		{
			problems = NeonRules::CheckGeneratingPlant(facts, fill);
			if (fill.mwh) { holder->AddProperty(NeonIds::kMwhRating, *fill.mwh, false); facts.mwh = *fill.mwh; }
			if (fill.kva) { holder->AddProperty(NeonIds::kKvaRating, *fill.kva, false); facts.kva = *fill.kva; }
		}
		// Nominal values of the building type (the exemplar instance is the building type of the occupants).
		// The occupant's own properties can differ: the game changes a plant's power output while it runs.
		exemplarFacts[key.instance] = facts;
		if (!neon) return;
		{
			// Catalog of the installed NEON lots: what kva_rating / mwh_rating and neon.installed() report.
			const NeonBuildingRecord record = NeonRules::MakeRecord(facts);
			catalogLots[key.instance] = CatalogLot{ NeonGridModel::CountedGroups(record), record.kva, record.mwh };
		}

		// The game loads some exemplars more than once: report each one only the first time.
		const uint64_t id = (static_cast<uint64_t>(key.group) << 32) | key.instance;
		if (!reportedExemplars.insert(id).second) return;

		const std::string name = ExemplarName(holder);
		for (const std::string& p : problems)
		{
			NeonLog::Write(NeonLog::Level::Warning, "0x%08X 0x%08X 0x%08X %s: %s",
				key.type, key.group, key.instance, name.c_str(), p.c_str());
		}
		if (!problems.empty())
		{
			std::string groups;
			char hex[12];
			for (uint32_t og : facts.groups) { std::snprintf(hex, sizeof(hex), " 0x%08X", og); groups += hex; }
			NeonLog::Write(NeonLog::Level::Info, "    occupant groups:%s | power produced %.0f, MWh %.0f, kVA %.0f",
				groups.c_str(), facts.powerProduced.value_or(-1), facts.mwh.value_or(-1), facts.kva.value_or(-1));
		}
		if (fill.mwh || fill.kva)
		{
			NeonLog::Write(NeonLog::Level::Info, "0x%08X 0x%08X 0x%08X %s: filled%s%s",
				key.type, key.group, key.instance, name.c_str(), fill.mwh ? " MWh" : "", fill.kva ? " kVA" : "");
		}
	}

private:
	void PostCityInit(cISC4City* newCity)
	{
		city = newCity;
		model.Clear();
		buildingsSeen = 0;
		if (!city) return;

		// Buildings already in a loaded city do not raise "occupant inserted": count them once here.
		if (cISC4OccupantManager* occupants = city->GetOccupantManager())
		{
			occupants->IterateOccupants(&NeonDllDirector::CountExisting, this, nullptr, nullptr, kOccupantTypeBuilding);
		}
		NeonLog::Write(NeonLog::Level::Info, "City loaded: %u buildings, %u counted by NEON.",
			buildingsSeen, static_cast<unsigned>(model.BuildingCount()));
		BuildCatalog();
		NeonLua::SetBeforeUpdate(&NeonDllDirector::BeforeUpdate, this);
		lastResync = GetTickCount();

		cISC4AdvisorSystem* advisors = city->GetAdvisorSystem();
		if (!advisors || !NeonLua::Register(advisors->GetScriptingContext(), &model))
		{
			NeonLog::Write(NeonLog::Level::Error, "The neon Lua table could not be registered: NEON_LUA keeps its Lua fallback.");
		}
	}

	struct CatalogLot { std::vector<uint32_t> groups; double kva; double mwh; };

	// Average kVA / MWh of the installed lots of every legacy group, and which infrastructure stages exist.
	void BuildCatalog()
	{
		struct Sum { double kva = 0, mwh = 0; uint32_t n = 0; };
		std::unordered_map<uint32_t, Sum> sums;
		for (const auto& [instance, lot] : catalogLots)
		{
			for (uint32_t og : lot.groups) { Sum& s = sums[og]; s.kva += lot.kva; s.mwh += lot.mwh; s.n++; }
		}
		std::vector<uint32_t> waste = NeonGridModel::GroupsOfSum("LARGE_WASTE_COUNT");
		for (uint32_t og : NeonGridModel::GroupsOfSum("SMALL_WASTE_COUNT")) waste.push_back(og);
		catalog.clear();
		for (const auto& [og, s] : sums)
		{
			const bool isWaste = std::find(waste.begin(), waste.end(), og) != waste.end();
			catalog.push_back({ og, s.kva / s.n, s.mwh / s.n, isWaste });
		}
		auto installed = [&](std::initializer_list<const char*> buckets)
		{
			unsigned lots = 0;
			for (const char* b : buckets)
				for (uint32_t og : NeonGridModel::GroupsOfSum(b))
					if (auto it = sums.find(og); it != sums.end()) lots += it->second.n;
			return lots;
		};
		const unsigned transformers = installed({ "TRANSFORMER_RATING" });
		const unsigned distribution = installed({ "DISTRIBUTE_RATING_A", "DISTRIBUTE_RATING_B" });
		const unsigned transmission = installed({ "TRANSMISSION_RATING" });
		NeonLua::SetCatalog(&catalog);
		// Transformers, distribution substations and transmission stations are required dependencies of NEON.
		const int missing = (transformers == 0) + (distribution == 0) + (transmission == 0);
		NeonLua::SetMissingDependencies(missing);
		NeonLog::Write(NeonLog::Level::Info,
			"Installed NEON lots: %u building types; transformers %u, distribution substations %u, transmission stations %u.",
			static_cast<unsigned>(catalogLots.size()), transformers, distribution, transmission);
		if (missing)
		{
			NeonLog::Write(NeonLog::Level::Error,
				"Required dependencies missing:%s%s%s. Install them (see the NEON readme): without them the grid cannot carry power.",
				transformers ? "" : " transformers", distribution ? "" : " distribution substations",
				transmission ? "" : " transmission stations");
		}
	}

	// Safety net: every 10 s of play (at the next neon.update) the city's buildings are listed again and the model
	// is corrected if an "occupant inserted / removed" message was missed. Differences are written to the log.
	static void BeforeUpdate(void* context)
	{
		auto* self = static_cast<NeonDllDirector*>(context);
		const DWORD now = GetTickCount();
		if (now - self->lastResync < 10000) return;
		self->lastResync = now;
		self->Resync();
	}

	void Resync()
	{
		if (!city) return;
		cISC4OccupantManager* occupants = city->GetOccupantManager();
		if (!occupants) return;
		const std::vector<uintptr_t> before = model.BuildingKeys();
		resyncSeen.clear();
		occupants->IterateOccupants(&NeonDllDirector::ResyncOne, this, nullptr, nullptr, kOccupantTypeBuilding);
		unsigned removed = 0, added = 0;
		for (uintptr_t key : before)
		{
			if (!resyncSeen.count(key)) { model.RemoveBuilding(key); removed++; }
		}
		const std::unordered_set<uintptr_t> had(before.begin(), before.end());
		for (uintptr_t key : model.BuildingKeys()) if (!had.count(key)) added++;
		if (added || removed)
		{
			NeonLog::Write(NeonLog::Level::Warning, "Resync: %u NEON buildings were missing from the count, %u were counted but are gone.",
				added, removed);
		}
	}

	static bool ResyncOne(cISC4Occupant* occupant, void* context)
	{
		auto* self = static_cast<NeonDllDirector*>(context);
		self->AddOccupant(occupant);
		self->resyncSeen.insert(reinterpret_cast<uintptr_t>(occupant));
		return true;
	}

	static bool CountExisting(cISC4Occupant* occupant, void* context)
	{
		auto* self = static_cast<NeonDllDirector*>(context);
		self->buildingsSeen++;
		self->AddOccupant(occupant);
		return true;
	}

	void AddOccupant(cISC4Occupant* occupant)
	{
		if (!occupant || occupant->GetType() != kOccupantTypeBuilding) return;

		// Occupant groups are read from the OccupantGroups property (0xAA1DD396), not with
		// cISC4Occupant::GetOccupantGroups: that one fills a std::set built with the game's own (2003) STL,
		// whose memory layout differs from the std::set of current Visual Studio and crashed the game.
		// Nominal values from the building's exemplar (cached when it was loaded); the occupant's own
		// properties are only used when SC4ResourceLoadingHooks.dll is missing.
		NeonRules::ExemplarFacts facts;
		uint32_t buildingType = 0;
		bool fromExemplar = false;
		{
			cRZAutoRefCount<cISC4BuildingOccupant> building;
			if (occupant->QueryInterface(GZIID_cISC4BuildingOccupant, building.AsPPVoid()))
			{
				buildingType = building->GetBuildingType();
				if (auto it = exemplarFacts.find(buildingType); it != exemplarFacts.end()) { facts = it->second; fromExemplar = true; }
			}
		}
		if (!fromExemplar)
		{
			// Occupant groups are read from the OccupantGroups property (0xAA1DD396), not with
			// cISC4Occupant::GetOccupantGroups: that one fills a std::set built with the game's own (2003) STL,
			// whose memory layout differs from the std::set of current Visual Studio and crashed the game.
			const cISCPropertyHolder* holder = occupant->AsPropertyHolder();
			if (!holder) return;
			facts.groups = ReadGroups(holder);
			facts.powerProduced = ReadNumber(holder, NeonIds::kPowerProduced);
			facts.kva = ReadNumber(holder, NeonIds::kKvaRating);
			facts.mwh = ReadNumber(holder, NeonIds::kMwhRating);
			facts.plantType = ReadNumber(holder, NeonIds::kPowerPlantType);
		}

		NeonBuildingRecord record;
		if (NeonRules::HasAnyNeonGroup(facts.groups))
		{
			record = NeonRules::MakeRecord(facts);
		}
		else if (facts.powerProduced && *facts.powerProduced > 0 && facts.plantType && *facts.plantType > 0)
		{
			// A power plant NEON does not support: only counted in the UNS_* values of the office query.
			// Buildings with a little "power produced" but no power plant type (parks, landmarks...) are not plants.
			record = NeonRules::MakeUnsupportedRecord(facts);
		}
		else
		{
			return;
		}

		if (loggedBuildingTypes.insert(buildingType).second)
		{
			std::string groups;
			char hex[12];
			for (uint32_t og : facts.groups) { std::snprintf(hex, sizeof(hex), " 0x%08X", og); groups += hex; }
			static const char* const classes[] = { "none", "Intermediate", "Base", "Peak" };
			const bool plant = record.unsupportedPlantType >= 0 || NeonRules::IsGeneratingPlant(facts.groups);
			NeonLog::Write(NeonLog::Level::Info, "Building type 0x%08X (%s): MWh %.0f, kVA %.0f, class %s%s%s | groups:%s",
				buildingType, fromExemplar ? "exemplar" : "occupant", record.mwh, record.kva,
				classes[static_cast<int>(record.loadClass)], plant ? (record.largePlant ? ", large" : ", small") : "",
				record.unsupportedPlantType >= 0 ? ", not supported by NEON" : "", groups.c_str());
		}
		model.AddBuilding(reinterpret_cast<uintptr_t>(occupant), std::move(record));
	}

	NeonGridModel model;
	cISC4City* city = nullptr;
	unsigned buildingsSeen = 0;
	std::unordered_set<uint64_t> reportedExemplars;
	std::unordered_set<uint32_t> loggedBuildingTypes;
	std::unordered_map<uint32_t, NeonRules::ExemplarFacts> exemplarFacts;
	std::unordered_map<uint32_t, CatalogLot> catalogLots;
	std::unordered_set<uintptr_t> resyncSeen;
	DWORD lastResync = 0;
	std::vector<NeonGridModel::GroupRating> catalog;
};

cRZCOMDllDirector* RZGetCOMDllDirector()
{
	static NeonDllDirector sDirector;
	return &sDirector;
}
