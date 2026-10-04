# Cross-compile cat_recomp for Windows x86-64 (run under Proton/Wine or on
# Windows) with llvm-mingw: clang + lld + mingw-w64 headers, UCRT runtime.
#
# Why llvm-mingw and not GCC MinGW: GCC on mingw implements __thread through
# emutls, a function call per access, and the RECOMP_TLS guest registers are
# touched by nearly every lifted instruction. Clang uses native TLS.
#
# Locating the toolchain, first match wins:
#   -DLLVM_MINGW_ROOT=<dir>  or  env LLVM_MINGW_ROOT=<dir>   (<dir>/bin/x86_64-w64-mingw32-clang)
#   x86_64-w64-mingw32-clang on PATH
#
#   cmake -S . -B build-mingw -DCMAKE_TOOLCHAIN_FILE=cmake/llvm-mingw-x86_64.cmake
#   cmake --build build-mingw -j N

set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

set(_triple x86_64-w64-mingw32)

if(NOT LLVM_MINGW_ROOT AND DEFINED ENV{LLVM_MINGW_ROOT})
    set(LLVM_MINGW_ROOT "$ENV{LLVM_MINGW_ROOT}")
endif()
set(LLVM_MINGW_ROOT "${LLVM_MINGW_ROOT}" CACHE PATH "llvm-mingw install root (empty: search PATH)")
# try_compile projects re-read this file; pass the root down to them.
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES LLVM_MINGW_ROOT)

if(LLVM_MINGW_ROOT)
    set(_hints HINTS "${LLVM_MINGW_ROOT}/bin" NO_DEFAULT_PATH)
endif()
find_program(_mingw_cc  ${_triple}-clang   ${_hints} REQUIRED)
find_program(_mingw_cxx ${_triple}-clang++ ${_hints} REQUIRED)
find_program(_mingw_rc  ${_triple}-windres ${_hints})

set(CMAKE_C_COMPILER   "${_mingw_cc}")
set(CMAKE_CXX_COMPILER "${_mingw_cxx}")
if(_mingw_rc)
    set(CMAKE_RC_COMPILER "${_mingw_rc}")
endif()

get_filename_component(_bin "${_mingw_cc}" DIRECTORY)
set(CMAKE_FIND_ROOT_PATH "${_bin}/../${_triple}")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
