// Power supply control software for Controllino Mega.
// Accepts input from custom switch board and serial commands.
// Generates both solicited and unsolicited output on serial port.

// Beeps and flashes obnoxiously if in error state.

// All serial I/O is ASCII text.
// First character indicates message type. Followed by space, then message.
// All messages are exactly one line in length.

// 'C' indicates that the device reCeived a serial command.
// 'X' indicates than an eXternal event occurred.
// 'E' indicates an Error report.
// 'I' indicates an Informative message intended for a human to parse
// 'M' indicates a Monitoring message intended for human and computer consumption
// 'R' indicates a Response to the last command.
// '>' indicates that the device is ready to accept commands.
// '!' indicates that the device is in an inconsistent state.

// For usage help, send "help" via serial.
//
// (C) 2016 John Hedditch

#include <Controllino.h>
#include <TimerOne.h>

#define SOFTWARE_VERSION "2016-08-09"
#define SOFTWARE_ID "pulse_control"

// Serial config
#define BUFFER_LENGTH          40
#define COMMAND_LENGTH         16
#define EOS_TERMINATOR_CHAR    '\n'
#define UNDEFINED              -1
#define BAUD_RATE 115200
char inputString[BUFFER_LENGTH + 1];
char strPtr;
boolean stringComplete;
long arg1;
long arg2;
char baseCmd[COMMAND_LENGTH + 1];

// Pin Assignments
#define TRIG1_PROBE CONTROLLINO_D0
#define TRIG2_PROBE CONTROLLINO_D1
#define TRIG3_PROBE CONTROLLINO_D2
#define TRIG4_PROBE CONTROLLINO_D3
#define TRIGHV_PROBE CONTROLLINO_D4

#define PROBE_AUTO CONTROLLINO_A1
#define PROBE_MANUAL CONTROLLINO_A2
#define PROBE_TRIGGER CONTROLLINO_A3

#define STROBE_OUTPUT CONTROLLINO_D18
#define ACTIVE_LED CONTROLLINO_D19

#define CHG_POWER CONTROLLINO_R13
#define CHG_ENBL CONTROLLINO_R14
#define CHG      CONTROLLINO_R15

#define PANEL_HV_MANUAL CONTROLLINO_A12
#define PANEL_HV_AUTO   CONTROLLINO_A13
#define REMOTE_HV_ON    CONTROLLINO_R7
#define HV_ENABLE       CONTROLLINO_R6
#define LOCAL_VOLTAGE_CONTROL CONTROLLINO_R8
#define REMOTE_VOLTAGE_CONTROL CONTROLLINO_R9
#define REMOTE_VREF_0_10V CONTROLLINO_D9

#define HV_VOLTAGE_DETECT CONTROLLINO_A15
#define HV_CURRENT_DETECT CONTROLLINO_A14

#define ANNOYING_BEEPER CONTROLLINO_D17

#define BANK1_L CONTROLLINO_A4
#define BANK1_U CONTROLLINO_A5
#define BANK2_L CONTROLLINO_A6
#define BANK2_U CONTROLLINO_A7
#define BANK3_L CONTROLLINO_A8
#define BANK3_U CONTROLLINO_A9
#define BANK4_L CONTROLLINO_A10
#define BANK4_U CONTROLLINO_A11

const int voltage_margin = 200; // Permissible slack in HV voltage.

// Device Parameters
#define NBANKS 4 // Capacitor bank groups
#define HV_MIN_VOLTAGE 0
#define HV_MAX_VOLTAGE 50000
#define HV_TIMEOUT 4000

#define CHARGE_TIMEOUT_MS 45000

long PANEL_HV_MANUAL_LAST = 2; // Set to 2 to force state change on first loop.
long PANEL_HV_AUTO_LAST = 2;   // Set to 2 to force state change on first loop.
int TRIG_PROBES[] = {TRIG1_PROBE, TRIG2_PROBE, TRIG3_PROBE, TRIG4_PROBE, TRIGHV_PROBE};
int TRIG_OUTPUT_PINS[] = {CONTROLLINO_D5, CONTROLLINO_D6, CONTROLLINO_D7, CONTROLLINO_D8, CONTROLLINO_D10};


const long trig_starts_default[] = {0, 0, 0, 0, 220};   // pulse pre-start delay
const long trig_stops_default[] =  {2000, 2000, 2000, 2000, 1220};  // pulse stops
long trig_starts[] = {0, 0, 0, 0, 220};
long trig_stops[] =  {2000, 2000, 2000, 2000, 1220};

long last_pulse;       // at what time did we last fire the banks?
long dead_time = 1000; // milliseconds required between pulses;

long requested_hv_voltage = 0;
int requested_charge_power = 0;
int requested_charge_enable = 0;
int polling = 0; // are we polling for status right now?
long last_poll = 0;
const int poll_interval = 100; // milliseconds between status updates when polling.



#define N_CAL_ENTRIES 207
// Calibration table for Spellman HV Supply:
// hv_in_table is the ADC value
// hv_actual_table is voltages (in kV, read from spellman front panel)
long hv_in_table[N_CAL_ENTRIES] =  {
  0,   0,   4,   7,   10,   13,   16,   19,   23,   26,
  29,  32,  35,  38,   42,   45,   48,   51,   54,   57,
  61,  64,  67,  70,   73,   76,   79,   83,   86,   89,
  92,  95,  99, 101,  105,  108,  111,  114,  117,  120,
  123, 127, 130, 133,  136,  139,  143,  146,  149,  152,
  155, 158, 161, 164,  168,  171,  174,  177,  180,  183,
  186, 190, 193, 196,  199,  202,  205,  209,  212,  215,
  218, 221, 224, 227,  230,  233,  237,  240,  243,  246,
  249, 252, 256, 259,  262,  265,  268,  271,  275,  278,
  281, 284, 287, 290,  294,  297,  300,  303,  306,  309,
  312, 315, 319, 322,  325,  328,  331,  335,  338,  341,
  344, 347, 351, 353,  356,  360,  363,  366,  369,  372,
  375, 378, 382, 385,  388,  391,  394,  398,  401,  404,
  408, 410, 414, 417,  420,  423,  426,  429,  432,  436,
  439, 442, 445, 448,  452,  455,  458,  461,  464,  467,
  471, 474, 477, 480,  483,  486,  489,  493,  496,  499,
  502, 505, 509, 511,  514,  518,  521,  524,  527,  531,
  533, 536, 540, 543,  546,  549,  553,  555,  559,  562,
  565, 568, 572, 574,  577,  581,  585,  587,  591,  593,
  597, 600, 603, 606,  609,  613,  616,  619,  622,  625,
  628, 631, 635, 638,  641,  644,  647
};

double hv_actual_table[N_CAL_ENTRIES] = {
  0.0,   0.3,   0.5,   0.8,   1.0,   1.2,   1.5,   1.7,   2.0,   2.2,
  2.4,   2.7,   2.9,   3.2,   3.4,   3.7,   3.9,   4.1,   4.4,   4.6,
  4.9,   5.1,   5.4,   5.6,   5.8,   6.1,   6.3,   6.6,   6.8,   7.0,
  7.3,   7.5,   7.8,   8.0,   8.3,   8.5,   8.7,   9.0,   9.2,   9.5,
  9.7,  10, 0,  10.2,  10.4,  10.7,  10.9,  11.2,  11.4,  11.6,  11.9,
  12.1, 12.4,  12.6,  12.9,  13.1,  13.3,  13.6,  13.8,  14.1,  14.3,
  14.6, 14.8,  15.0,  15.3,  15.5,  15.8,  16.0,  16.2,  16.5,  16.7,
  17.0, 17.2,  17.5,  17.7,  17.9,  18.2,  18.4,  18.7,  18.9,  19.2,
  19.4, 19.6,  19.9,  20.1,  20.4,  20.6,  20.9,  21.1,  21.3,  21.6,
  21.8, 22.1,  22.3,  22.5,  22.8,  23.0,  23.3,  23.5,  23.8,  24.0,
  24.2, 24.5,  24.7,  25.0,  25.2,  25.5,  25.7,  25.9,  26.2,  26.4,
  26.7, 26.9,  27.2,  27.4,  27.6,  27.9,  28.1,  28.4,  28.6,  28.8,
  29.1, 29.3,  29.6,  29.8,  30.1,  30.3,  30.5,  30.8,  31.0,  31.3,
  31.5, 31.8,  32.0,  32.2,  32.5,  32.7,  33.0,  33.2,  33.5,  33.7,
  33.9, 34.2,  34.4,  34.7,  34.9,  35.1,  35.4,  35.6,  35.9,  36.1,
  36.4, 36.6,  36.8,  37.1,  37.3,  37.6,  37.8,  38.1,  38.3,  38.5,
  38.8, 39.0,  39.3,  39.5,  39.7,  40.0,  40.2,  40.5,  40.7,  41.0,
  41.2, 41.5,  41.7,  41.9,  42.2,  42.4,  42.7,  42.9,  43.1,  43.4,
  43.6, 43.9,  44.1,  44.4,  44.6,  44.8,  45.1,  45.3,  45.6,  45.8,
  46.1, 46.3,  46.5,  46.8,  47.0,  47.3,  47.5,  47.8,  48.0,  48.2,
  48.7, 49.0,  49.2,  49.4,  49.7,  49.9
};


// Forward-declare our output routines.
void ack(String text);
void event(String text);
void error(String text);
void info(String text);
void mr_info(String field, String value);
void reply(String text);
void notbusy();
void borked();
void banner();


// Declare a datatype to hold the commands accepted by this controller.
typedef struct {
  char *cmdName;
  char *shortDescription;
  void (*handler)(char *in);
} Command;

// Declare all the callback functions
void help(char* );
void panic(char* );
void setBankPulseWidth(char* );
void getBankPulseWidth(char* );
void getBankDelay(char* );
void setBankDelay(char* );
void showPinState(char *);
void setChargeEnable(char *);
void setChargePWR(char*);
void charge(char*);
void controllerInitiatedPulse(char*);
void audibleAlert(char *);
void setHVState(char *);
void setHVVoltage(char *);
void getPanelHVMode(char *);
void getHVVoltage(char *);
void showPinStates(char *);
void showStatus(char* );
void reset(char* );
void hvCalibration(char *);
void showBankVoltages(char * );
void setPolling(char *);
void chargeToVoltage(char *);
void pulse_single(char *);

Command supportedCommands[] = {
  { "help",          "Show a helpful message giving all the commands",  help },
  { "panic",         "enter safe (panic) state",                          panic },
  { "!bpw",          "<N> <us> sets the pulse width for bank N in us",    setBankPulseWidth},
  { "?bpw",          "<N> get the pulse width for bank N (us)",           getBankPulseWidth},
  { "!bd",           "<N> <us> set the prepulse delay for bank N in us",  setBankDelay},
  { "?bd",           "<N> get the the prepulse delay for bank N (us)",    getBankDelay},
  { "debug",         "show the state of the front panel switches",        showPinStates},
  { "!chgEnbl",      "<0|1> set charge enable state for capacitor bank",  setChargeEnable},
  { "!chgPWR",       "<0|1> set charging state for capacitor bank",       setChargePWR},
  { "charge_ms",     "<ms> charge for given time in ms",                  charge},
  { "charge_V",      "<V> charge to a given voltage",                     chargeToVoltage},
  { "pulse",         "discharge the capacitor bank",                      controllerInitiatedPulse},
  { "pulse_single",  "<N> pulse bank N",                                  pulse_single},
  { "beep",          "make an annoying noise",                            audibleAlert},
  { "!hvState",      "<0|1> turn Spellman HV off or on",                  setHVState},
  { "!hvVoltage",    "<V> set the Spellman output voltage",              setHVVoltage},
  { "?panelHVMode",  "Show what state the HV mode select is in",          getPanelHVMode},
  { "?hvVoltage",    "Return a (crude) measurement of the HV voltage",    getHVVoltage},
  { "?status",       "Show full controller status",                       showStatus},
  { "?bankVoltages", "Show the voltages measured on each capacitor bank", showBankVoltages},
  { "hvCalibration", "Step through HV PWM and ADC range",                 hvCalibration},
  { "!poll",         "<0|1> turn status polling off or on",               setPolling},
  { "reset",         "Reset the controller to defaults",                  reset},
  { "---", "This is a sentinel - do not remove", help }
};

int analogWriteHV(long val) {
  if ( (val < 0) || ( val > 829 ) ) {
    error("Refusing to set HV pwm to overscale value ");
    return -1;
  }
  Timer1.pwm(REMOTE_VREF_0_10V, val); // maps to REMOTE_VREF_0_10V
  return 1;
}

void audibleAlert(char* in) {
  int i, j;
  int width = 400;

  for (i = 0; i < 2; i++) {
    digitalWrite(ANNOYING_BEEPER, HIGH);
    delay(width);
    digitalWrite(ANNOYING_BEEPER, LOW);
    delay(width);
  }

  width = 80;
  for (i = 1; i < 9; i++) {
    digitalWrite(ANNOYING_BEEPER, HIGH);
    delay(width);
    digitalWrite(ANNOYING_BEEPER, LOW);
    delay(width);
  }
}

void audibleAlertShort() {
  int i, j;
  int width = 80;

  digitalWrite(ANNOYING_BEEPER, HIGH);
  delay(width);
  digitalWrite(ANNOYING_BEEPER, LOW);
}


void reset(char *in) {

  PANEL_HV_MANUAL_LAST = 2; // Set to 2 to force state change on first loop.
  PANEL_HV_AUTO_LAST = 2;   // Set to 2 to force state change on first loop.

  for (int i = 0; i < NBANKS + 1; i++) {
    trig_starts[i] = trig_starts_default[i];
    trig_stops[i] = trig_stops_default[i];
  }

  dead_time = 1000;
  requested_hv_voltage = 0;


  digitalWrite(CHG, LOW);
  digitalWrite(CHG_ENBL, LOW);
  digitalWrite(CHG_POWER, LOW);

  digitalWrite(HV_ENABLE, LOW);
  delay(20);
  digitalWrite(HV_ENABLE, HIGH);
  analogWriteHV(REMOTE_VREF_0_10V);

  for (int i = 0; i < NBANKS + 1; i++) {
    pinMode(TRIG_PROBES[i], OUTPUT);
    digitalWrite(TRIG_PROBES[i], LOW);
    pinMode(TRIG_OUTPUT_PINS[i], OUTPUT);
    digitalWrite(TRIG_OUTPUT_PINS[i], LOW);
  }

  // Switch-matrix probe inputs
  pinMode(PROBE_AUTO, INPUT);
  pinMode(PROBE_MANUAL, INPUT);
  pinMode(PROBE_TRIGGER, INPUT);

  // Spellman feedback
  pinMode(HV_VOLTAGE_DETECT, INPUT);
  pinMode(HV_CURRENT_DETECT, INPUT);

  pinMode(REMOTE_HV_ON, OUTPUT);
  pinMode(ACTIVE_LED, OUTPUT);
  digitalWrite(ACTIVE_LED, HIGH);
  digitalWrite(HV_ENABLE, HIGH);
  banner();
  mr_info("controller_state", "started");
  last_pulse = millis();

  polling = 0;
  notbusy();

}

void banner() {
  info(F("----------- POWER SUPPLY CONTROLLER ----------"));
  info("Software Version : " + String(SOFTWARE_ID) + " " + String(SOFTWARE_VERSION));
  info("Number of Capacitor banks supported: " + String(NBANKS));
  info(("HV Supply is bank ") + String(NBANKS + 1));
  info(F("-----------------------------------------------------------------"));

}

void help(char *in) {
  banner();
  int i = 0;
  int l = 0;
  while ( 0 != strcmp(supportedCommands[i].cmdName, "---") ) {
    l = String(supportedCommands[i].cmdName).length();
    String space = "";
    for ( int j = 0; j < 20 - l; j++) {
      space = String(space + " ");
    }
    info( String(supportedCommands[i].cmdName) +
          space + String(":\t") +
          String(supportedCommands[i].shortDescription) );
    i++;
  }
  info(F("-----------------------------------------------------------------"));
}

void error(String text) {
  Serial.println("E " + text); resetBuffer();
}

void info(String text) {
  Serial.println("I " + text);
  Serial.flush();
}

// A more machine-parseable output of information
void mr_info(String field, String value) {
  Serial.println("M { \"" + field + "\" : \"" + value + "\" }");
  Serial.flush();
}

void ack(String text) {
  Serial.println("C " + text);
  Serial.flush();
}

void event(String text) {
  Serial.println("X " + text);
  Serial.flush();
}

void reply(String text) {
  Serial.println("R " + text);
  Serial.flush();
}

void notbusy() {
  Serial.println("> ");
  Serial.flush();
}

void borked() {
  Serial.println("! ");
  Serial.flush();
}


void setup() {
  Serial.begin(BAUD_RATE);
  Timer1.initialize(1000);
  reset(NULL);
  last_poll = millis();
}

void loop() {
  readBuffer();
  processCmd();

  if (polling && (abs(millis() - last_poll) > poll_interval)) {
    showStatus(NULL);
    last_poll = millis();
  }

  // If HV switch settings have changed then
  // Set up the appropriate HV State
  if (  (digitalRead(PANEL_HV_MANUAL) != PANEL_HV_MANUAL_LAST) ||
        (digitalRead(PANEL_HV_AUTO) != PANEL_HV_AUTO_LAST) ) {

    delay(30);

    analogWriteHV(0);
    requested_hv_voltage = 0;

    if ( (digitalRead(PANEL_HV_MANUAL) == LOW) &&
         (digitalRead(PANEL_HV_AUTO) == LOW) ) {
      event("Changed HV State to OFF");
      digitalWrite(REMOTE_HV_ON, LOW);
      digitalWrite(REMOTE_VOLTAGE_CONTROL, LOW);
      digitalWrite(LOCAL_VOLTAGE_CONTROL, LOW);

    }

    if (digitalRead(PANEL_HV_MANUAL) == HIGH)  {
      event("Changed HV State to MANUAL");
      digitalWrite(REMOTE_HV_ON, LOW);
      digitalWrite(REMOTE_VOLTAGE_CONTROL, LOW);
      digitalWrite(LOCAL_VOLTAGE_CONTROL, HIGH);
    }

    if (digitalRead(PANEL_HV_AUTO) == HIGH)  {
      event("Changed HV State to AUTO");
      digitalWrite(REMOTE_HV_ON, LOW);
      digitalWrite(LOCAL_VOLTAGE_CONTROL, LOW);
      digitalWrite(REMOTE_VOLTAGE_CONTROL, HIGH);
    }

    PANEL_HV_MANUAL_LAST = digitalRead(PANEL_HV_MANUAL);
    PANEL_HV_AUTO_LAST = digitalRead(PANEL_HV_AUTO);

  }

  // Handle manually-initiated trigger. Debounce to 500ms.
  bool triggered = false;
  if ((millis() - last_pulse) > dead_time) {

    for (int i = 0; i < NBANKS + 1; i++) {
      if (isTrigger(i + 1)) {
        last_pulse = millis();
        event("Trigger detected for bank: " + String(i + 1));
        triggered = true;
      }
    }

    if (triggered) {
      if (!stateIsSane()) {
        error("State is not sane. Ignoring Trigger");
        borked();
        return;
      }
      for (int i = 0; i < NBANKS + 1; i++) {
        if (isTrigger(i + 1)) {
          event("Triggered bank: " + String(i + 1));
          trigger(i + 1);
          return;
        }
      }
      notbusy();
    }
  }

}

// Pulse a single bank in response to serial command.
void pulse_single(char *in) {

  if (arg1 < 1 || arg1 > NBANKS + 1) {
    error("No such bank!");
    return;
  }

  if ((millis() - last_pulse) < dead_time) {
    error("Too soon after last pulse");
    return;
  }

  if (!isAuto(arg1)) {
    error("Selected bank is not set to AUTO");
    return;
  }
  bool done[NBANKS + 1];
  for (int i = 0; i < NBANKS + 1; i++) {
    done[i] = true;
  }
  done[arg1 - 1] = false;
  audibleAlert("");
  doPulse(done, trig_starts, trig_stops);
}

// Pulse banks in response to serial command.
void controllerInitiatedPulse(char* in) {
  if ((millis() - last_pulse) < dead_time) {
    error("Too soon after last pulse");
    return;
  }

  for (int i = 0; i < NBANKS + 1; i++) {
    if (isManual(i + 1)) {
      error("At least one bank is manual.");
      return;
    }
  }

  for (int i = 0; i < NBANKS + 1; i++) {
    if (isAuto(i + 1)) {
      break;
    }
    if (i == NBANKS) {
      error("No auto bank detected.");
      return;
    }
  }


  bool done[NBANKS + 1];
  for (int i = 0; i < NBANKS + 1; i++) {
    done[i] = !isAuto(i + 1);
  }
  audibleAlert("");
  doPulse(done, trig_starts, trig_stops);
}

// Handle the pressing of the trigger button on bank N
void trigger(int N) {
  int ix = N - 1;
  long my_trig_starts[NBANKS + 1];
  long my_trig_stops[NBANKS + 1];
  bool done[NBANKS + 1];

  for (int i = 0; i < NBANKS + 1; i++) {
    done[i] = !isAuto(i + 1);
    if (N == (NBANKS + 1)) {
      done[i] = true;
    }
    my_trig_starts[i] = trig_starts[i];
    my_trig_stops[i] = trig_stops[i];
  }

  my_trig_stops[ix] = my_trig_stops[ix] - my_trig_starts[ix];
  my_trig_starts[ix] = 0;

  last_pulse = millis();

  if (!isManual(N)) {
    error("Attempt to initiate manual trigger of non-manual bank");
    return;
  } else {
    done[ix] = false;
  }

  audibleAlertShort();
  delay(500);
  audibleAlertShort();
  audibleAlertShort();
  delay(500);
  doPulse(done, my_trig_starts, my_trig_stops);
}

void doPulse(bool* done, long* starts, long* stops) {


  unsigned long pulse_start = micros();
  unsigned long elapsed;
  bool pin_set[NBANKS + 1];
  bool all_done = true;

  last_pulse = millis();

  for (int i = 0; i < NBANKS + 1; i++) {
    pin_set[i] = false;
    all_done = all_done && done[i];
  }

  digitalWrite(STROBE_OUTPUT, HIGH);
  delay(5);
  while (!all_done) {
    for (int i = 0; i < NBANKS + 1; i++) {
      if (!done[i]) {
        elapsed = micros() - pulse_start;
        if ( elapsed > stops[i] ) {
          done[i] = true;
          digitalWrite(TRIG_OUTPUT_PINS[i], LOW);
          break;
        } else if (elapsed > starts[i] && !pin_set[i]) {
          digitalWrite(TRIG_OUTPUT_PINS[i], HIGH);
          //pin_set[i] = true;
          digitalWrite(TRIG_OUTPUT_PINS[i], LOW);
        }
      }
    }
    all_done = true;
    for (int i = 0; i < NBANKS + 1; i++) {
      all_done = all_done && done[i];
    }
  }
  delay(20);
  digitalWrite(STROBE_OUTPUT, LOW);

}

// return 1 if the "MANUAL" switch is closed for a given group
// (group is 1-4 for banks 1-4, 5 for HV)
bool isManual(int group) {
  return isSet(group, PROBE_MANUAL);
}

// return 1 if the "AUTO" switch is closed for a given group
// (group is 1-4 for banks 1-4, 5 for HV)
bool isAuto(int group) {
  return isSet(group, PROBE_AUTO);
}

// return 1 if the "TRIGGER" switch is closed for a given group
// (group is 1-4 for banks 1-4, 5 for HV)
bool isTrigger(int group) {
  return isSet(group, PROBE_TRIGGER);
}

// (group is 1-4 for banks 1-4, 5 for HV)
bool isSet(int group, int input) {
  bool result = false;
  digitalWrite(TRIG_PROBES[group - 1], HIGH);
  delay(0);
  result = (digitalRead(input) == HIGH);
  digitalWrite(TRIG_PROBES[group - 1], LOW);
  return result;
}


// Command Processing.
void readBuffer() {
  while (Serial.available()) {
    if (strPtr == BUFFER_LENGTH) {
      error("Buffer Overflow");
    } else {
      char inChar = (char)Serial.read();
      if (inChar == EOS_TERMINATOR_CHAR) {
        stringComplete = true;
        break;
      }
      inputString[strPtr++] = inChar;
      inputString[strPtr] = 0;
    }
  }
}

void processCmd() {
  if (stringComplete) {
    executeCommand();    // process the command
    notbusy();
    resetBuffer();    // clear for the next command
  }
}

void resetBuffer() {
  inputString[0] = 0;    // discard the buffer contents
  strPtr = 0;
  stringComplete = false;
  baseCmd[0] = 0;
  arg1 = UNDEFINED;
  arg2 = UNDEFINED;
}

/** dissectCommand

   parse the input "baseCmd arg1 [arg2]"
*/
void dissectCommand(char *source_string) {
  char *cmd;
  char buf[BUFFER_LENGTH + 1];

  strcpy(buf, source_string);  // copy locally so we don't modify source

  cmd = strtok(buf, " ");
  strcpy(baseCmd, cmd);

  cmd = strtok(NULL, " ");
  if (cmd) {
    arg1 = atol(cmd);

    cmd = strtok(NULL, " ");
    if (cmd) {
      arg2 = atol(cmd);

      cmd = strtok(NULL, " ");
      if (cmd) {
        error("More than two arguments supplied");
      }
    }
  }
}

bool is_safe_to_execute(char *c) {
  if ( 0 == strncmp(c, "?", 1) ) {
    return true;
  }
  if ( 0 == strcmp(c, "!poll") ) {
    return true;
  }
  if ( 0 == strcmp(c, "reset") ) {
    return true;
  }
  if ( 0 == strcmp(c, "help") ) {
    return true;
  }

  if (!stateIsSane()) {
    return false;
  }

  return true;
}

void executeCommand() {
  ack(inputString);
  dissectCommand(inputString);





  if ( strlen(baseCmd) ) {
    if (!is_safe_to_execute(baseCmd)) {
      error( "State is not sane, and command is not intrinsically safe. Refusing to proceed");
      digitalWrite(ACTIVE_LED, LOW);
      audibleAlertShort();
      delay(50);
      digitalWrite(ACTIVE_LED, HIGH);
      return;
    }

    int i = 0;
    while ( 0 != strcmp(supportedCommands[i].cmdName, "---") ) {
      if ( 0 == strcmp(baseCmd, supportedCommands[i].cmdName) ) {
        supportedCommands[i].handler(inputString);
        return;
      }
      i++;
    }

    error("Unknown command (help gives available cmds)");
  }
}


// Do not return.
void panic(char *in) {
  noInterrupts();
  while (true) {
    delay(1);
  }
}

void setBankPulseWidth(char* in) {
  // arg1 = bank number
  // arg2 = width in microseconds

  if (arg1 < 1 || arg1 > NBANKS + 1) {
    error("No such bank");
    return;
  }

  if ( (arg2 < 0) || (arg2 > 100000) ) {
    error("Illegal value for pulse width");
    return;
  }

  info("Setting Bank" + String(arg1) + " pulse width to " + String(arg2) + " us");
  trig_stops[arg1 - 1] = trig_starts[arg1 - 1] + arg2;

}

void getBankPulseWidth(char* in) {
  if (arg1 < 1 || arg1 > NBANKS + 1) {
    error("There is no such bank");
  } else {
    int pulseWidth = trig_stops[arg1 - 1] - trig_starts[arg1 - 1];
    reply(String(pulseWidth));
  }
}

void setBankDelay(char* in) {
  // arg1 = bank number
  // arg2 = delay in microseconds

  if (arg1 < 1 || arg1 > NBANKS + 1) {
    error("There is no such bank");
    return;
  }

  if (arg2 < 0 || arg2 > 500000 ) {
    error("Delay out of range");
    return;
  }

  info("Setting Bank " + String(arg1) + " delay to " + String(arg2) + " us");
  int delta = arg2 - trig_starts[arg1 - 1];
  trig_starts[arg1 - 1] = trig_starts[arg1 - 1] + delta;
  trig_stops[arg1 - 1] = trig_stops[arg1 - 1] + delta;
}

void getBankDelay(char* in) {
  // arg1 = bank number
  if (arg1 < 1 || arg1 > NBANKS + 1) {
    error("There is no such bank");
    return;
  }
  reply(String(trig_starts[arg1 - 1]));
}

void showPinStates(char* in) {
  for (int i = 0; i < NBANKS + 1; i++) {
    String bankname = "bank_" + String(i + 1);
    if (i == NBANKS) {
      bankname = "hv";
    }
    String descriptor = bankname + "_control_state";
    if (isManual(i + 1)) {
      mr_info(descriptor, "MANUAL");
    } else if (isAuto(i + 1)) {
      mr_info(descriptor, "AUTO");
    } else {
      mr_info(descriptor, "OFF");
    }
    if (isTrigger(i + 1)) {
      mr_info(bankname + "_trigger_depressed", "True");
    } else {
      mr_info(bankname + "_trigger_depressed", "False");
    }
  }
}

// Summarise the state of the system
void showStatus(char* in) {
  mr_info("requested_charge_power", String(requested_charge_power));
  mr_info("requested_charge_enable", String(requested_charge_enable));

  showPinStates(in);

  getPanelHVMode(in);
  mr_info("hv_voltage_requested", String(requested_hv_voltage));
  mr_info("hv_voltage_measured", String(HVVoltage()));
  showBankVoltages(in);

  for (int i = 0; i < NBANKS; i++) {
    mr_info("bank_" + String(i + 1) + "_start", String(trig_starts[i]));
    mr_info("bank_" + String(i + 1) + "_stop", String(trig_stops[i]));
  }

  for (int i = NBANKS; i < NBANKS + 1; i++) {
    mr_info("hv_start", String(trig_starts[i]));
    mr_info("hv_stop", String(trig_stops[i]));
  }

  int s;
  s = stateIsSane();
  if (s > 0) {
    mr_info("state_is_sane", "True");
  } else {
    mr_info("state_is_sane", "False");
  }
}

void setChargeEnable(char* in) {
  if (arg1 > 1 || arg1 < 0 ) {
    error("Illegal argument; should be 1 (ON) or 0 (OFF)");
    return;
  }
  requested_charge_enable = arg1;
  if (arg1 == 1) {
    reply(F("Charging enabled"));
    digitalWrite(CHG_ENBL, HIGH);
  }
  if (arg1 == 0) {
    reply(F("Charging disabled"));
    digitalWrite(CHG_ENBL, LOW);
  }
}

void setHVState(char* in) {
  if (digitalRead(PANEL_HV_AUTO) == HIGH) {

    if (arg1 == 1) {
      reply(F("User changed HV State to ON"));
      digitalWrite(REMOTE_HV_ON, HIGH);
      delay(20);
      digitalWrite(REMOTE_HV_ON, LOW);
    }

    if (arg1 == 0) {
      reply(F("User changed HV State to OFF"));
      requested_hv_voltage = 0;
      digitalWrite(HV_ENABLE, LOW);
      delay(20);
      digitalWrite(HV_ENABLE, HIGH);
      analogWriteHV(0);
    }

  } else {
    error("HV switch must be set to AUTO for programmed control of HV state");
    return;
  }

  if (arg1 < 0 || arg1 > 1) {
    error("Illegal HV State: please use either 0 or 1");
  }
}



void hvCalibration(char * in) {

  if (digitalRead(PANEL_HV_AUTO) == HIGH)  {
    int i = arg1;
    analogWriteHV(i);
    delay(2000);
    ADC = analogRead(HV_VOLTAGE_DETECT);
    requested_hv_voltage = HVVoltage();
    reply("OUT " + String(i) + " IN " + String(ADC));
  } else {
    error("ATTEMPTING HV CALIBRATION WHISLT !AUTO");
  }
}

void setHVVoltage(char* in) {

  if ( (arg1 < HV_MIN_VOLTAGE ) || arg1 > HV_MAX_VOLTAGE ) {
    error("Illegal value for HV voltage");
    return;
  }

  if (digitalRead(PANEL_HV_AUTO) == HIGH)  {

    long pwm_val =  abs(int( double(arg1 * 829.0) / double(50000) ));
    if ( analogWriteHV(abs(pwm_val)) > 0 ) {
      reply(String("Set HV voltage to ") + String(arg1));
      requested_hv_voltage = arg1;
    }
  } else {
    error("HV_ILLEGAL_OPERATION: SET VOLTAGE WHILST !AUTO");
  }

}

double HVVoltage() {
  // Piecewise linear interpolation from analog read.
  long ADC;
  ADC = analogRead(HV_VOLTAGE_DETECT);
  int i = 0;
  while (hv_in_table[i] < ADC) {
    i++;
    if (i == N_CAL_ENTRIES - 1) {
      error("Fell off end of table in HVVoltage()");
      return -1e27; // Guarantee that result is detected as problematic.
    }
  }
  double alpha = double(ADC - hv_in_table[i - 1]) / double(hv_in_table[i] - hv_in_table[i - 1]);
  double result = (1.0 - alpha) * hv_actual_table[i - 1] + alpha * hv_actual_table[i];
  return result * 1000;
}

void getHVVoltage(char* in) {
  double V = HVVoltage();
  reply(String(V));
}

// Check if the state of the system is sane.
// Complain loudly about things that are not sane.
int stateIsSane() {

  int is_sane = 1;

  // Are BANK switches in sane state
  if ( (digitalRead(PANEL_HV_MANUAL) == HIGH) && (digitalRead(PANEL_HV_AUTO) == HIGH) ) {
    error(F("HV BIAS CONTROL READS MANUAL *AND* AUTO"));
    is_sane = 0;
  }

  double SF = 500.0 / 335.0;
  int lower[] = {BANK1_L, BANK2_L, BANK3_L, BANK4_L};
  int upper[] = {BANK1_U, BANK2_U, BANK3_U, BANK4_U};
  long VL, VU;

  for (int i = 0; i < 4; i++) {
    VL = int( SF * analogRead(lower[i]) );
    VU = int( 2 * SF * analogRead(upper[i]) - VL);
    if (VL < 0 || VL > 450 ) {
      error("Bank " + String(i + 1) + " Lower Voltage abnormal: " + String(VL) + " V");
      is_sane = 0;
    }
    if (VU < 0 || VU > 450 ) {
      error("Bank " + String(i + 1) + " Upper Voltage abnormal: " + VU + " V");
      is_sane = 0;
    }
  }

  // Are Bank switches in sane state
  for (int i = 0; i < NBANKS + 1; i++) {
    if ( isManual(i + 1) && isAuto(i + 1) ) {
      error("SWITCH ERROR: BANK " + String(i + 1) + " reads MANUAL *AND* AUTO");
      is_sane = 0;
    }
  }

  if ((digitalRead(PANEL_HV_AUTO) == HIGH) ) {
    // Is HV Power supply voltage approximately what was requested?
    double V;
    V = HVVoltage();

    if ( abs(V - requested_hv_voltage) > voltage_margin ) {
      info("Waiting for HV to equilibrate...");
      delay(HV_TIMEOUT); // Give it some time
      if ( abs(V - requested_hv_voltage) > voltage_margin ) {
        error("HV Error: requested " + String(abs(requested_hv_voltage)) + " but reading " + V);
        is_sane = 0;
      }
    }
  }

  return is_sane;
}

void getPanelHVMode(char* in) {
  if (digitalRead(PANEL_HV_MANUAL) == HIGH)  {
    mr_info("panel_hv_mode", "MANUAL");
    return;
  }

  if (digitalRead(PANEL_HV_AUTO) == HIGH)  {
    mr_info("panel_hv_mode", "AUTO");
    return;
  }

  mr_info("panel_hv_mode", "OFF");
}

void showBankVoltages(char* in) {

  double SF = 500.0 / 335.0;
  int lower[] = {BANK1_L, BANK2_L, BANK3_L, BANK4_L};
  int upper[] = {BANK1_U, BANK2_U, BANK3_U, BANK4_U};
  long VL, VU;

  for (int i = 0; i < 4; i++) {
    VL = int( SF * analogRead(lower[i]) );
    VU = int( 2 * SF * analogRead(upper[i]) - VL);
    mr_info("bank_" + String(i + 1) + "_lower_voltage", String(VL));
    mr_info("bank_" + String(i + 1) + "_upper_voltage", String(VU));
  }

}

void chargeToVoltage(char* in) {
  double SF = 500.0 / 335.0;
  int lower[] = {BANK1_L, BANK2_L, BANK3_L, BANK4_L};
  int upper[] = {BANK1_U, BANK2_U, BANK3_U, BANK4_U};
  long VL = 0;
  long VU = 0;

  if (arg1 < 0 || arg1 > 800) {
    error("Cap bank voltage must be in the range 0-800V");
    return;
  }

  for (int i = 0; i < 4; i++) {
    VU = max(VU, int( 2 * SF * analogRead(upper[i])));
  }
  if (VU > arg1) {
    error("Cap bank is already above requested voltage");
    return;
  }

  long start_time = millis();

  mr_info("charging", "True");
  digitalWrite(CHG, HIGH);
  while (VU < arg1) {
    showBankVoltages("");
    for (int i = 0; i < 4; i++) {
      VU = max(VU, int( 2 * SF * analogRead(upper[i])));
    }
    if (abs(millis() - start_time) > ceil(1000 * (1.0 + float(arg1) / 12.5))) {
      digitalWrite(CHG, LOW);
      error("Timed out trying to charge - voltage still too low");
      mr_info("charging", "False");
      return;
    }
  }
  digitalWrite(CHG, LOW);
  mr_info("charging", "False");
}

void setChargePWR(char* in) {
  if (arg1 > 1 || arg1 < 0 ) {
    error("CHG_PWR_ERROR_INVALID_ARGUMENT");
    return;
  }
  requested_charge_power = arg1;
  if (arg1 == 1) {
    reply("Capacitor bank charge power ON");
    digitalWrite(CHG_POWER, HIGH);
  }
  if (arg1 == 0) {
    reply("Capacitor bank charge power OFF");
    digitalWrite(CHG_POWER, LOW);
  }
}

void charge(char* in) {
  if (arg1 < 0 || arg1 > 60000) {
    error("CHG_INVALID_DURATION_MS");
    return;
  }
  info("Charging for " + String(arg1) + " milliseconds");
  mr_info("charging", "True");
  digitalWrite(CHG, HIGH);
  delay(arg1);
  digitalWrite(CHG, LOW);
  mr_info("charging", "False");
  info("Charging complete");
}

void setPolling(char* in) {
  if (arg1 < 0 || arg1 > 1) {
    error(F("Invalid argument to !poll: should be 0 or 1"));
    return;
  }
  polling = int(arg1);
}




