from argparse import ArgumentParser
from os import chdir, listdir
from os.path import dirname, abspath, join, basename
from re import match
from subprocess import check_call, check_output, CalledProcessError
from sys import stderr, executable

FIRMWARE_FOLDER = dirname(abspath(__file__))

DEFAULT_BOARD = "arduino:avr:nano:cpu=atmega328old"


def parse_version(string: str):
    parts = string.split(".")
    try:
        if len(parts) != 2:
            raise ValueError
        version = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError("Version must be in major.minor format") from None
    if not (0 <= version[0] <= 255 and 0 <= version[1] <= 255):
        raise ValueError("Version numbers must be 0-255")
    return version


def parse_serial(string: str):
    try:
        serial = int(string)
    except ValueError:
        raise ValueError("Serial must be a number")
    if not 0 <= serial <= 255:
        raise ValueError("Serial must be 0-255")
    return serial


def main():
    arg_parser = ArgumentParser()
    arg_parser.add_argument("module", help="Name of module to build")
    arg_parser.add_argument("hw_version", help="HW version of module", type=parse_version)
    arg_parser.add_argument("serial", help="Serial number of module (unique within module type)", type=parse_serial)
    arg_parser.add_argument("-b", "--board", metavar="board", help="Arduino-CLI board name", default=DEFAULT_BOARD)
    arg_parser.add_argument("-u", "--upload", metavar="port", help="Upload to serial port")
    arg_parser.add_argument("--arduino-cli", metavar="path", help="Set Arduino-CLI path", default="arduino-cli")
    arg_parser.add_argument("-d", "--debug", action="store_true", help="Build debug version")
    args = arg_parser.parse_args()

    chdir(FIRMWARE_FOLDER)

    print("Checking known module types", file=stderr)
    known_types = []
    with open(join(FIRMWARE_FOLDER, "module.h")) as stream:
        for line in stream.readlines():
            define_match = match(r"\s*#define\s+MODULE_TYPE_([A-Z_]+)\s+\d+", line)
            if define_match is not None:
                known_types.append(define_match.group(1).lower())

    if args.module.lower() not in known_types:
        print(f"Module {args.module} not found in module.h. Make sure it's correct.", file=stderr)
        exit(1)
        return

    print("Checking arduino-cli version", file=stderr)
    try:
        version_output = check_output([args.arduino_cli, "version"]).decode()

        try:
            version_match = match(r"arduino-cli Version: ([\d.]+)", version_output)
            version_str = version_match.group(1)
            version = [int(part) for part in version_str.split(".")]
        except Exception:
            raise OSError("invalid output from arduino-cli version")
    except (OSError, CalledProcessError) as ex:
        print(f"Failed to check arduino-cli version: {ex}", file=stderr)
        print(f"Make sure arduino-cli is in PATH or use --arduino-cli to specify a location.", file=stderr)
        exit(1)
        return

    if version < [0, 13, 0]:
        print(f"Unsupported arduino-cli version: {version} (required: 0.13.0 or newer)")
        exit(1)
        return

    for file in listdir(FIRMWARE_FOLDER):
        if file.startswith(f"{args.module.lower()}_") and file.endswith(".prebuild.py"):
            print(f"{basename(executable)} {file}", file=stderr)
            try:
                check_call([executable, file])
            except CalledProcessError as ex:
                print("Pre-build command failed.", file=stderr)
                exit(ex.returncode or 1)
                return

    print("Writing module_config.h", file=stderr)
    with open(join(FIRMWARE_FOLDER, "module_config.h"), "w") as stream:
        stream.write(f"""\
// Define DEBUG to enable serial output.
{"" if args.debug else "//"}#define DEBUG

// Define DEBUG_CAN_MESSAGES to also dump all CAN messages to serial.
//#define DEBUG_CAN_MESSAGES

// Module type, chooses which module's code to build. Choose one from module.h.
#define MODULE_TYPE MODULE_TYPE_{args.module.upper()}

// Serial number, must be unique among copies of the same module used in the same bomb.
#define MODULE_SERIAL {args.serial}

// Hardware version. Can be used by the module code to support hardware revisions.
#define VERSION_HW_MAJOR {args.hw_version[0]}
#define VERSION_HW_MINOR {args.hw_version[1]}
""")

    command = [
        args.arduino_cli,
        "compile",
        "-b", DEFAULT_BOARD,
        "--output-dir", f"{FIRMWARE_FOLDER}/build/{args.module.lower()}",
        "--warnings", "all",
    ]
    if args.upload:
        command.extend(["-u", "-p", args.upload])

    print(" ".join(command), file=stderr)
    try:
        check_call(command)
    except CalledProcessError as ex:
        print("Build failed.")
        exit(ex.returncode or 1)
        return


if __name__ == "__main__":
    main()
