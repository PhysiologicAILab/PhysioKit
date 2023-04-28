#include <util/delay.h>

//  Variables
int APin = 0;
int sampling_rate = 250;
long int baudrate = 115200;

unsigned int aVal = 0;

// To compute: inter_sample_interval_us
//int(round(float(1000/sampling_rate))) ->use this formula to calculate. Here it can not be made dymanic due to library limitation
// Also account for the average processing delay, and substract from the value, e.g. for 250 sampling rate, 4 - 0.4
// 0.1 -> ADC, 0.2 - serial.Print, 0.1 - Misc
double inter_sample_interval_us = 3.6;
  
// The SetUp Function:
void setup() {
   Serial.begin(baudrate);         // Set's up Serial Communication at certain speed.
   pinMode(APin, INPUT);
}

// The Main Loop Function
void loop() {
    aVal = analogRead(APin);  // Read the sensor value. Assign this value to the "aVal" variable.
    Serial.println(aVal);                    // Send the aVal value to Serial.
    noInterrupts();
    _delay_ms(inter_sample_interval_us);
    interrupts();
}
