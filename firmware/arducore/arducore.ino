// ArduCore v0.6 - HC-SR04 + LM35 + Buzzer + Servo

#include <Servo.h>

// --- STATE ---------------------------------------
typedef enum {
  STATE_IDLE,
  STATE_AUTO,
  STATE_MANUAL,
  STATE_ALARM,
  STATE_FAULT
} SystemState;

volatile SystemState currentState = STATE_AUTO;

// --- HC-SR04 -------------------------------------
#define TRIG_PIN       4
#define ECHO_PIN       6
#define ALARM_DISTANCE 20.0f

volatile uint32_t echoStart    = 0;
volatile uint32_t echoDuration = 0;
volatile bool     echoReady    = false;

uint32_t lastTrigger = 0;
#define TRIGGER_INTERVAL 100

float lastDist   = 0.0f;
bool  alarmState = false;

ISR(PCINT2_vect) {
  if (PIND & (1 << PD6)) {
    echoStart = micros();
  } else {
    echoDuration = micros() - echoStart;
    echoReady    = true;
  }
}

void triggerSensor() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
}

float readDistance() {
  if (!echoReady) return -1.0f;
  echoReady = false;
  return (echoDuration * 0.0343f) / 2.0f;
}

// --- LM35 ----------------------------------------
#define LM35_PIN   A0
#define TEMP_ALARM 35.0f

float lastTemp = 0.0f;

float readTemp() {
  int32_t sum = 0;
  for (uint8_t i = 0; i < 4; i++) {
    sum += analogRead(LM35_PIN);
    delayMicroseconds(100);
  }
  return ((sum / 4) * 5000.0f / 1023.0f) / 10.0f;
}

// --- BUZZER --------------------------------------
#define BUZZER_PIN 7

// --- SERVO ---------------------------------------
#define SERVO_PIN 9
Servo lockServo;

// --- UART PROTOCOL -------------------------------
#define STX      0x02
#define ETX      0x03
#define BUF_SIZE 64

volatile uint8_t rxBuf[BUF_SIZE];
volatile uint8_t rxHead = 0;
volatile uint8_t rxTail = 0;

#define CMD_SET_MODE   0x01
#define CMD_SET_SPEED  0x02
#define CMD_GET_STATUS 0x03
#define CMD_RESET      0xFF

// --- TIMERS --------------------------------------
uint32_t lastTelemetry = 0;
uint32_t lastTempRead  = 0;
#define TELEMETRY_INTERVAL 500
#define TEMP_INTERVAL      200

// --- RING BUFFER ---------------------------------
void bufWrite(uint8_t byte) {
  uint8_t next = (rxHead + 1) % BUF_SIZE;
  if (next != rxTail) {
    rxBuf[rxHead] = byte;
    rxHead = next;
  }
}

int16_t bufRead() {
  if (rxHead == rxTail) return -1;
  uint8_t byte = rxBuf[rxTail];
  rxTail = (rxTail + 1) % BUF_SIZE;
  return byte;
}

// --- FORWARD DECLARATION -------------------------
void sendTelemetry();

// --- COMMAND HANDLER -----------------------------
void processCommand(uint8_t cmd, uint8_t data) {
  switch (cmd) {
    case CMD_SET_MODE:
      if (data < 5) currentState = (SystemState)data;
      break;
    case CMD_RESET:
      currentState = STATE_AUTO;
      alarmState   = false;
      digitalWrite(BUZZER_PIN, LOW);
      lockServo.write(0);
      break;
    case CMD_GET_STATUS:
      sendTelemetry();
      break;
  }
}

// --- FRAME PARSER --------------------------------
void parseBuffer() {
  static uint8_t stage    = 0;
  static uint8_t cmd      = 0;
  static uint8_t data     = 0;
  static uint8_t checksum = 0;

  int16_t b;
  while ((b = bufRead()) != -1) {
    switch (stage) {
      case 0: if (b == STX) stage = 1; break;
      case 1: cmd = b; checksum = b; stage = 2; break;
      case 2: data = b; checksum ^= b; stage = 3; break;
      case 3:
        if (checksum == b) processCommand(cmd, data);
        stage = 4; break;
      case 4: if (b == ETX) stage = 0; break;
    }
  }
}

// --- TELEMETRY -----------------------------------
void sendTelemetry() {
  Serial.print(F("{\"state\":"));
  Serial.print(currentState);
  Serial.print(F(",\"dist\":"));
  Serial.print(lastDist, 1);
  Serial.print(F(",\"temp\":"));
  Serial.print(lastTemp, 1);
  Serial.print(F(",\"alarm\":"));
  Serial.print(alarmState ? F("true") : F("false"));
  Serial.print(F("}\r\n"));
}

// --- STATE MACHINE -------------------------------
void runStateMachine() {
  switch (currentState) {
    case STATE_IDLE:
      digitalWrite(BUZZER_PIN, LOW);
      lockServo.write(0);
      break;
    case STATE_AUTO:
      if ((lastDist > 0.0f && lastDist < ALARM_DISTANCE) ||
           lastTemp > TEMP_ALARM) {
        alarmState   = true;
        currentState = STATE_ALARM;
      }
      break;
    case STATE_MANUAL:
      break;
    case STATE_ALARM:
      digitalWrite(BUZZER_PIN, HIGH);
      lockServo.write(180);
      if (lastDist > ALARM_DISTANCE) {
        alarmState   = false;
        currentState = STATE_AUTO;
        digitalWrite(BUZZER_PIN, LOW);
        lockServo.write(0);
      }
      break;
    case STATE_FAULT:
      break;
  }
}

// --- SETUP ---------------------------------------
void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN,   OUTPUT);
  pinMode(ECHO_PIN,   INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  lockServo.attach(SERVO_PIN);
  lockServo.write(0);

  // PCINT22 = D6 -> PCIE2
  PCICR  |= (1 << PCIE2);
  PCMSK2 |= (1 << PCINT22);
  sei();

  Serial.println(F("ArduCore v0.6 READY"));
}

// --- LOOP ----------------------------------------
void loop() {
  while (Serial.available()) {
    bufWrite((uint8_t)Serial.read());
  }

  parseBuffer();

  uint32_t now = millis();

  if (now - lastTrigger >= TRIGGER_INTERVAL) {
    lastTrigger = now;
    triggerSensor();
  }

  float d = readDistance();
  if (d > 0.0f && d < 400.0f) lastDist = d;

  if (now - lastTempRead >= TEMP_INTERVAL) {
    lastTempRead = now;
    lastTemp = readTemp();
  }

  runStateMachine();

  if (now - lastTelemetry >= TELEMETRY_INTERVAL) {
    lastTelemetry = now;
    sendTelemetry();
  }
}
