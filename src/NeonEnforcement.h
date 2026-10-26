// NEON DLL - makes the NEON grid limits real in the game's power simulation.
//
// cSC4PowerSimulator::UpdatePowerGrid (0x006EE110) computes the power a grid can hand out as
//     production x 1.1        (fmul dword ptr [0x00AB2888], the float -1.1, used only there)
// and then powers 8x8 blocks in random order until that amount runs out: the blocks left over have no power.
// The DLL rescales that constant, so the game hands out only the power NEON says can be delivered:
//   * load balance: Base / Intermediate / Peak shares (USED_I + USED_B + USED_P of the grid model);
//   * infrastructure: transmission -> distribution -> transformers, in MWh = kVA / 2.5;
//   * both reduced gradually with the population (StartPopulation .. FullPopulation) so new cities can grow.
#pragma once
#include "NeonGridModel.h"

struct NeonEnforcementSettings
{
	bool enabled = true;          // SC4NEON.ini [Enforcement] Enabled
	bool loadBalance = true;      // LoadBalance
	bool infrastructure = true;   // Infrastructure
	double startPopulation = 3000;  // below: no limits
	double fullPopulation = 15000;  // above: full limits (linear in between)
};

struct NeonEnforcementResult
{
	double demand = 0;            // demand + exports (MWh)
	double loadBalanceMwh = 0;    // power the Base / Intermediate / Peak balance can serve
	double infrastructureMwh = 0; // power the transmission / distribution / transformer chain can carry
	double deliverableMwh = 0;    // the lower of the two (only the enabled limits)
	double deficitMwh = 0;        // demand that cannot be served (before the population ramp)
	double strength = 0;          // 0 .. 1 from the population ramp
	double blackoutMwh = 0;       // deficit x strength: what the game will not hand out
	double factor = 1;            // multiplier of the game's 1.1 x production (1 = vanilla)
};

namespace NeonEnforcement
{
	// Pure calculation (no game access): used by the DLL and by the tests.
	NeonEnforcementResult Compute(const NeonGridModel& model, const NeonGridInputs& in, const NeonEnforcementSettings& s);

	// Game side (Windows only, see NeonEnforcementPatch.cpp).
	void LoadSettings();                       // reads SC4NEON.ini next to the DLL, writes it with defaults if missing
	const NeonEnforcementSettings& Settings();
	bool InstallPatch();                       // checks the exe (1.1.641) before touching anything
	void Apply(const NeonGridModel& model, const NeonGridInputs& in); // after each neon.update
	void Reset();                              // back to the vanilla 1.1 (city closed)
	const NeonEnforcementResult& LastResult();
}
