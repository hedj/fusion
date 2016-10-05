import time
import total_control

def pulse(N,V):
  c = total_control.TotalControl()
  for pulse in range(N):
    c.bank.charge(V)
    time.sleep(1)
    c.bank.pulse()
    c.writeCSVFiles("c:/data/field_measurement/160802",pulse+1)
    c.stepper.backwards(5)
    time.sleep(60)

