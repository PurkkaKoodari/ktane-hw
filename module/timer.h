#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_TIMER

#if (VERSION_HW_MAJOR != 0 || VERSION_HW_MINOR != 1) && (VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0)
#error This version of the module software does not support the configured hardware version.
#endif

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#if VERSION_HW_MAJOR == 0

#include <ht1632_bitbang.h>

#define HT1632_WR_PIN 7
#define HT1632_DATA_PIN 8
#define HT1632_CS_PIN 9

#elif VERSION_HW_MAJOR == 1

#include <Adafruit_LEDBackpack.h>

#define HT16K33_ADDR 0x70

#endif

#define STRIKE_1_PIN A0
#define STRIKE_2_PIN A1

#define NO_STATUS_LED

#endif
