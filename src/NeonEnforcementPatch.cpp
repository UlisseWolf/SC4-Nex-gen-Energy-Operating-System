// Game side of NeonEnforcement: SC4NEON.ini and the 1.1 constant of cSC4PowerSimulator::UpdatePowerGrid.
#include "NeonEnforcement.h"
#include "NeonLog.h"
#include <Windows.h>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <string>

EXTERN_C IMAGE_DOS_HEADER __ImageBase;

namespace
{
	// SimCity 4 1.1.641
	constexpr uintptr_t kFmulAddress = 0x006EE3DA;      // fmul dword ptr [0x00AB2888]
	constexpr uint8_t kFmulBytes[] = { 0xD8, 0x0D, 0x88, 0x28, 0xAB, 0x00 };
	constexpr uintptr_t kConstantAddress = 0x00AB2888;  // float -1.1, read only by that instruction
	constexpr float kVanilla = -1.1f;

	NeonEnforcementSettings settings;
	NeonEnforcementResult last;
	bool installed = false;
	float current = kVanilla;
	bool loggedThisCity = false;

	std::filesystem::path IniPath()
	{
		wchar_t path[MAX_PATH]{};
		GetModuleFileNameW(reinterpret_cast<HMODULE>(&__ImageBase), path, MAX_PATH);
		return std::filesystem::path(path).replace_filename(L"SC4NEON.ini");
	}

	bool WriteConstant(float value)
	{
		if (!installed || value == current) return true;
		auto* target = reinterpret_cast<float*>(kConstantAddress);
		DWORD old = 0;
		if (!VirtualProtect(target, sizeof(float), PAGE_READWRITE, &old)) return false;
		*target = value;
		VirtualProtect(target, sizeof(float), old, &old);
		current = value;
		return true;
	}
}

void NeonEnforcement::LoadSettings()
{
	const std::filesystem::path ini = IniPath();
	if (!std::filesystem::exists(ini))
	{
		const char* text =
			"; SC4NEON.dll settings\r\n"
			"[Enforcement]\r\n"
			"; 1 = the NEON grid limits are real: power NEON cannot deliver does not reach the buildings (blackouts).\r\n"
			"; 0 = NEON only shows the limits, the game hands out power as usual.\r\n"
			"Enabled=1\r\n"
			"; Base / Intermediate / Peak balance (Unusable power and Peak shortfall)\r\n"
			"LoadBalance=1\r\n"
			"; transmission stations, distribution substations and transformers (MWh = kVA / 2.5)\r\n"
			"Infrastructure=1\r\n"
			"; residential population where the limits start, and where they apply in full (linear in between)\r\n"
			"StartPopulation=3000\r\n"
			"FullPopulation=15000\r\n";
		if (FILE* f = _wfopen(ini.c_str(), L"wb")) { std::fputs(text, f); std::fclose(f); }
	}
	const wchar_t* p = ini.c_str();
	settings.enabled = GetPrivateProfileIntW(L"Enforcement", L"Enabled", 1, p) != 0;
	settings.loadBalance = GetPrivateProfileIntW(L"Enforcement", L"LoadBalance", 1, p) != 0;
	settings.infrastructure = GetPrivateProfileIntW(L"Enforcement", L"Infrastructure", 1, p) != 0;
	settings.startPopulation = GetPrivateProfileIntW(L"Enforcement", L"StartPopulation", 3000, p);
	settings.fullPopulation = GetPrivateProfileIntW(L"Enforcement", L"FullPopulation", 15000, p);
	NeonLog::Write(NeonLog::Level::Info, "Enforcement: %s (load balance %d, infrastructure %d, population %.0f .. %.0f)",
		settings.enabled ? "on" : "off", settings.loadBalance, settings.infrastructure,
		settings.startPopulation, settings.fullPopulation);
}

const NeonEnforcementSettings& NeonEnforcement::Settings() { return settings; }
const NeonEnforcementResult& NeonEnforcement::LastResult() { return last; }

bool NeonEnforcement::InstallPatch()
{
	if (!settings.enabled) return false;
	// The exe is always mapped at 0x00400000 (no relocation), so both addresses are readable in SimCity 4.
	const bool codeOk = std::memcmp(reinterpret_cast<const void*>(kFmulAddress), kFmulBytes, sizeof(kFmulBytes)) == 0;
	const bool valueOk = *reinterpret_cast<const float*>(kConstantAddress) == kVanilla;
	installed = codeOk && valueOk;
	if (installed) NeonLog::Write(NeonLog::Level::Info, "Enforcement: power grid hook ready (SimCity 4 1.1.641).");
	else NeonLog::Write(NeonLog::Level::Warning, "Enforcement: unknown SimCity 4 version, the grid limits stay informative only.");
	return installed;
}

void NeonEnforcement::Apply(const NeonGridModel& model, const NeonGridInputs& in)
{
	if (!installed) return;
	const NeonEnforcementResult r = Compute(model, in, settings);
	// Log the first evaluation of each city, then every real change: factor, cut on/off, population ramp
	// in steps of 10 %, or the deficit moving by more than 10 %.
	const bool bigChange = !loggedThisCity
		|| std::fabs(r.factor - last.factor) > 0.02
		|| (r.blackoutMwh > 0) != (last.blackoutMwh > 0)
		|| std::floor(r.strength * 10) != std::floor(last.strength * 10)
		|| std::fabs(r.deficitMwh - last.deficitMwh) > 0.1 * std::max(last.deficitMwh, 100.0);
	loggedThisCity = true;
	last = r;
	WriteConstant(static_cast<float>(kVanilla * r.factor));
	if (bigChange)
	{
		NeonLog::Write(NeonLog::Level::Info,
			"Enforcement: population %.0f, demand %.0f MWh, load balance %.0f, infrastructure %.0f, deliverable %.0f, "
			"deficit %.0f, strength %.0f%%, blackout %.0f, factor %.3f",
			in.population, r.demand, r.loadBalanceMwh, r.infrastructureMwh, r.deliverableMwh,
			r.deficitMwh, r.strength * 100, r.blackoutMwh, r.factor);
	}
}

void NeonEnforcement::Reset()
{
	last = NeonEnforcementResult{};
	loggedThisCity = false;
	WriteConstant(kVanilla);
}
