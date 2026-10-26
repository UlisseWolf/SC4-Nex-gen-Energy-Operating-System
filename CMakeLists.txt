# SC4NEON.dll - alternative to SC4NEON.sln. Build with Visual Studio 2022, 32-bit (SimCity 4 is a 32-bit game):
#   cmake -S . -B build -A Win32
#   cmake --build build --config Release
cmake_minimum_required(VERSION 3.20)
project(SC4NEON LANGUAGES CXX)

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
  message(FATAL_ERROR "SimCity 4 is 32-bit: configure with -A Win32")
endif()

set(CMAKE_CONFIGURATION_TYPES Release CACHE STRING "" FORCE)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(GZCOM ${CMAKE_SOURCE_DIR}/vendor/gzcom-dll/gzcom-dll)
if(NOT EXISTS ${GZCOM}/include/cRZCOMDllDirector.h)
  message(FATAL_ERROR "Missing vendor/gzcom-dll (it ships with the project)")
endif()

add_library(SC4NEON SHARED
  src/NeonDllDirector.cpp
  src/NeonEnforcement.cpp
  src/NeonEnforcementPatch.cpp
  src/NeonGridModel.cpp
  src/NeonLog.cpp
  src/NeonLua.cpp
  src/NeonRules.cpp
  ${GZCOM}/src/cRZBaseString.cpp
  ${GZCOM}/src/cRZBaseVariant.cpp
  ${GZCOM}/src/cRZCOMDllDirector.cpp
  ${GZCOM}/src/SCLuaUtil.cpp
  ${GZCOM}/src/SCPropertyUtil.cpp
)
target_include_directories(SC4NEON PRIVATE
  src
  ${GZCOM}/include
  ${CMAKE_SOURCE_DIR}/vendor/sc4-resource-loading-hooks/include)
target_compile_definitions(SC4NEON PRIVATE WIN32 _WINDOWS _USRDLL NOMINMAX)
target_compile_options(SC4NEON PRIVATE /W4 /permissive- /utf-8)
# Static runtime: players do not need to install the Visual C++ redistributable.
set_property(TARGET SC4NEON PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded")

# Host-side tests (any compiler): the C++ model against the original Lua, see tests/.
add_executable(neon_model_driver EXCLUDE_FROM_ALL tests/model_driver.cpp src/NeonGridModel.cpp)
add_executable(neon_rules_test EXCLUDE_FROM_ALL tests/rules_test.cpp src/NeonRules.cpp src/NeonGridModel.cpp)
