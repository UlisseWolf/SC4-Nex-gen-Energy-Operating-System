#include "NeonLog.h"
#include <Windows.h>
#include <cstdio>
#include <filesystem>
#include <mutex>

EXTERN_C IMAGE_DOS_HEADER __ImageBase;

namespace
{
	std::FILE* file = nullptr;
	std::mutex lock;
}

void NeonLog::Open()
{
	std::scoped_lock guard(lock);
	if (file) return;
	wchar_t path[MAX_PATH]{};
	if (GetModuleFileNameW(reinterpret_cast<HMODULE>(&__ImageBase), path, MAX_PATH) == 0) return;
	const std::filesystem::path log = std::filesystem::path(path).replace_filename(L"SC4NEON.log");
	_wfopen_s(&file, log.c_str(), L"w");
}

void NeonLog::Write(Level level, const char* format, ...)
{
	std::scoped_lock guard(lock);
	if (!file) return;
	static const char* const prefix[] = { "INFO", "WARNING", "ERROR" };
	std::fprintf(file, "[%s] ", prefix[static_cast<int>(level)]);
	va_list args;
	va_start(args, format);
	std::vfprintf(file, format, args);
	va_end(args);
	std::fputc('\n', file);
	std::fflush(file);
}
