// Host-side checks of the exemplar rules on the CAM coal plant and on the three coal patches.
#include "../src/NeonRules.h"
#include "../src/NeonIds.h"
#include <cassert>
#include <cstdio>
using namespace NeonIds;
int main()
{
	// CAM Up64x64_CoalPowerPlant: NEON Coal group, power 7500, MWh 7500, kVA 18750, no load class.
	NeonRules::ExemplarFacts cam{ { 0x1004, 0x1400, kOgCoal }, 7500.0, 18750.0, 7500.0 };
	NeonRules::Fill fill;
	auto p = NeonRules::CheckGeneratingPlant(cam, fill);
	assert(p.size() == 1 && !fill.mwh && !fill.kva);        // only "missing load class"
	std::printf("CAM coal: %s\n", p[0].c_str());

	// Same plant with Base Load and no ratings: the DLL fills MWh 7500 and kVA 18750.
	NeonRules::ExemplarFacts bare{ { 0x1004, 0x1400, kOgCoal, kOgBaseLoad }, 7500.0, std::nullopt, std::nullopt };
	fill = {};
	p = NeonRules::CheckGeneratingPlant(bare, fill);
	assert(p.empty() && fill.mwh && *fill.mwh == 7500 && fill.kva && *fill.kva == 18750);

	// Chicago Union Station patch: MWh 5200 / kVA 13000 but the plant produces less (example 1250).
	NeonRules::ExemplarFacts chicago{ { 0x1004, 0x1400, kOgCoal, kOgBaseLoad, 0xBB3501C0 }, 1250.0, 13000.0, 5200.0 };
	fill = {};
	p = NeonRules::CheckGeneratingPlant(chicago, fill);
	for (auto& s : p) std::printf("Chicago: %s\n", s.c_str());
	assert(p.size() == 1);                                   // MWh differs from power produced (kVA = 2.5 x 5200 is consistent)

	// Records: legacy group keeps its bucket, NEON-only plant goes to the large/small bucket by MWh.
	auto r = NeonRules::MakeRecord(bare);
	assert(r.kva == 18750 && r.mwh == 7500 && r.loadClass == NeonLoadClass::Base);
	assert(NeonGridModel::VirtualLegacyGroup(r) == 0xBB3501C0);  // 7500 < 8000 -> small (placeholder rule)
	NeonRules::ExemplarFacts nuke{ { kOgFission, kOgBaseLoad }, 43400.0, std::nullopt, std::nullopt };
	r = NeonRules::MakeRecord(nuke);
	assert(r.kva == 108500 && NeonGridModel::VirtualLegacyGroup(r) == 0xBB350078);
	std::puts("rules: all checks passed");
}
