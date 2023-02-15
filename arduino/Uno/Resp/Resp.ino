//  Variables
int RespPin = 0;

int sampling_rate = 250;
int inter_sample_interval_us = int(round(float(1000000 / sampling_rate)));

unsigned long startMicros = 0; // some global variables available anywhere in the program
int processTimeMicros = 0;
int delayMicros = 0;

unsigned int respVal = 0;
  
// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(RespPin, INPUT);
}

// The Main Loop Function
void loop() {
   startMicros = micros(); // initial start time
   Serial.flush();

   respVal = analogRead(RespPin); // Read the Resp value. Assign this value to the "respVal" variable.
   Serial.print(respVal);         // Send the respVal value to Serial.
   Serial.print(",");
   processTimeMicros = micros() - startMicros; // get the current "time" (actually the number of microseconds since the program started)
   Serial.println(processTimeMicros);

   processTimeMicros = processTimeMicros + 150;
   if (inter_sample_interval_us > processTimeMicros)
   {
       delayMicros = inter_sample_interval_us - processTimeMicros;
       delayMicroseconds(delayMicros);
   }
}
