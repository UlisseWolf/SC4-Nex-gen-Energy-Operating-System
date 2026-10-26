#include "NeonLua.h"
#include "NeonEnforcement.h"
#include "NeonGridModel.h"
#include "NeonLog.h"
#include "cISCLua.h"
#include "cRZAutoRefCount.h"
#include "SCLuaUtil.h"
#include "version.h"
#include <array>
#include <cstdio>
#include <string_view>

namespace
{
	NeonGridModel* spModel = nullptr;
	const std::vector<NeonGridModel::GroupRating>* spCatalog = nullptr;
	int sMissingDependencies = 0;
	void (*sBeforeUpdate)(void*) = nullptr;
	void* sBeforeUpdateContext = nullptr;

	double ArgNumber(cISCLua* lua, int index)
	{
		return lua->IsNumber(index) ? lua->ToNumber(index) : 0.0;
	}

	int32_t Update(lua_State* state)
	{
		cRZAutoRefCount<cISCLua> lua = SCLuaUtil::GetISCLuaFromFunctionState(state);
		if (sBeforeUpdate) sBeforeUpdate(sBeforeUpdateContext);
		NeonGridInputs in;
		in.powerDemanded      = ArgNumber(lua, 1);
		in.powerExported      = ArgNumber(lua, 2);
		in.powerImported      = ArgNumber(lua, 3);
		in.powerProduced      = ArgNumber(lua, 4);
		in.garbageToEnergy    = ArgNumber(lua, 5);
		in.powerConsumed      = ArgNumber(lua, 6);
		in.productionCapacity = ArgNumber(lua, 7);
		in.difficulty         = static_cast<int>(ArgNumber(lua, 8));
		in.population         = ArgNumber(lua, 9);
		const bool changed = spModel ? spModel->Update(in) : false;
		if (spModel) NeonEnforcement::Apply(*spModel, in);
		lua->PushBoolean(changed);
		return 1;
	}

	void WriteTable(cISCLua* lua, int tableIndex, const std::vector<std::pair<std::string, double>>& values)
	{
		if (!lua->IsTable(tableIndex)) return;
		for (const auto& [name, value] : values)
		{
			lua->PushString(name.c_str());
			lua->PushNumber(value);
			lua->SetTable(tableIndex);
		}
	}

	int32_t Export(lua_State* state)
	{
		cRZAutoRefCount<cISCLua> lua = SCLuaUtil::GetISCLuaFromFunctionState(state);
		if (spModel)
		{
			WriteTable(lua, 1, spModel->GridValues());
			WriteTable(lua, 2, spModel->CompanyValues());
			// Enforcement values for the query texts.
			const NeonEnforcementResult& e = NeonEnforcement::LastResult();
			WriteTable(lua, 1, { { "NEON_DELIVERABLE_POWER", e.deliverableMwh }, { "NEON_LOADBALANCE_POWER", e.loadBalanceMwh },
				{ "NEON_INFRASTRUCTURE_POWER", e.infrastructureMwh }, { "NEON_BLACKOUT_POWER", e.blackoutMwh },
				{ "NEON_ENFORCE_STRENGTH", e.strength }, { "NEON_ENFORCE_FACTOR", e.factor },
				{ "NEON_MISSING_DEPENDENCIES", static_cast<double>(sMissingDependencies) } });
			// Optional kva_rating / mwh_rating tables: values of the lots actually in the city.
			const bool kvaTable = lua->IsTable(3), mwhTable = lua->IsTable(4);
			std::vector<NeonGridModel::GroupRating> ratings;
			if (spCatalog) ratings = *spCatalog;                                   // every installed lot
			for (const auto& r : spModel->GroupRatings()) ratings.push_back(r);    // lots in the city win
			for (const NeonGridModel::GroupRating& r : ratings)
			{
				if (r.kva <= 0 && r.mwh <= 0) continue;
				char key[24];
				std::snprintf(key, sizeof(key), "ID_%08X", r.group);
				if (kvaTable) { lua->PushString(key); lua->PushNumber(r.kva); lua->SetTable(3); }
				if (mwhTable)
				{
					// Waste-to-energy: the Lua keeps the nominal value in ID_xxx_A and the live output in ID_xxx.
					if (r.wasteToEnergy) std::snprintf(key, sizeof(key), "ID_%08X_A", r.group);
					lua->PushString(key); lua->PushNumber(r.mwh); lua->SetTable(4);
				}
			}
		}
		return 0;
	}

	int32_t Grid(lua_State* state)
	{
		cRZAutoRefCount<cISCLua> lua = SCLuaUtil::GetISCLuaFromFunctionState(state);
		double value = 0;
		const char* type = lua->IsString(1) ? lua->ToString(1) : nullptr;
		if (spModel && type && type[0] && spModel->GridReturn(type[0], value)) lua->PushNumber(value);
		else lua->PushNil();
		return 1;
	}

	int32_t Count(lua_State* state)
	{
		cRZAutoRefCount<cISCLua> lua = SCLuaUtil::GetISCLuaFromFunctionState(state);
		lua->PushNumber(spModel ? spModel->CountOfGroup(static_cast<uint32_t>(ArgNumber(lua, 1))) : 0);
		return 1;
	}

	int32_t Installed(lua_State* state)
	{
		cRZAutoRefCount<cISCLua> lua = SCLuaUtil::GetISCLuaFromFunctionState(state);
		const uint32_t og = static_cast<uint32_t>(ArgNumber(lua, 1));
		bool found = false;
		if (spCatalog)
			for (const auto& r : *spCatalog) if (r.group == og) { found = true; break; }
		lua->PushBoolean(found);
		return 1;
	}

	int32_t Version(lua_State* state)
	{
		cRZAutoRefCount<cISCLua> lua = SCLuaUtil::GetISCLuaFromFunctionState(state);
		lua->PushString(NEON_DLL_VERSION_STR);
		return 1;
	}
}

void NeonLua::SetCatalog(const std::vector<NeonGridModel::GroupRating>* catalog) { spCatalog = catalog; }
void NeonLua::SetMissingDependencies(int count) { sMissingDependencies = count; }
void NeonLua::SetBeforeUpdate(void (*callback)(void*), void* context) { sBeforeUpdate = callback; sBeforeUpdateContext = context; }

bool NeonLua::Register(cISCLua* lua, NeonGridModel* model)
{
	if (!lua) return false;
	spModel = model;

	// Make sure the global table exists; NEON_LUA declares it with "if neon == nil then neon = {} end".
	lua->GetGlobal("neon");
	const bool exists = lua->IsTable(-1);
	lua->Pop(1);
	if (!exists)
	{
		lua->NewTable();
		lua->SetGlobal("neon");
	}

	constexpr std::array<std::pair<std::string_view, lua_CFunction>, 6> functions = { {
		{ "update", Update }, { "export", Export }, { "grid", Grid }, { "count", Count }, { "version", Version },
		{ "installed", Installed } } };

	bool ok = true;
	for (const auto& [name, fn] : functions)
	{
		const auto status = SCLuaUtil::RegisterLuaFunction(lua, "neon", name, fn);
		if (status != SCLuaUtil::RegisterLuaFunctionStatus::Ok)
		{
			NeonLog::Write(NeonLog::Level::Error, "Could not register neon.%.*s (status %d)",
				static_cast<int>(name.size()), name.data(), static_cast<int>(status));
			ok = false;
		}
	}
	return ok;
}
