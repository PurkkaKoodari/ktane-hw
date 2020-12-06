# Module firmware

## Libraries

- [Arduino-MCP2515][mcp2515] for CAN communication
- [Adafruit_LED_Backpack][ledbackpack] for modules using the HT16K33 chip
- [Custom library][ht1632c_bitbang] for modules using the HT1632C chip (see the [README.md][ht1632c_readme])
- [LiquidCrystal_I2C][lcd_i2c] for modules using 1602 LCDs with a PCF8574
- [FastLED][fastled] for modules using WS2812B (NeoPixel) LEDs

## Building

Building from command line using the included script is highly recommended.

Install [arduino-cli] first, then run `python3 build.py`.

Substitute your module details and serial port name.
Refer to `python3 build.py --help` for other options.

```sh
python3 build.py <module> <hwver> <serial> -u /dev/<serialport>
```

[arduino-cli]: https://arduino.github.io/arduino-cli/latest/installation/
[mcp2515]: https://github.com/autowp/arduino-mcp2515
[ht1632c_bitbang]: ../arduino-libraries/ht1632c_bitbang
[ht1632c_readme]: ../arduino-libraries/ht1632c_bitbang/README.md
[ledbackpack]: https://github.com/adafruit/Adafruit_LED_Backpack/
[lcd_i2c]: https://github.com/johnrickman/LiquidCrystal_I2C
[fastled]: https://github.com/FastLED/FastLED
