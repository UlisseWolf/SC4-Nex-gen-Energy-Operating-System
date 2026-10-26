#include "../src/NeonEnforcement.h"
// Build: g++ -std=c++20 tests/enforcement_test.cpp src/NeonEnforcement.cpp src/NeonGridModel.cpp -Isrc -o enforcement_test
#include <cstdio>
static void run(const char* title, std::initializer_list<NeonBuildingRecord> recs, NeonGridInputs in, NeonEnforcementSettings s = {})
{
	NeonGridModel m; uintptr_t k = 1;
	for (auto r : recs) m.AddBuilding(k++, r);
	m.Update(in);
	auto r = NeonEnforcement::Compute(m, in, s);
	std::printf("%-46s demand %7.0f LB %7.0f infra %7.0f deliver %7.0f deficit %7.0f strength %.2f blackout %7.0f factor %.3f\n",
		title, r.demand, r.loadBalanceMwh, r.infrastructureMwh, r.deliverableMwh, r.deficitMwh, r.strength, r.blackoutMwh, r.factor);
}
static NeonBuildingRecord B(uint32_t og, double kva, double mwh, int cls = 0) { NeonBuildingRecord r; r.groups = {og}; r.kva = kva; r.mwh = mwh; r.loadClass = (NeonLoadClass)cls; return r; }
int main()
{
	auto in = [](double demand, double produced, double pop) { NeonGridInputs i; i.powerDemanded = demand; i.powerProduced = produced; i.powerConsumed = demand; i.productionCapacity = produced; i.difficulty = 1; i.population = pop; return i; };
	run("coal only, no infrastructure, pop 1000", { B(0xBB3500C0, 15000, 6000, 2) }, in(1000, 6000, 1000));
	run("coal only, no infrastructure, pop 9000", { B(0xBB3500C0, 15000, 6000, 2) }, in(1000, 6000, 9000));
	run("coal only, no infrastructure, pop 20000", { B(0xBB3500C0, 15000, 6000, 2) }, in(1000, 6000, 20000));
	run("coal + gas + full infrastructure, pop 20000", { B(0xBB3500C0, 15000, 6000, 2), B(0xBB3500A0, 73750, 29500, 3),
		B(0xBB350120, 10000, 0), B(0xBB350121, 20000, 0), B(0xBB350122, 35000, 0), B(0xBB350126, 120000, 0), B(0xBB350038, 25000, 0), B(0xBB350038, 25000, 0), B(0xBB350038, 25000, 0),
		B(0xBB350026, 6000, 0) }, in(1000, 35500, 20000));
	run("same, 30000 MWh demand", { B(0xBB3500C0, 15000, 6000, 2), B(0xBB3500A0, 73750, 29500, 3),
		B(0xBB350120, 10000, 0), B(0xBB350121, 20000, 0), B(0xBB350122, 35000, 0), B(0xBB350126, 120000, 0), B(0xBB350038, 25000, 0), B(0xBB350038, 25000, 0), B(0xBB350038, 25000, 0),
		B(0xBB350026, 6000, 0) }, in(30000, 35500, 20000));
	NeonEnforcementSettings off; off.enabled = false;
	run("coal only, enforcement off", { B(0xBB3500C0, 15000, 6000, 2) }, in(1000, 6000, 20000), off);
	NeonEnforcementSettings lb; lb.infrastructure = false;
	run("coal only, load balance only", { B(0xBB3500C0, 15000, 6000, 2) }, in(1000, 6000, 20000), lb);
}
