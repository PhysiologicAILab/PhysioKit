//  Variables
int EDAPin = 0;
int RespPin = 1;
int PulseSensor1Pin = 2;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 2

unsigned long startMillis;  //some global variables available anywhere in the program
unsigned long currentMillis;
unsigned int edaVal = 0;
unsigned int respVal = 0;
unsigned int ppg1Val = 0;
  
// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(EDAPin, INPUT);
   pinMode(RespPin, INPUT);
   pinMode(PulseSensor1Pin, INPUT);
   startMillis = millis();  //initial start time
}

// The Main Loop Function
void loop() {
    
    currentMillis = millis() - startMillis;  //get the current "time" (actually the number of milliseconds since the program started)
    Serial.flush();

    edaVal = analogRead(EDAPin);  // Read the EDA value. Assign this value to the "edaVal" variable.
    respVal = analogRead(RespPin);  // Read the Resp value. Assign this value to the "respVal" variable.  
    ppg1Val = analogRead(PulseSensor1Pin);  // Read the PulseSensor1 value. Assign this value to the "ppg1Val" variable.
    Serial.print(edaVal);                    // Send the edaVal value to Serial.
    Serial.print(",");
    Serial.print(respVal);                    // Send the respVal value to Serial.
    Serial.print(",");
    Serial.print(ppg1Val);                    // Send the ppg1Val value to Serial.
    Serial.print(",");
    Serial.println(currentMillis);    

    //delay(3); // 250 samples per second, 1ms is spent in processing
    delayMicroseconds(3000);
}
