//  Variables
int EDAPin = 0;

unsigned long startMillis;  //some global variables available anywhere in the program
unsigned long currentMillis;
unsigned int edaVal = 0;
  
// The SetUp Function:
void setup() {
   SerialUSB.begin(2000000);         // Set's up Serial Communication at certain speed.
   pinMode(EDAPin, INPUT);
   startMillis = millis();  //initial start time
}

// The Main Loop Function
void loop() {
    
    currentMillis = millis() - startMillis;  //get the current "time" (actually the number of milliseconds since the program started)
    SerialUSB.flush();
    
    analogReadResolution(12);
    edaVal = analogRead(EDAPin);  // Read the EDA value. Assign this value to the "edaVal" variable.
    
    SerialUSB.print(edaVal);                    // Send the edaVal value to Serial.
    SerialUSB.print(",");
    SerialUSB.println(currentMillis);    

    delayMicroseconds(3560); // 250 samples per second, ~0.5ms spent in processing
}
