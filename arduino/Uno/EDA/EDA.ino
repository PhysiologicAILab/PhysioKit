//  Variables
int EDAPin = 0;

unsigned long startMillis;  //some global variables available anywhere in the program
unsigned long currentMillis;
unsigned int edaVal = 0;
  
// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(EDAPin, INPUT);
   startMillis = millis();  //initial start time
}

// The Main Loop Function
void loop() {
    
    currentMillis = millis() - startMillis;  //get the current "time" (actually the number of milliseconds since the program started)
    Serial.flush();

    edaVal = analogRead(EDAPin);  // Read the EDA value. Assign this value to the "edaVal" variable.
    Serial.print(edaVal);                    // Send the edaVal value to Serial.
    Serial.print(",");
    Serial.println(currentMillis);    

    //delay(3); // 250 samples per second, 1ms is spent in processing
    delayMicroseconds(3000);
}
