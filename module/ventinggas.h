#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_VENTING_GAS

#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#define MODULE_NAME "Venting Gas"

#include <Adafruit_LEDBackpack.h>
#include <LiquidCrystal_I2C.h>

#define HT16K33_ADDR 0x70

#define NO_STATUS_LED

#endif
