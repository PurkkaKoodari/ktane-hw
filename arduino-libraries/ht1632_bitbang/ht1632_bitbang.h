#ifndef HT1632_BITBANG_H
#define HT1632_BITBANG_H

#if(ARDUINO >= 100)
 #include <Arduino.h>
#else
 #include <WProgram.h>
#endif

class HT1632 {
 public:
  HT1632(uint8_t data, uint8_t wr, uint8_t cs, uint8_t rows = 32, uint8_t coms = 8);
  void begin();
  void clear(uint8_t pattern = 0);
  void set(uint8_t row, uint8_t com, bool on);
  void update();
  void brightness(uint8_t value);
  
 private:
  uint8_t data_pin, wr_pin, cs_pin;
  uint8_t rows, coms;
  uint8_t data[16 * 24 / 8];
  
  void send_command(uint16_t command);
  void send_data(uint16_t data, uint8_t bits);
  void send_data_lsb_first(uint16_t data, uint8_t bits);
};

#endif // HT1632_BITBANG_H
