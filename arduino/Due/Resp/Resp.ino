//  Variables
int RespPin = 0;

unsigned long startMillis;  //some global variables available anywhere in the program
unsigned long currentMillis;
unsigned int respVal = 0;

// The SetUp Function:
void setup() {
   SerialUSB.begin(2000000);         // Set's up Serial Communication at certain speed.
   pinMode(RespPin, INPUT);
   startMillis = millis();  //initial start time
}

// The Main Loop Function
void loop() {
    currentMillis = millis() - startMillis;  //get the current "time" (actually the number of milliseconds since the program started)
    SerialUSB.flush();
    
    analogReadResolution(12);
    respVal = analogRead(RespPin);  // Read the Resp value. Assign this value to the "respVal" variable.  
    
    SerialUSB.print(respVal);                    // Send the respVal value to Serial.
    SerialUSB.print(",");
    SerialUSB.println(currentMillis);    

    delayMicroseconds(3560); // 250 samples per second, ~0.5ms spent in processing    
}
