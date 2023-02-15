//  Variables
int PulseSensor1Pin = 0;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 2
int PulseSensor2Pin = 1;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 3

int sampling_rate = 250;
int inter_sample_interval_us = int(round(float(1000000 / sampling_rate)));

unsigned long startMicros = 0; // some global variables available anywhere in the program
int processTimeMicros = 0;
int delayMicros = 0;

unsigned int ppg1Val = 0;
unsigned int ppg2Val = 0;                // holds the incoming raw data. Signal value can range from 0-1024

// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(PulseSensor1Pin, INPUT);
   pinMode(PulseSensor2Pin, INPUT);
}

// The Main Loop Function
void loop() {
   startMicros = micros(); // initial start time
   Serial.flush();

   ppg1Val = analogRead(PulseSensor1Pin); // Read the PulseSensor1 value. Assign this value to the "ppg1Val" variable.
   ppg2Val = analogRead(PulseSensor2Pin); // Read the PulseSensor2 value. Assign this value to the "ppg2Val" variable.

   Serial.print(ppg1Val); // Send the ppg1Val value to Serial.
   Serial.print(",");
   Serial.print(ppg2Val); // Send the ppg2Val value to Serial.
   Serial.print(",");
   processTimeMicros = micros() - startMicros; // get the current "time" (actually the number of microseconds since the program started)
   Serial.println(processTimeMicros);

   processTimeMicros = processTimeMicros + 150;
   if (inter_sample_interval_us > processTimeMicros)
   {
       delayMicros = inter_sample_interval_us - processTimeMicros;
       delayMicroseconds(delayMicros);
    }
}
