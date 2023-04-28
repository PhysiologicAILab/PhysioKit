#include <util/delay.h>

//  Variables
int APin = 0;               // Sensor1 connected to ANALOG PIN 0
int BPin = 1;               // Sensor2 connected to ANALOG PIN 1
int CPin = 2;               // Sensor3 connected to ANALOG PIN 2
int DPin = 3;               // Sensor4 connected to ANALOG PIN 3
int sampling_rate = 250;
long int baudrate = 115200;

unsigned int aVal = 0;      // holds the incoming raw data. Signal value can range from 0-1024
unsigned int bVal = 0;      // holds the incoming raw data. Signal value can range from 0-1024
unsigned int cVal = 0;      // holds the incoming raw data. Signal value can range from 0-1024   
unsigned int dVal = 0;      // holds the incoming raw data. Signal value can range from 0-1024

// To compute: inter_sample_interval_us
//int(round(float(1000/sampling_rate))) ->use this formula to calculate. Here it can not be made dymanic due to library limitation
// Also account for the average processing delay, and substract from the value, e.g. for 250 sampling rate, 4 - 1.3
// 0.1 -> ADC, 0.2 - serial.Print, 0.1 - Misc
double inter_sample_interval_us = 2.7;
  

// The SetUp Function:
void setup() {
    Serial.begin(baudrate);         // Set's up Serial Communication at certain speed.
    pinMode(APin, INPUT);
    pinMode(BPin, INPUT);
    pinMode(CPin, INPUT);
    pinMode(DPin, INPUT);
}

// The Main Loop Function
void loop() {    
    aVal = analogRead(APin);  // Read the Sensor1 value. Assign this value to the "aVal" variable.
    bVal = analogRead(BPin);  // Read the Sensor2 value. Assign this value to the "bVal" variable.  
    cVal = analogRead(CPin);  // Read the Sensor3 value. Assign this value to the "cVal" variable.
    dVal = analogRead(DPin);  // Read the Sensor4 value. Assign this value to the "dVal" variable.                                             

    Serial.print(aVal);         // Send the aVal value to Serial.
    Serial.print(",");
    Serial.print(bVal);         // Send the bVal value to Serial.
    Serial.print(",");
    Serial.print(cVal);         // Send the cVal value to Serial.
    Serial.print(",");
    Serial.println(dVal);       // Send the dVal value to Serial.
    noInterrupts();
    _delay_ms(inter_sample_interval_us);
    interrupts();
}
