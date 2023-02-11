//  Variables
int RespPin = 0;

unsigned long startMillis;  //some global variables available anywhere in the program
unsigned long currentMillis;
unsigned int respVal = 0;

  
// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(RespPin, INPUT);
   startMillis = millis();  //initial start time
}

// The Main Loop Function
void loop() {
    
    currentMillis = millis() - startMillis;  //get the current "time" (actually the number of milliseconds since the program started)
    Serial.flush();
    
    respVal = analogRead(RespPin);  // Read the Resp value. Assign this value to the "respVal" variable.  
    Serial.print(respVal);                    // Send the respVal value to Serial.
    Serial.print(",");
    Serial.println(currentMillis);    
    //delay(3); // 250 samples per second, 1ms is spent in processing
    delayMicroseconds(3000);
}
