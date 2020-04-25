#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_TIMER

#include <ht1632_bitbang.h>

#define HT1632_WR_PIN 7
#define HT1632_DATA_PIN 8
#define HT1632_CS_PIN 9

#define STRIKE_1_PIN A0
#define STRIKE_2_PIN A1

#define NO_STATUS_LED

#endif
