#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_BUTTON

#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif

#define MODULE_NAME "Button"

#include <FastLED.h>

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#define BUTTON_PIN 4

#define LED_DATA_PIN 7
#define NUM_LEDS 6

#define STRIKE_LED_PIN A0
#define SOLVE_LED_PIN A1

#endif
