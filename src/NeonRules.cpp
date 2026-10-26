#include "NeonRules.h"
#include "NeonIds.h"
#include <algorithm>
#include <cmath>
#include <cstdio>

using namespace NeonIds;

namespace
{
	constexpr uint32_t kFuelGroups[] = {
		kOgCoal, kOgOil, kOgBiomass, kOgNaturalGas, kOgFission, kOgFusion, kOgGeothermal,
		kOgSolar, kOgMicrowave, kOgTidal, kOgWasteToEnergy, kOgHydro, kOgWind };
	constexpr uint32_t kOtherNeonGroups[] = {
		kOgGenerators, kOgAuxiliary, kOgPowerStorage, kOgHvTransformers, kOgMvTransformers, kOgLvTransformers,
		kOgIntermediate, kOgBaseLoad, kOgPeak };

	bool Contains(const std::vector<uint32_t>& v, uint32_t og) { return std::find(v.begin(), v.end(), og) != v.end(); }

	std::string Format(const char* fmt, double a, double b = 0)
	{
		char buf[256];
		std::snprintf(buf, sizeof(buf), fmt, a, b);
		return buf;
	}
}

bool NeonRules::IsGenerationFuel(uint32_t og)
{
	return std::find(std::begin(kFuelGroups), std::end(kFuelGroups), og) != std::end(kFuelGroups);
}

bool NeonRules::IsNeonGroup(uint32_t og)
{
	return IsGenerationFuel(og)
		|| std::find(std::begin(kOtherNeonGroups), std::end(kOtherNeonGroups), og) != std::end(kOtherNeonGroups)
		|| IsLegacyGroup(og);
}

bool NeonRules::HasAnyNeonGroup(const std::vector<uint32_t>& groups)
{
	return std::any_of(groups.begin(), groups.end(), IsNeonGroup);
}

bool NeonRules::IsGeneratingPlant(const std::vector<uint32_t>& groups)
{
	const bool equipment = Contains(groups, kOgPowerStorage) || Contains(groups, kOgHvTransformers)
		|| Contains(groups, kOgMvTransformers) || Contains(groups, kOgLvTransformers) || Contains(groups, kOgAuxiliary);
	if (equipment) return false;
	return Contains(groups, kOgGenerators) || std::any_of(groups.begin(), groups.end(), IsGenerationFuel);
}

NeonLoadClass NeonRules::LoadClassFromGroups(const std::vector<uint32_t>& groups, int& classGroupCount)
{
	classGroupCount = 0;
	NeonLoadClass result = NeonLoadClass::None;
	if (Contains(groups, kOgIntermediate)) { classGroupCount++; result = NeonLoadClass::Intermediate; }
	if (Contains(groups, kOgBaseLoad))     { classGroupCount++; result = NeonLoadClass::Base; }
	if (Contains(groups, kOgPeak))         { classGroupCount++; result = NeonLoadClass::Peak; }
	return result;
}

std::vector<std::string> NeonRules::CheckGeneratingPlant(const ExemplarFacts& f, Fill& fill)
{
	std::vector<std::string> problems;
	int classCount = 0;
	LoadClassFromGroups(f.groups, classCount);
	if (classCount == 0) problems.emplace_back("missing load class group (Base Load 0x18E64EA5, Intermediate 0x0BADB9AC or Peak 0x7283DCD7)");
	if (classCount > 1) problems.emplace_back("more than one load class group");

	double mwh = 0;
	if (f.mwh)
	{
		mwh = *f.mwh;
		if (f.powerProduced && *f.powerProduced != mwh)
			problems.push_back(Format("MWh Rating %.0f differs from power produced %.0f", mwh, *f.powerProduced));
	}
	else if (f.powerProduced)
	{
		mwh = *f.powerProduced;
		fill.mwh = static_cast<uint32_t>(std::lround(mwh));
	}
	else
	{
		problems.emplace_back("no MWh Rating and no power produced (0x27812852) in the exemplar itself");
		return problems;
	}

	const double expectedKva = std::round(kKvaPerMwh * mwh);
	if (f.kva)
	{
		if (std::fabs(*f.kva - expectedKva) > 0.5)
			problems.push_back(Format("KVA Rating %.0f is not 2.5 x MWh (%.0f)", *f.kva, expectedKva));
	}
	else
	{
		fill.kva = static_cast<uint32_t>(expectedKva);
	}
	return problems;
}

NeonBuildingRecord NeonRules::MakeRecord(const ExemplarFacts& f)
{
	NeonBuildingRecord r;
	r.groups = f.groups;
	int classCount = 0;
	r.loadClass = LoadClassFromGroups(f.groups, classCount);

	double fallbackKva = 0, fallbackMwh = 0;
	bool haveFallback = false;
	for (uint32_t og : f.groups)
	{
		if (IsLegacyGroup(og) && NeonGridModel::LegacyFallback(og, fallbackKva, fallbackMwh)) { haveFallback = true; break; }
	}

	// MWh: exemplar property, then the old Lua table, then the power the building produces.
	if (f.mwh) r.mwh = *f.mwh;
	else if (haveFallback && fallbackMwh > 0) r.mwh = fallbackMwh;
	else if (f.powerProduced) r.mwh = *f.powerProduced;

	// kVA: exemplar property, then the old Lua table, then 2.5 x MWh for generating plants.
	if (f.kva) r.kva = *f.kva;
	else if (haveFallback && fallbackKva > 0) r.kva = fallbackKva;
	else if (IsGeneratingPlant(f.groups)) r.kva = std::round(kKvaPerMwh * r.mwh);

	r.largePlant = r.mwh >= kLargePlantMinMwh;
	return r;
}

NeonBuildingRecord NeonRules::MakeUnsupportedRecord(const ExemplarFacts& f)
{
	NeonBuildingRecord r;
	r.mwh = f.powerProduced.value_or(0.0);
	r.kva = std::round(kKvaPerMwh * r.mwh);
	r.largePlant = r.mwh >= kLargePlantMinMwh;
	r.unsupportedPlantType = static_cast<int>(f.plantType.value_or(0.0));
	return r;
}
