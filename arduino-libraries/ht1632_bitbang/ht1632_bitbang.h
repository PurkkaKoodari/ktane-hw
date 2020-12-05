#ifndef HT1632_BITBANG_H
#define HT1632_BITBANG_H

enum HT1632_ComMode {
  HT1632_8COM_NMOS = 0b00,
  HT1632_16COM_NMOS = 0b01,
  HT1632_8COM_PMOS = 0b10,
  HT1632_16COM_PMOS = 0b11
};

#if(ARDUINO >= 100)
 #include <Arduino.h>
#else
 #include <WProgram.h>
#endif

class HT1632 {
 public:
  HT1632(uint8_t data, uint8_t wr, uint8_t cs, uint8_t rows = 32, uint8_t coms = 8);
  void begin(HT1632_ComMode com_mode = HT1632_8COM_NMOS);
  void clear(uint8_t pattern = 0);
  void set(uint8_t row, uint8_t com, bool on);
  void update();
  void brightness(uint8_t value);
  void blink(bool blink);
  
 private:
  uint8_t data_pin, wr_pin, cs_pin;
  uint8_t rows, coms;
  uint8_t data[16 * 24 / 8];
  
  void send_command(uint16_t command);
  void send_data(uint16_t data, uint8_t bits);
  void send_data_lsb_first(uint16_t data, uint8_t bits);
};

#endif // HT1632_BITBANG_H
