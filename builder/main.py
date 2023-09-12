import sys
from os.path import join

from SCons.Script import (ARGUMENTS, COMMAND_LINE_TARGETS, AlwaysBuild, Builder, Default, DefaultEnvironment)

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()

env.Replace(
    AR="arm-none-eabi-ar",
    AS="arm-none-eabi-as",
    CC="arm-none-eabi-gcc",
    CXX="arm-none-eabi-g++",
    GDB="arm-none-eabi-gdb",
    OBJCOPY="arm-none-eabi-objcopy",
    RANLIB="arm-none-eabi-ranlib",
    SIZETOOL="arm-none-eabi-size",

    ARFLAGS=["rc"],

    PIODEBUGFLAGS=["-O0", "-g3", "-ggdb", "-gdwarf-2"],

    SIZEPROGREGEXP=r"^(?:\.text|\.data|\.rodata|\.text.align|\.ARM.exidx)\s+(\d+).*",
    SIZEDATAREGEXP=r"^(?:\.data|\.bss|\.noinit)\s+(\d+).*",
    SIZECHECKCMD="$SIZETOOL -A -d $SOURCES",
    SIZEPRINTCMD='$SIZETOOL -B -d $SOURCES',

    PROGSUFFIX=".elf"
)

env.Append(
    # ASFLAGS=["-x", "assembler-with-cpp"],

    CCFLAGS=[
        "-Os",
        "-ffunction-sections",
        "-fdata-sections",
        "-mthumb",
        "-mcpu=$BOARD_MCU",
        "-mfpu=fpv4-sp-d16",
        "-mabi=aapcs",
        "-mfloat-abi=hard",
        "-march=armv7e-m",
        "-MMD",
    ],

    CXXFLAGS=[
        "-fno-exceptions",
        "-fno-threadsafe-statics",
        "-fno-rtti",
    ],

    CPPDEFINES=[
        ("F_CPU", "$BOARD_F_CPU"),
        "gcc",
    ],

    LINKFLAGS=[
        "-Os",
        "-mthumb",
        "-mcpu=$BOARD_MCU",
        "-mfpu=fpv4-sp-d16",
        "-mfloat-abi=hard",
        "-mabi=aapcs",
        "-specs=nosys.specs",
    ],

    LIBS=["m", "stdc++", "gcc", "nosys", "c"],

    BUILDERS=dict(
        ElfToHex=Builder(
            action=env.VerboseAction(" ".join([
                "$OBJCOPY",
                "-O",
                "ihex",
                "-R",
                ".eeprom",
                "$SOURCES",
                "$TARGET"
            ]), "Building $TARGET"),
            suffix=".hex"
        )
    )
)


# Allow user to override via pre:script
if env.get("PROGNAME", "program") == "program":
    env.Replace(PROGNAME="firmware")

if "energia" in env.get("PIOFRAMEWORK", []):
    env.Replace(PIOFRAMEWORK=["arduino"])

# Target: Build executable and linkable firmware
target_elf = None
if "nobuild" in COMMAND_LINE_TARGETS:
    target_elf = join("$BUILD_DIR", "${PROGNAME}.elf")
    target_firm = join("$BUILD_DIR", "${PROGNAME}.hex")
else:
    target_elf = env.BuildProgram()
    target_firm = env.ElfToHex(join("$BUILD_DIR", "${PROGNAME}"), target_elf)

AlwaysBuild(env.Alias("nobuild", target_firm))
target_buildprog = env.Alias("buildprog", target_firm, target_firm)

#
# Target: Print binary size
#

target_size = env.Alias(
    "size", target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"))
AlwaysBuild(target_size)

#
# Target: Upload firmware
#

if env.subst("$UPLOAD_PROTOCOL") == "dslite":
    env.Replace(
        UPLOADER=join(env.PioPlatform().get_package_dir(
            "tool-dslite") or "", "DebugServer", "bin", "DSLite"),
        UPLOADERFLAGS=[
            "load", "-c",
            join(env.PioPlatform().get_package_dir("tool-dslite") or "",
                 "%s.ccxml" % env.BoardConfig().get("build.variant")), "-f"
        ],
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS $SOURCES"
    )

elif env.subst("$UPLOAD_PROTOCOL") == "openocd":
    openocd_args = board.get("debug.tools.mspdebug.server.arguments", [])
    openocd_args.extend(["-c", "program {$SOURCE} reset; shutdown;"])
    openocd_args = [
        f.replace("$PACKAGE_DIR", platform.get_package_dir("tool-openocd") or "")
        for f in openocd_args
    ]
    print("ARGS=", openocd_args)
    env.Replace(
        UPLOADER="openocd",
        UPLOADERFLAGS=openocd_args,
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS"
    )

target_upload = env.Alias("upload", target_firm, env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE"))
AlwaysBuild(target_upload)
#
# Default targets
#

Default([target_buildprog, target_size])
