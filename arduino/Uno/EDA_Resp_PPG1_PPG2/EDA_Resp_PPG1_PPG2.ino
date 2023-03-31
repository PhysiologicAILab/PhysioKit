//  Variables
int EDAPin = 0;
int RespPin = 1;
int PulseSensor1Pin = 2;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 2
int PulseSensor2Pin = 3;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 3
int sampling_rate = 250;

unsigned long startMicros = 0;  //some global variables available anywhere in the program
int processTimeMicros = 0;
int delayMicros = 0;
unsigned int edaVal = 0;
unsigned int respVal = 0;
unsigned int ppg1Val = 0;
unsigned int ppg2Val = 0;                // holds the incoming raw data. Signal value can range from 0-1024
int inter_sample_interval_us = int(round(float(1000000/sampling_rate)));
  
// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(EDAPin, INPUT);
   pinMode(RespPin, INPUT);
   pinMode(PulseSensor1Pin, INPUT);
   pinMode(PulseSensor2Pin, INPUT);
}

// The Main Loop Function
void loop() {    
    startMicros = micros();  //initial start time
    Serial.flush();
    
    edaVal = analogRead(EDAPin);  // Read the EDA value. Assign this value to the "edaVal" variable.
    respVal = analogRead(RespPin);  // Read the Resp value. Assign this value to the "respVal" variable.  
    ppg1Val = analogRead(PulseSensor1Pin);  // Read the PulseSensor1 value. Assign this value to the "ppg1Val" variable.
    ppg2Val = analogRead(PulseSensor2Pin);  // Read the PulseSensor2 value. Assign this value to the "ppg2Val" variable.                                             

    Serial.print(edaVal);                    // Send the edaVal value to Serial.
    Serial.print(",");
    Serial.print(respVal);                    // Send the respVal value to Serial.
    Serial.print(",");
    Serial.print(ppg1Val);                    // Send the ppg1Val value to Serial.
    Serial.print(",");
    Serial.print(ppg2Val);                    // Send the ppg2Val value to Serial.
    Serial.print(",");
    processTimeMicros = micros() - startMicros;  //get the current "time" (actually the number of microseconds since the program started)
    Serial.println(processTimeMicros);    

    processTimeMicros = processTimeMicros + 150;
    if (inter_sample_interval_us > processTimeMicros)
    {
      delayMicros = inter_sample_interval_us - processTimeMicros;
      delayMicroseconds(delayMicros);
    }
}
