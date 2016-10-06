
// Power supply control software for Controllino Mega.
// Accepts input from custom switch board
// Also speaks NSLC over serial; serial settings are 250000 Baud, 8N1
// see https://github.com/hedj/nslc for a deeper description of the protocol.

// (C) 2016 John Hedditch

#include <Controllino.h>
#include <TimerOne.h>

#include "pinouts.h"
#include "constants.h"
#include "spellman.h"

#include "nslc.h"
#define MAX_FRAME_LENGTH 128

// defines for setting and clearing register bits
#ifndef cbi
#define cbi(sfr, bit) (_SFR_BYTE(sfr) &= ~_BV(bit))
#endif
#ifndef sbi
#define sbi(sfr, bit) (_SFR_BYTE(sfr) |= _BV(bit))
#endif

void frame_handler(const uint8_t *data, uint16_t len);
void send_character(uint8_t data);
NSLC lc = NSLC(&send_character, &frame_handler, MAX_FRAME_LENGTH);

uint8_t switch_state[NBANKS+2]; // last entry is the HV Power control
uint8_t hv_ctrl_state = 0;
uint8_t present_hv_state;

double spellman_voltage;

bool charging = false;
long charge_start;
long v_charge_start;
long target_voltage;
long last_heartbeat;

bool dry_run = false;

int requested_hv_voltage;

bool pulsing = false;
long pulse_start;

long last_switch_change;


bool should_abort = false;  // Drop whatever we're doing?

double SF = 500.0 / 335.0;
int lower[] = {BANK1_L, BANK2_L, BANK3_L, BANK4_L};
int upper[] = {BANK1_U, BANK2_U, BANK3_U, BANK4_U};
int TRIG_OUTPUT_PINS[] = {CONTROLLINO_D5, CONTROLLINO_D6, CONTROLLINO_D7, CONTROLLINO_D8, CONTROLLINO_D10};
long bank_voltages_lower[NBANKS];
long bank_voltages_upper[NBANKS];

bool manual_override[NBANKS+1]; // did we manually trigger?
uint8_t bpd[NBANKS+1];
uint8_t bpw[NBANKS+1];

uint8_t requested_chg_enbl = 0;
uint8_t requested_chg_pwr = 0;

uint8_t colPins[5] = {
  TRIG1_PROBE, TRIG2_PROBE, TRIG3_PROBE, TRIG4_PROBE, TRIGHV_PROBE
};



void send_response(uint8_t command, uint8_t parameter, uint8_t response_code, uint16_t val) {
  char data[5] = {command, parameter, response_code, val / 256, val % 256};
  lc.frameDecode(data, 5);
}

/* Function to send out one 8bit character */
void send_character(uint8_t data) {
    Serial.write((char)data);
}

bool is_vanilla_bank_state(int state) {
  return ( (state == BANK_AUTO) || (state == BANK_MANUAL) || (state == BANK_OFF) );
}

void setHVVoltage(uint16_t v) {

  long pwm_val =  abs(int( double(v * 829.0) / double(50000) ));

  if ( pwm_val < 0 || pwm_val > 829 ) {
    send_response(COMMAND_SET, HV_VOLTAGE, BANK_VOLTAGE_OUT_OF_RANGE, 0);
    return;
  }

  if (dry_run) {
    send_response(COMMAND_SET, HV_VOLTAGE, OK, 0);
    requested_hv_voltage = v;
    return;
  }

  if ( digitalRead(PANEL_HV_AUTO) != HIGH ) {
    send_response(COMMAND_SET, HV_VOLTAGE, BAD_SWITCH_STATE, 0);
    return;
  }
  
  Timer1.pwm(REMOTE_VREF_0_10V, pwm_val); 
  send_response(COMMAND_SET, HV_VOLTAGE, OK, 0);
  requested_hv_voltage = v;
  
}

bool is_valid_bank(uint8_t N) {
  return (1 <= N) && (N <= NBANKS+1);
}

void getParam(const uint8_t *data, uint16_t len) {

  uint32_t result;
  uint8_t msb;
  uint8_t lsb;
  char reply[32];

  if (len<2) {
   return;
  }

  switch(data[1]) {
    case PULSE_WIDTH:
      if (len != 3) {
        send_response(COMMAND_GET, PULSE_WIDTH, WRONG_NUMBER_OF_ARGUMENTS, len-2);
        return;
      }
      if (is_valid_bank(data[2])) {
        send_response(COMMAND_GET, PULSE_WIDTH, OK, bpw[data[2]-1]);
      } else {
        send_response(COMMAND_GET, PULSE_WIDTH, INVALID_BANK_NUMBER, data[2]);
      }
      break;

    case PULSE_DELAY:
      if (len != 3) {
        send_response(COMMAND_GET, PULSE_DELAY, WRONG_NUMBER_OF_ARGUMENTS, len-2);
      }
      if (is_valid_bank(data[2])) {
        send_response(COMMAND_GET, PULSE_DELAY, OK, bpd[data[2]-1]);
      } else {
        send_response(COMMAND_GET, PULSE_DELAY, INVALID_BANK_NUMBER, data[2]);
      }
      break;

    case CHARGE_ENABLE:
      send_response(COMMAND_GET, CHARGE_ENABLE, OK, requested_chg_enbl);
      break;

    case CHARGE_POWER:
      send_response(COMMAND_GET, CHARGE_ENABLE, OK, requested_chg_pwr);
      break;

    case HV_STATE:
      send_response(COMMAND_GET, HV_STATE, OK, present_hv_state);
      break;

    case HV_VOLTAGE:
      result = (uint32_t)spellman_voltage;
      send_response(COMMAND_GET, HV_VOLTAGE, OK, (uint16_t)result);
      break;

    case BANK_VOLTAGE:
      reply[0] = (uint8_t)COMMAND_GET;
      reply[1] = (uint8_t)BANK_VOLTAGE;
      for(int i=0; i<8; i += 2) {
        int v = bank_voltages_lower[i/2];
        reply[i+2] = (uint8_t)(v/256);
        reply[i+3] = (uint8_t)(v - reply[i+2]);
      }
      for(int i=0; i<8; i += 2) {
        int v = bank_voltages_upper[i/2];
        reply[i+10] = (uint8_t)(v/256);
        reply[i+11] = (uint8_t)(v - reply[i+10]);
      }
      lc.frameDecode(reply, 18);
      break;

    case SWITCH_STATE:
      char data[NBANKS+2];
      data[0] = COMMAND_GET;
      data[1] = SWITCH_STATE;
      for(int i=0; i<NBANKS+1; i++) {
        data[i+2] = switch_state[i];
      }
      lc.frameDecode(data, NBANKS+3);
      break;

    default:
      break;
  }
}

void setParam(const uint8_t *data, uint16_t len) {

  
  int val;

  if (len < 3) {
    return;
  }

  byte which_param = data[1];
  switch(which_param) {
    case PULSE_WIDTH: // arguments are bank number and pulse width in ms
      if (len != 4) {
        send_response(COMMAND_SET, PULSE_WIDTH, WRONG_NUMBER_OF_ARGUMENTS, len-2);
        return;
      }
      if (is_valid_bank(data[2]))  {
        bpw[data[2] - 1] = data[3];
        send_response(COMMAND_SET, PULSE_WIDTH, OK, 0);
      } else {
        send_response(COMMAND_SET, PULSE_WIDTH, INVALID_BANK_NUMBER, data[2]);
      }
      break;

    case PULSE_DELAY: // arguments are bank number and pulse delay in ms
       if (len != 4) {
        send_response(COMMAND_SET, PULSE_DELAY, WRONG_NUMBER_OF_ARGUMENTS, len-2);
        return;
      }
      if (is_valid_bank(data[2]))  {
        bpd[data[2] - 1] = data[3];
        send_response(COMMAND_SET, PULSE_DELAY, OK, data[3]);
      } else {
        send_response(COMMAND_SET, PULSE_DELAY, INVALID_BANK_NUMBER, data[2]);
      }
      break;

    case CHARGE_POWER: 
      val = data[2] > 0;
      requested_chg_pwr = val;
      if (!dry_run) {
        digitalWrite(CHG_POWER, val);
      }
      send_response(COMMAND_SET, CHARGE_POWER, OK, val);
      break;
 
    case CHARGE_ENABLE:
      val = data[2] > 0;
      requested_chg_enbl = val;
      if (!dry_run) {
        digitalWrite(CHG_ENBL, val);
      }
      send_response(COMMAND_SET, CHARGE_ENABLE, OK, val);
      break;

    case HV_STATE:
      setHVState(data[2]);
      break;

    case HV_VOLTAGE: 
      if (len != 4 ) {
        send_response(COMMAND_SET, HV_VOLTAGE, WRONG_NUMBER_OF_ARGUMENTS, len-2);
      } else {
        setHVVoltage(256*data[2] + data[3]); 
      }
      break;

    default: // Ignore anything else
      break;
  }

}

void setHVState(uint8_t v) {

  if (!dry_run) {
  if ( digitalRead(PANEL_HV_AUTO) != HIGH ) {
    send_response(COMMAND_SET, HV_STATE, BAD_SWITCH_STATE, 0);
    return;
  }
  }

  if (v > 0) {
    present_hv_state = 1;
    if (!dry_run) {
      digitalWrite(REMOTE_HV_ON, HIGH); 
      delay(20);
      digitalWrite(REMOTE_HV_ON, LOW);
    }
  } else {
    requested_hv_voltage = 0;
    present_hv_state = 0;
    if (!dry_run) {
      digitalWrite(HV_ENABLE, LOW); 
      delay(20);
      digitalWrite(HV_ENABLE, HIGH);
      Timer1.pwm(REMOTE_VREF_0_10V, 0);
    }
  }
  send_response(COMMAND_SET, HV_STATE, OK, v);
}

bool safe_to_pulse() {
  // Check that voltages are OK
  for( int i=0; i<NBANKS; i++ ) {
   if ( bank_voltages_lower[i] < 0 || bank_voltages_lower[i] > 450 ) {
     send_response(COMMAND_PULSE, GENERAL, BANK_VOLTAGE_OUT_OF_RANGE, i+1);
     return false;
   }
   if ( bank_voltages_upper[i] < 0 ||  bank_voltages_upper[i] > 450) {
     send_response(COMMAND_PULSE, GENERAL, BANK_VOLTAGE_OUT_OF_RANGE, i+1);
     return false;
   }
  }

  // Check that we are not already pulsing
  if ( pulsing ) {
     send_response(COMMAND_PULSE, GENERAL, ALREADY_PULSING, 0);
     return false;
  }

  // Check that we are not still charging!
  if ( charging ) {
     send_response(COMMAND_PULSE, GENERAL, ATTEMPT_TO_PULSE_WHILST_CHARGING, 0);
     return false;
  }
  return true;
}

void manual_pulse() {

  for (int i=0; i<NBANKS+1; i++) {
    manual_override[i] = false;
  }

  if (!safe_to_pulse()) { // safe_to_pulse() will generate errors if they are found
    return;
  }

  // One bank should be set to manual and have the trigger depressed.
  // All other banks should be either MANUAL, AUTO, or OFF
  int ntriggered_banks = 0;
  for ( int i=0; i< NBANKS+1; i++ ) {
    if ( switch_state[i] == BANK_TRIGGER_MANUAL ) {
      ntriggered_banks++;
      manual_override[i] = true;
    } else if ( !is_vanilla_bank_state(switch_state[i]) ) {
      send_response(COMMAND_PULSE, GENERAL, BAD_SWITCH_STATE, i+1);
      return;
    }
  }
  if ( ntriggered_banks != 1 ) {
    send_response(COMMAND_PULSE, GENERAL, BAD_SWITCH_STATE, 6);
    return;
  }

   // Start pulsing 
  pulsing = true;
  send_response(COMMAND_PULSE, GENERAL, OK, 1);
  pulse_start = millis();


}

void auto_pulse(const uint8_t *data, uint16_t len) {

  if (!safe_to_pulse()) { // safe_to_pulse() will generate errors if they are found
    return;
  }

  if (!dry_run) {
  // Check switch config is OK for automatic pulse
  for(int i=0; i<NBANKS+1;i++) {
    if (switch_state[i] == BANK_MANUAL) {
      send_response(COMMAND_PULSE, GENERAL, AT_LEAST_ONE_BANK_MANUAL, i+1); 
      return;
    }
    if (switch_state[i] != BANK_AUTO && switch_state[i] != BANK_OFF) {
      send_response(COMMAND_PULSE, GENERAL, BAD_SWITCH_STATE, i+1); 
      return;
    }
  }
  }

  // Start pulsing 
  pulsing = true;
  send_response(COMMAND_PULSE, GENERAL, OK, 1);
  if (!dry_run) {
    digitalWrite(STROBE_OUTPUT, HIGH);
  }
  pulse_start = millis();
  
}

void setDryRun(const uint8_t *data, uint16_t len) {
  if (len != 2) {
    send_response(COMMAND_DRY_RUN, GENERAL, WRONG_NUMBER_OF_ARGUMENTS, len-1);
    return; 
  }
  if (data[1] > 0) {
    dry_run = true;
  } else {
    dry_run = false;
  }
  send_response(COMMAND_DRY_RUN, GENERAL, OK, (char)dry_run);
}

void charge(const uint8_t *data, uint16_t len) {
  // Check that we have enough arguments
  if (len != 3) {
    send_response(COMMAND_CHARGE, GENERAL, WRONG_NUMBER_OF_ARGUMENTS, len-2);
    return;
  }

  // Check that target voltage is sane
  target_voltage = 256 * data[1] + data[2];
  if (target_voltage > 800 || target_voltage == 0) {
    send_response(COMMAND_CHARGE, GENERAL, ILLEGAL_VALUE_FOR_ARGUMENT, 0); 
    return;
  }

  if (dry_run) {
     send_response(COMMAND_CHARGE, GENERAL, OK, 1);
    // Start charging (pretending)
    v_charge_start = 0; 
    for (int i=0; i<NBANKS; i++) {
      v_charge_start = max(v_charge_start, bank_voltages_lower[i] + bank_voltages_upper[i]);
    }
    charging = true;
    charge_start = millis();
    return;
  }

  if ( charging ) {
    send_response(COMMAND_CHARGE, GENERAL, ALREADY_CHARGING, 0 );
    return;
  }

  if (pulsing) {
    send_response(COMMAND_CHARGE, GENERAL, ATTEMPT_TO_CHARGE_WHILST_PULSING, 0 );
    return;
  }

  // Check that the switches are in a sane state
  for (int i=0; i<NBANKS+1; i++) {
    if ( switch_state[i] != BANK_AUTO
      && switch_state[i] != BANK_OFF
      && switch_state[i] != BANK_MANUAL) {
      send_response(COMMAND_CHARGE, GENERAL, BAD_SWITCH_STATE, i+1); 
      return;
    }
  }

  // Check that we're not already sufficiently charged
  for(int i=0; i<NBANKS; i++) {
    if ( bank_voltages_lower[i] + bank_voltages_upper[i] >= target_voltage ) {
      send_response(COMMAND_CHARGE, GENERAL, ALREADY_AT_TARGET_VOLTAGE, 0 );
      return;
    }
  }

  // Inform the host we have started charging
  send_response(COMMAND_CHARGE, GENERAL, OK, 1);

  // Start charging
  v_charge_start = 0; 
  for (int i=0; i<NBANKS; i++) {
    v_charge_start = max(v_charge_start, bank_voltages_lower[i] + bank_voltages_upper[i]);
  }
  charging = true;
  charge_start = millis();
  if (!dry_run) {
    digitalWrite(CHG, HIGH);
  }

}

void reset() {
  dry_run = false;
  digitalWrite(CHG, LOW);
  digitalWrite(CHG_ENBL, LOW);
  digitalWrite(CHG_POWER, LOW);

  digitalWrite(HV_ENABLE, LOW);
  delay(20);
  digitalWrite(HV_ENABLE, HIGH);
  Timer1.pwm(REMOTE_VREF_0_10V, 0);

  digitalWrite(ANNOYING_BEEPER, LOW);

  for (int i = 0; i < NBANKS + 1; i++) {
    pinMode(colPins[i], OUTPUT);
    digitalWrite(colPins[i], LOW);
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
 
  pulsing = false;
  charging = false;
  should_abort = false; // Clear should_abort flag.
  for(int i=0; i<NBANKS; i++) {
    bpd[i] = 10;
    bpw[i] = 200;
  }
  bpd[NBANKS] = 0;
  bpw[NBANKS] = 50;

  last_switch_change = millis();
  last_heartbeat = millis() - 2000;
  send_response(COMMAND_RESET, GENERAL, OK, 0);
}

void showHelp() {
  char data[] = "See https://github.com/hedj/nslc for protocol details";
  lc.frameDecode(data, strlen(data));
}

/* Frame handler function. What to do with received data? */
void frame_handler(const uint8_t *data, uint16_t len) {

  // Do something with data that is in framebuffer
  if (len >0) {

    if (len ==3) {
      if (data[0] == 'h' && data[1] == 'e' && data[2] == 'l') {
        showHelp();
      }
    } else if (len ==4) {
      if (data[0] == 'h' && data[1] == 'e' && data[2] == 'l' && data[3] == 'p') {
        showHelp();
      }
    }

    // otherwise, handle as needed    
    switch (data[0])  {
      case COMMAND_GET:                   getParam(data, len); break;
      case COMMAND_SET:                   setParam(data, len); break;
      case COMMAND_CHARGE:                charge(data, len); break;
      case COMMAND_DRY_RUN:               setDryRun(data, len); break;
      case COMMAND_PULSE:                 auto_pulse(data, len); break;
      case COMMAND_ABORT:                 should_abort = true; break;
      case COMMAND_RESET:                 reset(); break;
      default:                       
        break;
    }
  } 
}


void setup() {
  Serial.begin(250000);
  reset();
  // set prescale to 16 for faster but less accurate analog reads.
  //  sbi(ADCSRA,ADPS2) ;
  //  cbi(ADCSRA,ADPS1) ;
  //  cbi(ADCSRA,ADPS0) ;
}

double HVVoltage() {
  // Piecewise linear interpolation from analog read.
  long ADC;
  ADC = analogRead(HV_VOLTAGE_DETECT);
  int i= (ADC/4); // table delta is about 3 per entry, so we guarantee to start low
  while(hv_in_table[i] < ADC) { 
    i++;
    if (i == N_CAL_ENTRIES-1) {
      return -1e27; // Guarantee that result is detected as problematic.
    }  
  }
  double alpha = double(ADC - hv_in_table[i-1]) / double(hv_in_table[i] - hv_in_table[i-1]);
  double result = (1.0 - alpha)*hv_actual_table[i-1] + alpha*hv_actual_table[i];
  return result*1000;
}


bool in_range(long val, long a, long b) {
  return ( val >= a && val <= b );
}

void do_pulse_step() {

  if (dry_run) {
    pulsing = false;
    send_response(COMMAND_PULSE, GENERAL, OK, 0);
    return;
  }

  if ( should_abort ) { // Bail out, and notify host
     pulsing = false;
    for (int i=0; i<NBANKS+1; i++) {
      digitalWrite(TRIG_OUTPUT_PINS[i], LOW);
    }
    digitalWrite(STROBE_OUTPUT, LOW);
    digitalWrite(ANNOYING_BEEPER, LOW);
    send_response(COMMAND_PULSE, GENERAL, ABORTED, 0);
    return;
   
  }

  long now = millis();
  bool all_done = true;

  if ( in_range(now - pulse_start, 0, 2240) ) {
    if ( in_range(now - pulse_start, 0, 400) ) {
       digitalWrite(ANNOYING_BEEPER, HIGH);
    } else if ( in_range(now - pulse_start, 800, 1200) ) {
       digitalWrite(ANNOYING_BEEPER, HIGH);
    } else if ( (now-pulse_start) > 1599 &&  (now - pulse_start)%160 <= 80 ) {
       digitalWrite(ANNOYING_BEEPER, HIGH);
    } else {
       digitalWrite(ANNOYING_BEEPER, LOW);
    }
    return;
  } else {
    digitalWrite(ANNOYING_BEEPER, LOW);
    digitalWrite(STROBE_OUTPUT, HIGH);
    now = millis() - 2240;
  }


  if ( manual_override[NBANKS] ) {
    // only fire HV.
    int d = now - pulse_start;
    if ( d <= (bpw[NBANKS] + bpd[NBANKS]) && d >= bpd[NBANKS]  ) {
      digitalWrite(TRIG_OUTPUT_PINS[NBANKS], HIGH);
      all_done = false;
      return;
    } else {
      digitalWrite(TRIG_OUTPUT_PINS[NBANKS], LOW);
      all_done = true;
    }
  }

  if (all_done) {
    pulsing = false;
    for (int i=0; i<NBANKS+1; i++) {
      digitalWrite(TRIG_OUTPUT_PINS[i], LOW);
    }
    digitalWrite(STROBE_OUTPUT, LOW);
    send_response(COMMAND_PULSE, GENERAL, OK, 0);
    return;
  }


  for(int i=0; i<NBANKS+1; i++) {

    if ( switch_state[i] != BANK_AUTO && !manual_override[i] ) {
      continue;
    }
 
    int this_bpd = bpd[i];

    // Manually initiated bank should fire at t=0
    if (manual_override[i]) {
      this_bpd = 0;
    }

    if ( (now - pulse_start) >= this_bpd ) {
      if ( (now - pulse_start) <= (this_bpd + bpw[i]) )  {
        all_done = false;
        if (i == NBANKS) {
          digitalWrite(TRIG_OUTPUT_PINS[i], HIGH);
        } else {
          digitalWrite(TRIG_OUTPUT_PINS[i], !digitalRead(TRIG_OUTPUT_PINS[i]));
        }
      } else {
        digitalWrite(TRIG_OUTPUT_PINS[i], LOW);
      }
    }
  }

  if (all_done) {
    pulsing = false;
    for (int i=0; i<NBANKS+1; i++) {
      digitalWrite(TRIG_OUTPUT_PINS[i], LOW);
    }
    digitalWrite(STROBE_OUTPUT, LOW);
    send_response(COMMAND_PULSE, GENERAL, OK, 0);
  }
}

void do_charge_step() {
  int dv_dt;

  if (dry_run) {
    charging = false;
    send_response(COMMAND_CHARGE, GENERAL, OK, 0);
    return; 
  }
  
  if ( should_abort ) { // Bail out, and notify host
    charging = false;
    digitalWrite(CHG, LOW);
    send_response(COMMAND_CHARGE, GENERAL, ABORTED, 0);
    return;
  }

  bool timeout = false;
  bool succeeded = false;
  bool brownout = false;
  int vmax = 0;

  int charge_timeout = ceil(1000 * (1.0 + float(target_voltage) / 12.5));

  if ((millis() - charge_start) > charge_timeout) {
    timeout = true;
    charging = false;
  } 
  
  for (int i=0; i<NBANKS; i++) {
    vmax = max(vmax, bank_voltages_lower[i] + bank_voltages_upper[i]);
  }

  // Is charge rate within reasonable limits?
  if ( millis() - charge_start > 100 ) {
    dv_dt = (1000 * (vmax - v_charge_start)) / (1 + millis() - charge_start);
    if ( dv_dt > 15 || dv_dt < 5 ) {
      brownout = true;
      charging = false;
    }
  }

  if (vmax >= target_voltage) {
    succeeded = true;
    charging = false;
  }

  if (!charging) {
    digitalWrite(CHG, LOW);
  }

  if (succeeded) {
    send_response(COMMAND_CHARGE, GENERAL, OK, 0);  
  } else if (timeout) {
    send_response(COMMAND_CHARGE, GENERAL, TIMED_OUT, 0);  
  } else if (brownout) {
    send_response(COMMAND_CHARGE, GENERAL, CHARGE_RATE_ABNORMAL, dv_dt);  
  }

}

int get_state(int i) {
  uint8_t new_state;
  if (i == NBANKS+1) {
    new_state = 2*digitalRead(PANEL_HV_AUTO) + digitalRead(PANEL_HV_MANUAL);
  } else {
    digitalWrite( colPins[i], HIGH );
    new_state = 4*digitalRead(PROBE_TRIGGER) + 2*digitalRead(PROBE_AUTO) + digitalRead(PROBE_MANUAL);
    digitalWrite( colPins[i], LOW );
  }
  return new_state;
}

void handle_hv_state_change(int new_state) {
   Timer1.pwm(REMOTE_VREF_0_10V, 0);  // Set voltage to zero!
   switch (new_state) {
      case BANK_OFF:
        digitalWrite(REMOTE_HV_ON, LOW);
        digitalWrite(REMOTE_VOLTAGE_CONTROL, LOW);
        digitalWrite(LOCAL_VOLTAGE_CONTROL, LOW);
        break;
      case BANK_MANUAL:
        digitalWrite(REMOTE_HV_ON, LOW);
        digitalWrite(REMOTE_VOLTAGE_CONTROL, LOW);
        digitalWrite(LOCAL_VOLTAGE_CONTROL, HIGH);
        break;
      case BANK_AUTO:
        digitalWrite(REMOTE_HV_ON, LOW);
        digitalWrite(LOCAL_VOLTAGE_CONTROL, LOW);
        digitalWrite(REMOTE_VOLTAGE_CONTROL, HIGH);
        break;
      default:
        // Something is wrong with the switch. Turn the power supply off.
        digitalWrite(REMOTE_HV_ON, LOW);
        digitalWrite(REMOTE_VOLTAGE_CONTROL, LOW);
        digitalWrite(LOCAL_VOLTAGE_CONTROL, LOW);           
        break;
    }
}

void loop() {


  // Read PULSE TRIGGER / HV PULSE switches
  int new_state;
  int i;
  for(i=0; i<NBANKS+2;i++) {
    new_state = get_state(i);

    if ( new_state != switch_state[i] ) {
      if (( millis() - last_switch_change ) > 100) {
        send_response(SWITCH_STATE_CHANGE, i+1, switch_state[i], new_state);
        switch_state[i] = new_state;
        last_switch_change = millis();
        
      
        // Handle HV switch change
        if (i == NBANKS + 1) {
          handle_hv_state_change( switch_state[i] );
        }
        else if (  new_state != BANK_AUTO &&
            new_state != BANK_MANUAL &&
            new_state != BANK_OFF ) {
          manual_pulse();
        }
      }
    }
  }

  if (pulsing) { 
    do_pulse_step(); 
  }

  if (!pulsing && !charging) {
    // heartbeat
    char hb_data[] = {(char)HEARTBEAT};
    if (millis() - last_heartbeat >= 2000) {
      // lc.frameDecode(hb_data, 1);
      last_heartbeat = millis();
    }
  }

  // Sample bank and Spellman voltages
  spellman_voltage = HVVoltage();
  for (int i=0; i<NBANKS; i++) {
    bank_voltages_lower[i] = analogRead(lower[i]);
    bank_voltages_upper[i] = 2*analogRead(upper[i]) - bank_voltages_lower[i];
    bank_voltages_lower[i] *= SF;
    bank_voltages_upper[i] *= SF;
  }

  if ( charging ) {
    do_charge_step();
  }

  // Get serial input
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    lc.charReceiver(inChar);
  }

  
}
