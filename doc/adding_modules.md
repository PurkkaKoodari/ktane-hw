# Adding modules

This document provides a step-by-step guide to adding new modules to the system.

## Conventions

### Version numbering

Each module has two version numbers, the hardware and software version, each represented as `major.minor`.

- The first released version is always 1.0.
- **Hardware version:**
    - The hardware version should always match the one printed on the board's silkscreen.
    - Any pre-release hardware should be marked as version 1.0 so that it can become the 1.0 release when it works.
    - A **major** version change indicates a major redesign that requires large firmware changes (e.g. changing of full mechanism).
    - A **minor** change may be anything smaller. It may still require changes in the firmware or main controller actions (e.g. pin changes, changing a driver chip, fixing errors that needed workarounds) or it may be a non-functional board update.
- **Software version:**
    - The software version is not tied to the hardware version, but relates to the bus protocol versioning.
    - Pre-release software may opt to use version 0.x or 1.0.
    - A **major** version change indicates that the main controller software will need a explicit update to support the protocol used by this version.
    - A **minor** version change indicates that the main controller may support this version without an explicit update. It may still be unable to use some new features in this version.

### Module IDs

You'll need a unique module ID. IDs 1-63 are reserved for vanilla modules, IDs 64-4095 for modded modules. Choose the lowest free ID from the appropriate range and add it in `bus_protocol.md`.

## 1. Build the hardware

A module starts with hardware. Most modules consist of the following:

- Faceplate, 100mm x 110mm x 3mm (WxHxD), acrylic/aluminum
    - 5mm on top/bottom reserved for mounting
    - All measurements below are from the 100mm x 100mm area excluding the mounting part
- PCB, usually 100mm x 100mm
    - 100mm x 100mm chosen for easy & cheap production
- Arduino-compatible microprocessor
    - Current modules use an Arduino Nano (or clone) on headers
- MCP2515 based CAN module with 5V bus voltage
    - Current modules use a MCP2515+TJA1050 module on headers, commonly available from China
- 10mm RGB LED for non-needy modules, centered 8mm from the right and top edges
- Mounting holes with M3 bolts
    - Usually centered 5mm from each edge, can be customized depending on module
    - With the RGB LED, the standard location for the top-right hole is 20mm from the right edge
- Various electrical, 3D-printed, laser-cut, etc. parts for the user interface

(TODO: add CAD models to repository for reference)

Before designing a new PCB, see if the [base module PCB][base-pcb] is enough for your needs. It breaks out many pins of the Arduino, including PWM and I&sup2;C and adds pins for two common LED matrix drivers, the HT1632C and HT16K33. It can be used as-is or by adding an adapter board. If you decide you need your own board, the base PCB is a good starting point as well.

Most module electronics should work with 5V. The MODULE_READY and MODULE_ENABLE signals, as well as the CAN bus, are configured for 5V operation. If your components need 3.3V, the module will need its own regulator.

The module connector additionally provides a 12V pin that can be used for more power-hungry peripherals such as motors or solenoids. This pin is not strictly 12V, but is intended to be the unregulated battery voltage &mdash; it may be anything from 11V to 15V, so make sure your components can handle that. Some bomb casings may not provide 12V power at all, as most modules don't use it.

## 2. Build the module firmware

The Arduino-based firmware needs to be extended to support your module.

1. Add your module ID to the start of `module.h`. This is the only change you'll need to make to existing files.
2. Copy [`newmodule.h`][newmodule.h] and [`newmodule.cpp`][newmodule.cpp] to the `module` directory and write your code as described in the comments.
3. Follow the instructions in [`module/README.md`][module-readme] to configure your build.

## 3. Add support in the controller software

The main controller then needs to be extended.

1. Copy [`template.py`][template.py] to your module's name (in lowercase) and write your code as described in the comments.
2. Add the name of your module to `bombgame/modules/__init__.py` so it will be loaded properly.
3. Optionally, write tests for your module. <!-- TODO: create a standard location - probably bombgame/test/modules -->

## 4. Add support in the frontend

The frontend is going to be rewritten soon, instructions will be updated later.


[base-pcb]: ../hardware/module_base
[newmodule.h]: ../module/module_template/newmodule.h
[newmodule.cpp]: ../module/module_template/newmodule.cpp
[template.py]: ../maincontroller/bombgame/modules/template.py
[module-readme]: ../module/README.md
