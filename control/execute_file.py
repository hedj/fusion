import os
import serial
import ds1054z
import picoscope

def syntax_is_good(string):
  return True

def execute(RUNFILE):
  # Open Rigol Scopes
  # Check for control system

  # do startup
    # power up chargers
    # power up HV
    # turn on CHG_ENBL

  # check for existence and correct formatting of RUNFILE
  if not(os.path.isfile(RUNFILE)):
    print(RUNFILE + " was not found")
    sys.exit(-1)
  rf = open(RUNFILE,"r")
  contents = rf.readlines()

  line_count = 0;
  for line in contents:
  	line_count += 1
  	if not(syntax_is_good(line)):
      print("Error on line " + line_count)
  	  print(line)
      sys.exit(-1)




  # summarise run
  # prompt user for confirmation

  # until interrupted or out of iterations, do:
    # read parameters for this step from RUNFILE
    # charge the power supply
    # check the voltage is sane
    # set triggering for oscilloscopes
    # pulse coil
    # read data out of oscilloscopes
    # write data to CSV files
    # check the voltage is sane


  # do shutdown
     # turn off CHG_ENBL
     # power off HV
     # power off chargers