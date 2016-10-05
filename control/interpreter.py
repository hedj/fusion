#!/usr/bin/python3
import dummy_control
#import total_control
import re
import sys

# Accepts a file with the following structure
#   comments lines prefixed (first char) with #   (ignored)
#   first non-comment line is whitespace-separated list of commands 
#   subsequent lines are values for the commands

# remove non-True elements from a list
def strip(l):
  return [i for i in filter(None,l)]

class CmdFileInterpreter:
  def __init__(self,input_file):
    print( "Connecting to devices")
    self.c = dummy_control.DummyControl()
    print( "Reading input file" )
    f = open(input_file,"r")
    self.contents = f.readlines()
    if self.validate(self.contents):
      pass
    else:
      print("ERROR: Invalid file contents. Refusing to load")
      sys.exit(-1)

  def run(self, dry_run=False):
    # run the currently-loaded script
    non_comment_lines = []
    for line in self.contents:
      if line[0] != '#':
        non_comment_lines.append(line)
    for line in non_comment_lines[1:]:
      columns = strip(re.split('\s+', line))
      for i in range(len(columns)):
        self.column_functions[i](columns[i], dryrun=dry_run)

  def validate(self, lines):
    # Lines beginning with a hash are comments; strip them out
    non_comment_lines = []
    for line in self.contents:
      if line[0] != '#':
        non_comment_lines.append(line)
    # First non-comment line should be composed only of space-separated names of commands we understand
    # (we allow any choice of case)
    first_line_commands = strip([s.lower() for s in re.split('\s+',non_comment_lines[0])])
    supported_commands = dir(self.c)
    for cmd in supported_commands:
      if cmd.lower()[0:4] == "cmd_":
        print("Found supported command : %s"%cmd[4:])
    self.column_functions = []
    self.commands = first_line_commands
    for cmd in first_line_commands:
      if not ('cmd_' + cmd in [ i.lower() for i in supported_commands]):
        print("Command %s not found in command class"%cmd)
        print("Offending line is: ")
        print(non_comment_lines[0])
        return False
      else:
        x = [i.lower() for i in supported_commands].index('cmd_'+cmd)
        cmd_with_case = supported_commands[x] 
        self.column_functions.append( getattr(self.c,cmd_with_case)) 
    # OK, so we have valid column headings. Now make sure each following line has the same number of
    # columns as the header and the inputs are acceptable
    N = len(first_line_commands)
    for line in non_comment_lines[1:]:
      count = len(strip(re.split('\s+', line) ))
      if count != N:
        print("Column number mismatch! Expected %d entries, but got %d"%(N,count))
        print("Offending line is: ")
        print(line)
        return False
    # So far, so good. Now check that all the values are acceptable to the appropriate functions
    for line in non_comment_lines[1:]:
      columns = strip(re.split('\s+', line))
      for i in range(len(columns)): 
        if not self.column_functions[i](columns[i], dryrun=True):
          print("Invalid value for function %s : %s"%(self.commands[i], columns[i]))
          return False
    return True
    # All done ! 
