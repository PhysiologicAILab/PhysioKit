//  Variables
int EDAPin = 0;

unsigned long startMicros;  //some global variables available anywhere in the program
int processTimeMicros = 0;
int delayMicros = 0;
unsigned int edaVal = 0;
  
// The SetUp Function:
void setup() {
   SerialUSB.begin(2000000);         // Set's up Serial Communication at certain speed.
   pinMode(EDAPin, INPUT);
}

// The Main Loop Function
void loop() {
    
    startMicros = micros();  //get the current "time" (actually the number of milliseconds since the program started)
    SerialUSB.flush();
    
    analogReadResolution(12);
    edaVal = analogRead(EDAPin);  // Read the EDA value. Assign this value to the "edaVal" variable.
    
    SerialUSB.print(edaVal);                    // Send the edaVal value to Serial.
    SerialUSB.print(",");

    processTimeMicros = micros() - startMicros;  //get the current "time" (actually the number of microseconds since the program started)
    SerialUSB.println(processTimeMicros);

    processTimeMicros = processTimeMicros + 50;
    if ((4000 - processTimeMicros) > 0)
    {
      delayMicros = 4000 - processTimeMicros;
    }
    else
    {
      delayMicros = 1;
    }

    delayMicroseconds(delayMicros); // 250 samples per second, ~0.6ms spent in processing

}
