// NEON DLL - the "neon" Lua table used by NEON_LUA.
#pragma once
class cISCLua;
#include "NeonGridModel.h"

namespace NeonLua
{
	// Creates the global "neon" table if needed and registers:
	//   neon.update(demand, exported, imported, produced, g2e, consumed, capacity, difficulty) -> changed (bool)
	//   neon.export(grid_logic_var, power_company_buildings [, kva_rating, mwh_rating])
	//       copies every computed value into the tables; kva_rating / mwh_rating get the values of the lots in the city
	//   neon.grid(ret_type)                                     same as run_grid_balance_variables(ret_type)
	//   neon.count(occupant_group)                              buildings counted under a legacy group
	//   neon.version()                                          DLL version string
	//   neon.installed(occupant_group)                          true if a lot of that group is in the Plugins
	bool Register(cISCLua* lua, NeonGridModel* model);

	// Ratings of every installed NEON lot (by legacy group), written into kva_rating / mwh_rating by neon.export
	// before the values of the lots in the city. Also answers neon.installed(group).
	void SetCatalog(const std::vector<NeonGridModel::GroupRating>* catalog);

	// Number of required infrastructure kinds (transformers, distribution, transmission) with no lot installed;
	// exported as grid_logic_var.NEON_MISSING_DEPENDENCIES.
	void SetMissingDependencies(int count);

	// Called at the start of every neon.update (the DLL uses it to re-check the buildings of the city now and then).
	void SetBeforeUpdate(void (*callback)(void* context), void* context);
}
