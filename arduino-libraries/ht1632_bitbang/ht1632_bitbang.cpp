#include "ht1632_bitbang.h"

HT1632::HT1632(uint8_t data, uint8_t wr, uint8_t cs, uint8_t row, uint8_t com): data_pin(data), wr_pin(wr), cs_pin(cs), rows(row), coms(com) {}

void HT1632::send_data(uint16_t data, uint8_t bits) {
  for (uint16_t bit = (1 << (bits - 1)); bit; bit >>= 1) {
    digitalWrite(wr_pin, LOW);
    digitalWrite(data_pin, (data & bit) ? HIGH : LOW);
    digitalWrite(wr_pin, HIGH);
  }
}

void HT1632::send_data_lsb_first(uint16_t data, uint8_t bits) {
  for (; bits--; data >>= 1) {
    digitalWrite(wr_pin, LOW);
    digitalWrite(data_pin, data & 1);
    digitalWrite(wr_pin, HIGH);
  }
}

void HT1632::send_command(uint16_t command) {
  digitalWrite(cs_pin, LOW);
  send_data(0b100, 3);
  send_data(command, 9);
  digitalWrite(cs_pin, HIGH);
}

void HT1632::begin(HT1632_ComMode com_mode) {
  pinMode(cs_pin, OUTPUT);
  pinMode(wr_pin, OUTPUT);
  pinMode(data_pin, OUTPUT);
  digitalWrite(cs_pin, HIGH);
  digitalWrite(data_pin, HIGH);
  
  send_command(0b000110000); // rc master mode
  send_command(0b000010000); // blink off
  send_command(0b001000000 | (com_mode << 3));
  send_command(0b101011110); // PWM 16/16
  send_command(0b000000010); // sys enable
  send_command(0b000000110); // led on
}

void HT1632::clear(uint8_t pattern) {
  memset(data, pattern, rows * coms / 8);
}

void HT1632::set(uint8_t row, uint8_t com, bool on) {
  int bit = com & 7;
  int index = (com >> 3) + (row * (coms >> 3));
  data[index] = data[index] & ~(1 << bit) | (on << bit);
}

void HT1632::brightness(uint8_t value) {
  if (value > 15) value = 15;
  send_command(0b101000000 | (value << 1));
}

void HT1632::blink(bool blink) {
  send_command(0b000010000 | ((blink & 1) << 1));
}

void HT1632::update() {
  digitalWrite(cs_pin, LOW);
  send_data(0b101, 3);
  send_data(0b0000000, 7);
  for (uint8_t i = 0; i < rows * coms / 8; i++) {
    send_data_lsb_first(data[i], 8);
  }
  digitalWrite(cs_pin, HIGH);
}
