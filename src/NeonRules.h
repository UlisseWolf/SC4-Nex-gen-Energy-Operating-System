// NEON DLL - data rules shared by the exemplar check and the building reader. No game headers.
#pragma once
#include "NeonGridModel.h"
#include <optional>
#include <string>
#include <vector>

namespace NeonRules
{
	// Placeholder until the size rule is decided (see README "Open questions"):
	// a NEON-fuel plant WITHOUT a legacy 0xBB35xxxx group is "large" when its MWh reaches this value.
	constexpr double kLargePlantMinMwh = 8000.0;

	struct ExemplarFacts
	{
		std::vector<uint32_t> groups;
		std::optional<double> powerProduced; // 0x27812852
		std::optional<double> kva;           // 0xE652E51F
		std::optional<double> mwh;           // 0x09A44AC9
		std::optional<double> plantType;     // 0x27812853 (only read for plants without NEON groups)
	};

	bool IsNeonGroup(uint32_t og);
	bool IsGenerationFuel(uint32_t og);           // Coal ... Wind (not equipment, not generators)
	bool HasAnyNeonGroup(const std::vector<uint32_t>& groups);
	bool IsGeneratingPlant(const std::vector<uint32_t>& groups); // NEON fuel group or Generators group
	NeonLoadClass LoadClassFromGroups(const std::vector<uint32_t>& groups, int& classGroupCount);

	// Values the DLL writes into a generating plant's exemplar when they are missing:
	// MWh = power produced, kVA = 2.5 x MWh. Returns the problems found (empty = exemplar is clean).
	struct Fill { std::optional<uint32_t> mwh; std::optional<uint32_t> kva; };
	std::vector<std::string> CheckGeneratingPlant(const ExemplarFacts& facts, Fill& fill);

	// Builds the record the grid model counts.
	NeonBuildingRecord MakeRecord(const ExemplarFacts& facts);

	// Record for a power plant without any NEON or legacy group (counted only in the UNS_* / *_OTHER_* values).
	NeonBuildingRecord MakeUnsupportedRecord(const ExemplarFacts& facts);
}
