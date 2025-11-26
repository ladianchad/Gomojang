#include <Wire.h>
#include <BH1750.h>
#include <DHT.h>
#include <OneWire.h>
#include <DS18B20.h>

// --- sensor settings ---

// Temp, humidity
#define DHTPIN 7
#define DHTTYPE DHT22
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


// --- setup ---
void setup() {
  Serial.begin(9600);
  while (!Serial) {
    delay(10);
  }

  Serial1.begin(9600);      // CO2
  dht.begin();              // TH
  Wire.begin();             // Light
  lightMeter.begin();       // Light
  pinMode(SCK, OUTPUT);     // HX711
  pinMode(DOUT, INPUT);     // HX711
  pinMode(ECpin, INPUT);     // EC
  pinMode(PHpin, INPUT); // pH raw
  
  //Serial.println("Initialization done!!!");
}

void loop() {
  Serial1.write(cmd, 9);
  delay(500);
  if (Serial1.available() >= 9) {
    Serial1.readBytes(response, 9);

    if (response[0] == 0xFF && response[1] == 0x86) {
      byte checksum = calculateChecksum(response);
      if (response[8] == checksum) {
        int co2_ppm = response[2] * 256 + response[3];
        float temperature = dht.readTemperature();
        float humidity = dht.readHumidity();
        float lux = lightMeter.readLightLevel();
        long raw_weight = ReadRaw();
        

        float raw_EC = analogRead(ECpin);
        float EC_voltage =  raw_EC * (5.0 / 1023.0);
        int raw_PH = analogRead(PHpin);
        float PH_voltage = raw_PH * (5.0 / 1023.0);
        float water_temp = DS18B20_Sensor.getTempC();
        float insolation = ((lux/54)*(1/4.57));

        Serial.print(temperature);
        Serial.print(",");
        Serial.print(humidity);
        Serial.print(",");
        Serial.print(co2_ppm);
        Serial.print(","); 
        Serial.print(insolation);
        Serial.print(",");
        Serial.print(raw_weight);
        Serial.print(",");
        Serial.print(PH_voltage);
        Serial.print(",");
        Serial.print(EC_voltage);
        Serial.print(",");
        Serial.println(water_temp);
      } 
    } 
  } else {
    while (Serial1.available()) { Serial1.read(); }
  }

  delay(1000); // 2초마다 전체 측정 과정 반복
}


// CO2 checksum
byte calculateChecksum(byte *packet) {
  byte checksum = 0;
  for (int i = 1; i < 8; i++) {
    checksum += packet[i];
  }
  checksum = 0xFF - checksum;
  checksum += 1;
  return checksum;
}

// read raw scale
long ReadRaw() {
  while (digitalRead(DOUT) == HIGH);
  long value = 0;
  for (int i = 0; i < 24; i++) {
    digitalWrite(SCK, HIGH);
    value = value << 1;
    if (digitalRead(DOUT) == HIGH) value++;
    digitalWrite(SCK, LOW);
  }
  for (int i = 0; i < 3; i++) {
    digitalWrite(SCK, HIGH);
    digitalWrite(SCK, LOW);
  }
  if (value & 0x800000) value |= 0xFF000000;
  return value;
}

