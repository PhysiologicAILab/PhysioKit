//  Variables
int PulseSensor1Pin = 0;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 2

unsigned long startMillis;  //some global variables available anywhere in the program
unsigned long currentMillis;
unsigned int ppg1Val = 0;

  
// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(PulseSensor1Pin, INPUT);
   startMillis = millis();  //initial start time
}

// The Main Loop Function
void loop() {
    
    currentMillis = millis() - startMillis;  //get the current "time" (actually the number of milliseconds since the program started)
    Serial.flush();
    
    ppg1Val = analogRead(PulseSensor1Pin);  // Read the PulseSensor1 value. Assign this value to the "ppg1Val" variable.
    Serial.print(ppg1Val);                    // Send the ppg1Val value to Serial.
    Serial.print(",");
    Serial.println(currentMillis);    
    //delay(3); // 250 samples per second, 1ms is spent in processing
    delayMicroseconds(3000);
}
