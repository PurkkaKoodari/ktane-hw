# KTaNE HW

This project is a hardware reimplementation of the game [Keep Talking and Nobody Explodes][ktane]. The game runs fully on the physical device and is controlled using a web interface over Wi-Fi. The project will be documented in this repository &ndash; expect the links below to be broken for the near future.

(TODO: insert photos here)

## Architecture

The hardware is built around a Raspberry Pi Zero W, which runs the main controller software, attached to a [backplane](doc/hardware/backplane.md) that provides power, connectivity and audio. The game's [modules](doc/hardware/modules.md) are built as independent devices, usually based on an Arduino Nano, which connect to the backplane using RJ-45 connectors (with a completely nonstandard usage of the pins).

The software can be divided into three parts: the [main controller](doc/software/main_controller.md), written in Python 3 using `asyncio` and [`websockets`][websockets]; the module software, written in C++ and built using [`arduino-cli`][arduino-cli]; and the Web interface, written using [Preact][preact]. In addition, one can run a [room server](doc/software/room_server.md), which supports room-scale audio and DMX lights and other effects.

## License

Unless otherwise noted, all software in this repository is licensed under the [MIT license](LICENSE); the hardware design files in `hardware/` are licensed under the [CERN-OHL-P v2](hardware/LICENSE); and the sounds in `sounds/` are licensed under CC-BY 3.0 (see [sounds/CREDITS.txt](sounds/CREDITS.txt) for authors).

This project is not in any way related to or endorsed by Steel Crate Games, nor does it include any assets from the original game. If you intend to build a copy of the project, please support them and [purchase a copy of the game][buy-ktane]!

[ktane]: http://www.keeptalkinggame.com/
[buy-ktane]: https://keeptalkinggame.com/#buynow
[websockets]: https://websockets.readthedocs.io/en/stable/intro.html
[arduino-cli]: https://arduino.github.io/arduino-cli/latest/commands/arduino-cli/
[preact]: https://preactjs.com/
