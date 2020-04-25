#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_PASSWORD

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#include <ht1632_bitbang.h>

#define HT1632_WR_PIN 7
#define HT1632_DATA_PIN 8
#define HT1632_CS_PIN 9

#endif
