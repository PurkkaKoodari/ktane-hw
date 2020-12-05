#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_PASSWORD

#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#define MODULE_NAME "Password"

#include <ht1632_bitbang.h>
#include "password_font.h"

#define HT1632_WR_PIN 4
#define HT1632_DATA_PIN 3
#define HT1632_CS_PIN 5

#define BTN_PIN_0 6
#define BTN_PIN_1 7
#define BTN_PIN_2 9
#define BTN_PIN_3 A4
#define SUBMIT_PIN A5

#define STRIKE_LED_PIN A0
#define SOLVE_LED_PIN A1

#endif
