//  Variables
int APin = 0;               // Sensor1 connected to ANALOG PIN 0
int sampling_rate = 250;
long int baudrate = 2000000;

unsigned int aVal = 0;        // holds the incoming raw data. Signal value can range from 0-4096

// To compute: inter_sample_interval_us
//int(round(float(1000/sampling_rate))) ->use this formula to calculate. Here it can not be made dymanic due to library limitation
// Also account for the average processing delay, and substract from the value, e.g. for 250 sampling rate, 4 - 0.35
// 0.05 -> ADC, 0.1 - serial.Print, 0.05 - Misc
int inter_sample_interval_us = int(3.65 * 1000);

// The SetUp Function:
void setup() {
   SerialUSB.begin(baudrate);         // Set's up Serial Communication at certain speed.
   pinMode(APin, INPUT);
}

// The Main Loop Function
void loop() {
    analogReadResolution(12);
    aVal = analogRead(APin);  // Read the Sensor1 value. Assign this value to the "aVal" variable.
        
    SerialUSB.println(aVal);   // Send the aVal value to Serial.
    noInterrupts();
    delayMicroseconds(inter_sample_interval_us);
    interrupts();
}
