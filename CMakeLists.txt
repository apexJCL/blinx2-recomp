cmake_minimum_required(VERSION 3.20)

# ============================================================================
# cat_recomp - static recompilation of BLiNX 2: Masters of Time & Space
#
# Builds the game-specific half (boot code, manual overrides, the generated
# sources in src/recomp/gen/) against the xboxrecomp toolkit, found as
# described below. See README.md for the build steps.
# ============================================================================

project(cat_recomp C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Common definitions
add_compile_definitions(
    WIN32_LEAN_AND_MEAN
    NOMINMAX
)

# ── xboxrecomp toolkit ──────────────────────────────────────────
#
# The toolkit is a fork of sp00nznet/xboxrecomp (see README.md). By default it
# is found at external/xboxrecomp inside this project when that exists, else at
# ../xboxrecomp next to it. Pass -DXBOXRECOMP_DIR=<path> to use another clone.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/external/xboxrecomp/CMakeLists.txt")
    set(_xboxrecomp_default "${CMAKE_CURRENT_SOURCE_DIR}/external/xboxrecomp")
else()
    set(_xboxrecomp_default "${CMAKE_CURRENT_SOURCE_DIR}/../xboxrecomp")
endif()
set(XBOXRECOMP_DIR "${_xboxrecomp_default}" CACHE PATH
    "Path to the xboxrecomp toolkit root directory")

# Keep this hoist: without it a clean configure fails with "target was not
# found" for OpenSSL::Crypto.
#
# Off Windows, xbox_kernel links OpenSSL::Crypto PUBLIC but finds it inside its
# own subdirectory, where the imported target stays invisible to this
# executable. Finding it here first puts it in scope for both.
if(NOT WIN32)
    find_package(OpenSSL REQUIRED)
endif()

# The toolkit's enhancements layer (render scale, present filter, fullscreen;
# enhance.toml beside the executable). ON for this title, every key stock by
# default; not FORCE, so -DXBOXRECOMP_ENHANCE=OFF builds a layer-free binary
# for A/B.
set(XBOXRECOMP_ENHANCE ON CACHE BOOL
    "Build the enhancements layer (enhance.toml, RECOMP_RENDER_SCALE, ...)")

# Add xboxrecomp as a subdirectory -- this builds all 6 runtime libraries
# and provides the 'xboxrecomp' umbrella target to link against.
add_subdirectory(${XBOXRECOMP_DIR} ${CMAKE_BINARY_DIR}/xboxrecomp)

# This game's own environment keys (save seeding, scripted input, memory and
# thread dumps) join the toolkit's table: src/env/recomp_env_game.h.
target_compile_definitions(recomp_env PUBLIC RECOMP_ENV_HAVE_GAME_KEYS)
target_include_directories(recomp_env PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src/env)

# ── Recompiled game executable ──────────────────────────────────

# Collect generated recompiled code.
# The recomp pipeline outputs files into src/recomp/gen/.
# With --split 1000, you get gen_0000.c, gen_0001.c, etc.
# CONFIGURE_DEPENDS so re-running the recompiler picks up added/removed files
# without a manual re-configure. A plain GLOB is evaluated once at configure
# time, so a newly generated file (an extra chunk, recomp_stubs_unresolved.c)
# is silently left out of the build and shows up as unresolved externals.
file(GLOB RECOMP_GEN_SOURCES CONFIGURE_DEPENDS "src/recomp/gen/*.c")

# Core game sources
set(GAME_SOURCES
    src/main.c
    src/recomp_manual.c
    src/pad_input.c
    src/save_seed.c
    src/glow.c
    # Add game-specific sources here, e.g.:
    # src/asset_loader.c
    # src/custom_renderer.c
)

# The recomp pipeline also generates a dispatch header and function declarations.
# These are included by the generated .c files:
#   src/recomp/gen/recomp_funcs.h    - extern declarations for all recompiled functions
#   src/recomp/recomp_dispatch.h     - binary search dispatch table
#   src/recomp/recomp_types.h        - register model, ICALL macros, MEM helpers

# WIN32 selects the GUI subsystem on Windows and is ignored elsewhere, so the
# macOS build is a plain console executable.
add_executable(${PROJECT_NAME} WIN32
    ${GAME_SOURCES}
    ${RECOMP_GEN_SOURCES}
)

# Opt-in app icon for the Windows exe: a .ico path. Only `blinx2 package`
# sets it, in its own build-pkg-win/ (the icon is the game's title image,
# kept out of git); empty, nothing below runs and the build is unchanged.
set(CAT_APP_ICON "" CACHE FILEPATH
    "Windows: .ico compiled into cat_recomp.exe (the taskbar shows the game's own icon)")
if(CAT_APP_ICON AND WIN32)
    enable_language(RC)
    file(TO_CMAKE_PATH "${CAT_APP_ICON}" ICON)
    configure_file(${CMAKE_CURRENT_SOURCE_DIR}/packaging/windows/BLiNX2.rc.in
                   ${CMAKE_CURRENT_BINARY_DIR}/cat_recomp_icon.rc @ONLY)
    target_sources(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/cat_recomp_icon.rc)
endif()

# Link against the xboxrecomp umbrella target (all 6 runtime libraries)
target_link_libraries(${PROJECT_NAME} PRIVATE xboxrecomp)

# Include paths for generated recomp headers
target_include_directories(${PROJECT_NAME} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/recomp
    ${XBOXRECOMP_DIR}/include
)

# Windows SDK libraries needed at link time. Other hosts get graphics, input
# and crypto through the xboxrecomp targets and need nothing extra here.
#
# The executable stays unstripped on every host: the fault handler names the
# generated function a crash happened in from the symbol table (dbghelp on
# Windows, dladdr elsewhere). macOS needs no -export_dynamic for that, only no
# strip -x / -Wl,-x.
if(WIN32)
    target_link_libraries(${PROJECT_NAME} PRIVATE
        d3d11
        dxgi
        dxguid
        xinput
        winmm
        # Lets the fault handler resolve the host RIP back to the generated
        # function's symbol, i.e. to the guest function that faulted.
        dbghelp
    )
endif()

# MSVC-specific: large address aware, increase section limit for big generated files
if(MSVC)
    target_link_options(${PROJECT_NAME} PRIVATE
        /LARGEADDRESSAWARE
    )
    # The generated code files can be very large. Increase object file section limit.
    target_compile_options(${PROJECT_NAME} PRIVATE /bigobj)
endif()

# MinGW (llvm-mingw, or GCC MinGW as a fallback). Clang's COFF writer switches
# to the big-object format on its own when a generated file needs it; GCC's
# assembler has to be told. lld writes a PDB of public symbols even without -g,
# which is what the fault handler's SymFromAddr needs to name a function.
if(MINGW)
    if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
        set_property(SOURCE ${RECOMP_GEN_SOURCES} APPEND PROPERTY
            COMPILE_OPTIONS -Wa,-mbig-obj)
    else()
        target_link_options(${PROJECT_NAME} PRIVATE
            "-Wl,--pdb=$<TARGET_FILE_DIR:${PROJECT_NAME}>/${PROJECT_NAME}.pdb")
    endif()
endif()

# Optimization override for the generated code only. Empty by default (the
# build type decides); set e.g. -DCAT_GEN_OPT=-O1 when -O3 over ~800 MB of
# generated C takes too long or too much memory. Host code keeps the default.
set(CAT_GEN_OPT "" CACHE STRING
    "Extra compile options for src/recomp/gen/*.c only (e.g. -O1)")
if(CAT_GEN_OPT)
    separate_arguments(_cat_gen_opt NATIVE_COMMAND "${CAT_GEN_OPT}")
    set_property(SOURCE ${RECOMP_GEN_SOURCES} APPEND PROPERTY
        COMPILE_OPTIONS ${_cat_gen_opt})
endif()
