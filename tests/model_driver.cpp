// Host-side test driver: reads a city description on stdin, prints every computed NEON value.
//   B <group hex> <kVA> <MWh> [class 0-3]   one building
//   I <demand> <exported> <imported> <produced> <g2e> <consumed> <capacity> <difficulty>
#include "../src/NeonGridModel.h"
#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>
int main()
{
	NeonGridModel model;
	NeonGridInputs in;
	std::string line;
	uintptr_t key = 1;
	while (std::getline(std::cin, line))
	{
		std::istringstream s(line);
		std::string tag; s >> tag;
		if (tag == "B")
		{
			std::string og; double kva, mwh; int cls = 0;
			s >> og >> kva >> mwh >> cls;
			NeonBuildingRecord r; r.groups.push_back(std::stoul(og, nullptr, 16));
			r.kva = kva; r.mwh = mwh; r.loadClass = static_cast<NeonLoadClass>(cls);
			model.AddBuilding(key++, r);
		}
		else if (tag == "I")
		{
			s >> in.powerDemanded >> in.powerExported >> in.powerImported >> in.powerProduced
			  >> in.garbageToEnergy >> in.powerConsumed >> in.productionCapacity >> in.difficulty;
		}
	}
	model.Update(in);
	for (auto& [n, v] : model.GridValues()) std::printf("G %s %.10g\n", n.c_str(), v);
	for (auto& [n, v] : model.CompanyValues()) std::printf("C %s %.10g\n", n.c_str(), v);
	for (char c : std::string("TDXIBP")) { double v; model.GridReturn(c, v); std::printf("R %c %.10g\n", c, v); }
}
