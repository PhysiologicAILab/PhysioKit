//  Variables
int EDAPin = 0;
int sampling_rate = 250;
int inter_sample_interval_us = int(round(float(1000000/sampling_rate)));

unsigned long startMicros;  //some global variables available anywhere in the program
int processTimeMicros = 0;
int delayMicros = 0;
unsigned int edaVal = 0;
  
// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(EDAPin, INPUT);
}

// The Main Loop Function
void loop() {
    startMicros = micros();  //get the current "time" (actually the number of milliseconds since the program started)
    Serial.flush();

    edaVal = analogRead(EDAPin);  // Read the EDA value. Assign this value to the "edaVal" variable.
    Serial.print(edaVal);                    // Send the edaVal value to Serial.
    Serial.print(",");
    processTimeMicros = micros() - startMicros;  // get the current "time" (actually the number of microseconds since the program started)
    Serial.println(processTimeMicros);

    processTimeMicros = processTimeMicros + 150;
    if ((inter_sample_interval_us - processTimeMicros) > 0)
    {
      delayMicros = inter_sample_interval_us - processTimeMicros;
      delayMicroseconds(delayMicros);
    }
}
