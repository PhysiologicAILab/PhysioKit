//  Variables
int RespPin = 0;
int sampling_rate = 250;
int inter_sample_interval_us = int(round(float(1000000 / sampling_rate)));

unsigned long startMicros; // some global variables available anywhere in the program
int processTimeMicros = 0;
int delayMicros = 0;

unsigned int respVal = 0;

// The SetUp Function:
void setup() {
   SerialUSB.begin(2000000);         // Set's up Serial Communication at certain speed.
   pinMode(RespPin, INPUT);
}

// The Main Loop Function
void loop() {
   startMicros = micros(); // get the current "time" (actually the number of milliseconds since the program started)
   SerialUSB.flush();

   analogReadResolution(12);
   respVal = analogRead(RespPin); // Read the Resp value. Assign this value to the "respVal" variable.

   SerialUSB.print(respVal); // Send the respVal value to Serial.
   SerialUSB.print(",");
   processTimeMicros = micros() - startMicros; // get the current "time" (actually the number of microseconds since the program started)
   SerialUSB.println(processTimeMicros);

   processTimeMicros = processTimeMicros + 150;
   if ((inter_sample_interval_us - processTimeMicros) > 0)
   {
       delayMicros = inter_sample_interval_us - processTimeMicros;
       delayMicroseconds(delayMicros);
   }
}
