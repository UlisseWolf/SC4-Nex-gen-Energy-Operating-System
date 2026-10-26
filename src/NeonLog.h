// NEON DLL - minimal log file (SC4NEON.log next to the DLL).
#pragma once
#include <cstdarg>

namespace NeonLog
{
	enum class Level { Info, Warning, Error };
	void Open();
	void Write(Level level, const char* format, ...);
}
