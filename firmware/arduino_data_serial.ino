#include <Wire.h>
#include <BH1750.h>
#include <DHT.h>
#include <OneWire.h>
#include <DS18B20.h>

// --- settings ---
#define DHTPIN 7
#define DHTTYPE DHT22
#define HEADER1 0xAA
#define HEADER2 0x55

DHT dht(DHTPIN, DHTTYPE);

// CO2
byte cmd[9] = {0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79};
byte response[9];

// Light
#define DOUT 14
#define SCK 15
BH1750 lightMeter;

// EC
#define ECpin A0

// pH
#define PHpin A1

// Water temp
DS18B20 DS18B20_Sensor(5);

// CRC16 (Modbus)
uint16_t crc16_modbus(const uint8_t *buf, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t pos = 0; pos < len; pos++) {
    crc ^= buf[pos];
    for (int i = 0; i < 8; i++) {
      if (crc & 1) { crc >>= 1; crc ^= 0xA001; }
      else crc >>= 1;
    }
  }
  return crc;
}

void writeFloatLE(float v, uint8_t* out) {
  uint8_t* p = (uint8_t*)&v;
  out[0] = p[0];
  out[1] = p[1];
  out[2] = p[2];
  out[3] = p[3];
}

// ---------------------
//   SEND SENSOR PACKET
// ---------------------
void sendSensorPacket(
  float temperature,
  float humidity,
  float co2,
  float insolation,
  float weight_raw,
  float ph_voltage,
  float ec_voltage,
  float water_temp
) {
  const uint8_t LENGTH = 32;
  uint8_t payload[LENGTH];

  writeFloatLE(temperature, payload + 0);
  writeFloatLE(humidity, payload + 4);
  writeFloatLE(co2, payload + 8);
  writeFloatLE(insolation, payload + 12);
  writeFloatLE(weight_raw, payload + 16);
  writeFloatLE(ph_voltage, payload + 20);
  writeFloatLE(ec_voltage, payload + 24);
  writeFloatLE(water_temp, payload + 28);

  uint8_t crc_input[3 + LENGTH];
  crc_input[0] = HEADER1;
  crc_input[1] = HEADER2;
  crc_input[2] = LENGTH;
  memcpy(crc_input + 3, payload, LENGTH);

  uint16_t crc = crc16_modbus(crc_input, sizeof(crc_input));

  Serial.write(HEADER1);
  Serial.write(HEADER2);
  Serial.write(LENGTH);
  Serial.write(payload, LENGTH);
  Serial.write(crc & 0xFF);
  Serial.write((crc >> 8) & 0xFF);
}

int32_t readCommandPacket() {
  if (Serial.available() < 1) return -1;

  // 동기화: HEADER1 찾기
  if (Serial.read() != HEADER1) return -1;

  while (!Serial.available());
  if (Serial.read() != HEADER2) return -1;

  while (!Serial.available());
  uint8_t length = Serial.read();
  if (length != 4) return -1;

  uint8_t payload[4];
  for (int i = 0; i < 4; i++) {
    while (!Serial.available());
    payload[i] = Serial.read();
  }

  uint8_t crc_low, crc_high;
  while (!Serial.available());
  crc_low = Serial.read();
  while (!Serial.available());
  crc_high = Serial.read();

  uint16_t recv_crc = crc_low | (crc_high << 8);

  uint8_t crc_input[3 + 4];
  crc_input[0] = HEADER1;
  crc_input[1] = HEADER2;
  crc_input[2] = length;
  memcpy(crc_input + 3, payload, 4);

  uint16_t calc_crc = crc16_modbus(crc_input, sizeof(crc_input));

  if (calc_crc != recv_crc) return -1;

  int32_t cmdInt;
  memcpy(&cmdInt, payload, 4);

  return cmdInt;
}

void setup() {
  Serial.begin(9600);
  Serial1.begin(9600);

  dht.begin();
  Wire.begin();
  lightMeter.begin();

  pinMode(SCK, OUTPUT);
  pinMode(DOUT, INPUT);
  pinMode(ECpin, INPUT);
  pinMode(PHpin, INPUT);
}

void loop() {
  // 1) Command Packet 먼저 읽기
  int32_t command = readCommandPacket();
  if (command == 1) {
    // TODO: Implement command actions
  }

  // 2) CO2 센서 polling
  Serial1.write(cmd, 9);
  delay(300);

  if (Serial1.available() >= 9) {
    Serial1.readBytes(response, 9);

    if (response[0] == 0xFF && response[1] == 0x86) {
      byte checksum = calculateChecksum(response);
      if (response[8] == checksum) {

        int co2_ppm = response[2] * 256 + response[3];
        float temp = dht.readTemperature();
        float hum = dht.readHumidity();
        float lux = lightMeter.readLightLevel();
        long raw = ReadRaw();

        float ec_raw = analogRead(ECpin);
        float ec_v = ec_raw * (5.0 / 1023.0);

        int raw_ph = analogRead(PHpin);
        float ph_v = raw_ph * (5.0 / 1023.0);

        float wt = DS18B20_Sensor.getTempC();
        float ins = (lux / 54.0) * (1 / 4.57);

        sendSensorPacket(temp, hum, co2_ppm, ins, (float)raw, ph_v, ec_v, wt);
      }
    }
  }

  delay(1000);
}

// CO2 checksum
byte calculateChecksum(byte *packet) {
  byte checksum = 0;
  for (int i = 1; i < 8; i++) checksum += packet[i];
  checksum = 0xFF - checksum + 1;
  return checksum;
}

long ReadRaw() {
  while (digitalRead(DOUT) == HIGH);
  long value = 0;
  for (int i = 0; i < 24; i++) {
    digitalWrite(SCK, HIGH);
    value <<= 1;
    if (digitalRead(DOUT)) value++;
    digitalWrite(SCK, LOW);
  }
  for (int i = 0; i < 3; i++) {
    digitalWrite(SCK, HIGH);
    digitalWrite(SCK, LOW);
  }
  if (value & 0x800000) value |= 0xFF000000;
  return value;
}
