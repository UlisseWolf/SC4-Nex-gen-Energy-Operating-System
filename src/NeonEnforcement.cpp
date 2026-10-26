#include "NeonEnforcement.h"
#include "NeonIds.h"
#include <algorithm>
#include <cmath>

namespace
{
	double Value(const NeonGridModel& model, const char* name)
	{
		double v = 0;
		model.TryGetValue(name, v);
		return v;
	}
}

NeonEnforcementResult NeonEnforcement::Compute(const NeonGridModel& m, const NeonGridInputs& in, const NeonEnforcementSettings& s)
{
	NeonEnforcementResult r;
	r.demand = std::max(Value(m, "MWH_DEMAND_TOTAL"), 0.0);
	const double produced = std::max(in.powerProduced, 0.0);

	// Load balance: what the Base / Intermediate / Peak shares can serve (imports are part of the Peak share).
	r.loadBalanceMwh = Value(m, "USED_I_POWER") + Value(m, "USED_B_POWER") + Value(m, "USED_P_POWER");

	// Infrastructure chain on the nominal plant output, then applied to the real production:
	//   large plants + imports -> transmission stations -> distribution substations -> transformers -> buildings
	//   small plants           ->                          distribution substations -> transformers -> buildings
	//   generators deliver household voltage directly (no kVA, as in the NEON Lua).
	const double kvaPerMwh = NeonIds::kKvaPerMwh;
	const double large = Value(m, "LARGE_I_POWER") + Value(m, "LARGE_B_POWER") + Value(m, "LARGE_P_POWER");
	const double small = Value(m, "SMALL_I_POWER") + Value(m, "SMALL_B_POWER") + Value(m, "SMALL_P_POWER");
	const double gens = Value(m, "GENERATOR_I_POWER") + Value(m, "GENERATOR_B_POWER") + Value(m, "GENERATOR_P_POWER");
	const double imported = std::max(in.powerImported, 0.0);
	const double transmission = Value(m, "TRANSMISSION_RATING") / kvaPerMwh;
	const double distribution = Value(m, "DISTRIBUTION_RATING") / kvaPerMwh;
	const double transformers = Value(m, "TRANSFORMER_RATING") / kvaPerMwh;
	const double nominal = large + small + gens + imported;
	if (nominal > 0)
	{
		const double throughTransmission = std::min(large + imported, transmission);
		const double throughDistribution = std::min(throughTransmission + small, distribution);
		const double toBuildings = std::min(throughDistribution, transformers) + gens;
		// The nominal ratings and the real production differ (age, funding): scale the capacity down when the plants
		// produce less than their rating, never up (the game can count plants NEON does not, for example unsupported lots).
		r.infrastructureMwh = toBuildings * std::min(1.0, (produced + imported) / nominal);
	}

	if (s.loadBalance && s.infrastructure) r.deliverableMwh = std::min(r.loadBalanceMwh, r.infrastructureMwh);
	else if (s.loadBalance)                r.deliverableMwh = r.loadBalanceMwh;
	else if (s.infrastructure)             r.deliverableMwh = r.infrastructureMwh;
	else                                   r.deliverableMwh = r.demand;

	r.deficitMwh = std::max(r.demand - r.deliverableMwh, 0.0);

	const double span = std::max(s.fullPopulation - s.startPopulation, 1.0);
	r.strength = std::clamp((in.population - s.startPopulation) / span, 0.0, 1.0);
	if (!s.enabled) r.strength = 0;
	r.blackoutMwh = r.deficitMwh * r.strength;

	// The game hands out 1.1 x production. Scale it so it hands out (demand - blackout), never more than vanilla.
	if (r.blackoutMwh > 0 && produced > 0)
	{
		const double allowed = r.demand - r.blackoutMwh;
		r.factor = std::clamp(allowed / (produced * 1.1), 0.0, 1.0);
	}
	return r;
}
