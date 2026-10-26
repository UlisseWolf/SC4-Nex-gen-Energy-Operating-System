// NEON DLL - identifiers shared by the whole plugin.
#pragma once
#include <cstdint>

namespace NeonIds
{
	// ---------------------------------------------------------------- exemplar properties
	constexpr uint32_t kExemplarName          = 0x00000020;
	constexpr uint32_t kOccupantGroups        = 0xAA1DD396;
	constexpr uint32_t kPowerProduced         = 0x27812852; // MWh/month the plant produces at 100 %
	constexpr uint32_t kPowerPlantType        = 0x27812853; // Maxis power plant type (1 coal ... 9 wind)
	constexpr uint32_t kKvaRating             = 0xE652E51F; // NEON "KVA Rating"
	constexpr uint32_t kMwhRating             = 0x09A44AC9; // NEON "MWh Rating"

	// kVA = kKvaPerMwh x MWh. Agreed rule for NEON (kept identical to the Reader templates).
	constexpr double kKvaPerMwh = 2.5;

	// ---------------------------------------------------------------- game messages (verified in SimCity_4.exe 1.1.641)
	constexpr uint32_t kMsgPostCityInit       = 0x26D31EC1;
	constexpr uint32_t kMsgPreCityShutdown    = 0x26D31EC2;
	constexpr uint32_t kMsgOccupantInserted   = 0x99EF1142; // cIGZMessage2Standard::GetVoid1() = cISC4Occupant*
	constexpr uint32_t kMsgOccupantRemoved    = 0x99EF1143;

	// ---------------------------------------------------------------- NEON occupant groups (new_properties.xml)
	// Fuel / function groups.
	constexpr uint32_t kOgCoal                = 0x1946409F;
	constexpr uint32_t kOgOil                 = 0xD6B169D9;
	constexpr uint32_t kOgBiomass             = 0x36CA5093;
	constexpr uint32_t kOgNaturalGas          = 0x5512235E;
	constexpr uint32_t kOgFission             = 0xA945A10D;
	constexpr uint32_t kOgFusion              = 0xB680D7E0;
	constexpr uint32_t kOgGeothermal          = 0x1F221780;
	constexpr uint32_t kOgSolar               = 0x7134683C;
	constexpr uint32_t kOgMicrowave           = 0x0CED62DC;
	constexpr uint32_t kOgTidal               = 0xF0D606AC;
	constexpr uint32_t kOgWasteToEnergy       = 0xEC9175AA;
	constexpr uint32_t kOgHydro               = 0x8765D979;
	constexpr uint32_t kOgWind                = 0xC78E0054;
	constexpr uint32_t kOgGenerators          = 0xB075C142;
	constexpr uint32_t kOgAuxiliary           = 0x7AB34F1B;
	constexpr uint32_t kOgPowerStorage        = 0x861A7248;
	constexpr uint32_t kOgHvTransformers      = 0xED378A8E;
	constexpr uint32_t kOgMvTransformers      = 0x1B823F5A;
	constexpr uint32_t kOgLvTransformers      = 0x215395E9;

	// Load class groups. Every NEON generating plant must carry exactly one of these.
	constexpr uint32_t kOgIntermediate        = 0x0BADB9AC;
	constexpr uint32_t kOgBaseLoad            = 0x18E64EA5;
	constexpr uint32_t kOgPeak                = 0x7283DCD7;

	// Legacy NEON / AMPS groups live in 0xBB35xxxx (see NeonLegacyGroups.inc).
	constexpr bool IsLegacyGroup(uint32_t og) { return (og & 0xFFFF0000u) == 0xBB350000u; }
}
