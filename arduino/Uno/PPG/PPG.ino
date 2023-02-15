//  Variables
int PulseSensor1Pin = 0;        // Pulse Sensor PURPLE WIRE connected to ANALOG PIN 2
int sampling_rate = 250;
int inter_sample_interval_us = int(round(float(1000000 / sampling_rate)));

unsigned long startMicros = 0; // some global variables available anywhere in the program
int processTimeMicros = 0;
int delayMicros = 0;
unsigned int ppg1Val = 0;

// The SetUp Function:
void setup() {
   Serial.begin(115200);         // Set's up Serial Communication at certain speed.
   pinMode(PulseSensor1Pin, INPUT);
}

// The Main Loop Function
void loop() {
   startMicros = micros(); // initial start time
   Serial.flush();

   ppg1Val = analogRead(PulseSensor1Pin); // Read the PulseSensor1 value. Assign this value to the "ppg1Val" variable.
   Serial.print(ppg1Val);                 // Send the ppg1Val value to Serial.
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
