//  Variables
int EDAPin = 0;
int RespPin = 1;
int PulseSensor1Pin = 2;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 2
int PulseSensor2Pin = 3;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 3

unsigned long startMicros = 0;  //some global variables available anywhere in the program
int processTimeMicros = 0;
int delayMicros = 0;
unsigned int edaVal = 0;
unsigned int respVal = 0;
unsigned int ppg1Val = 0;
unsigned int ppg2Val = 0;                // holds the incoming raw data. Signal value can range from 0-1024

  
// The SetUp Function:
void setup() {
   SerialUSB.begin(2000000);         // Set's up Serial Communication at certain speed.
   pinMode(EDAPin, INPUT);
   pinMode(RespPin, INPUT);
   pinMode(PulseSensor1Pin, INPUT);
   pinMode(PulseSensor2Pin, INPUT);
}

// The Main Loop Function
void loop() {
    
    startMicros = micros();  //initial start time
    SerialUSB.flush();
    
    analogReadResolution(12);
    edaVal = analogRead(EDAPin);  // Read the EDA value. Assign this value to the "edaVal" variable.
    
    analogReadResolution(12);
    respVal = analogRead(RespPin);  // Read the Resp value. Assign this value to the "respVal" variable.  
    
    analogReadResolution(12);
    ppg1Val = analogRead(PulseSensor1Pin);  // Read the PulseSensor1 value. Assign this value to the "ppg1Val" variable.
    
    analogReadResolution(12);
    ppg2Val = analogRead(PulseSensor2Pin);  // Read the PulseSensor2 value. Assign this value to the "ppg2Val" variable.                                             

    SerialUSB.print(edaVal);                    // Send the edaVal value to Serial.
    SerialUSB.print(",");
    SerialUSB.print(respVal);                    // Send the respVal value to Serial.
    SerialUSB.print(",");
    SerialUSB.print(ppg1Val);                    // Send the ppg1Val value to Serial.
    SerialUSB.print(",");
    SerialUSB.print(ppg2Val);                    // Send the ppg2Val value to Serial.
    SerialUSB.print(","); 
    processTimeMicros = micros() - startMicros;  //get the current "time" (actually the number of microseconds since the program started)
    SerialUSB.println(processTimeMicros);

    processTimeMicros = processTimeMicros + 100;
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
