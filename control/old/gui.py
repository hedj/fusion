#!/usr/bin/python3
from tkinter import *
from tkinter import filedialog
from tkinter import ttk
from tkinter import font
from PIL import Image, ImageTk
import win32com
import win32com.client
import time
import os
import io
import csv
import picoscope
from picoscope import ps3000a


import Pmw
import system_control

bank = system_control.BankControl()
stepper = system_control.StepperControl()
sequencer = system_control.SequenceControl()


speaker = win32com.client.Dispatch('SAPI.SpVoice')


root = Pmw.initialise()
root.title("Shielded-Grid System Control")
bolder = font.Font(family='Helvetica', size=11, weight='bold')


messageBar = Pmw.MessageBar(root,
        entry_width = 40,
        entry_relief='groove',
        labelpos = 'w',
        label_text = 'Status:')

balloon = Pmw.Balloon()
menuBar = Pmw.MenuBar(root,
                hull_relief = 'raised',
                hull_borderwidth = 1,
                balloon = balloon)
menuBar.pack(fill = 'x')




# Create and pack the main part of the window.
nb = ttk.Notebook(root)
nb.pack(fill = 'both', expand = 1,side=TOP)

tabs = dict()
for name in [ 'Manual Control', 'Sequencing', 'Data Acquisition' ]:
  tabs[name] = Frame(root)
  nb.add(tabs[name], text=name)


rigols = system_control.RigolControl()

def drawRigolTab(parent, ip):
  device = rigols.get(ip)
  Label(parent, font=bolder, text=device.idn).grid(padx=5, pady=10, row=0,column=0,sticky=(W,E))
  #stream = io.BytesIO(rigols.image(ip))
  #image = Image.open(stream)
  #bitmap = ImageTk.PhotoImage(image)
  #label = Label(parent)
  #label.grid(row=1,column=0)
  #label.configure(image = bitmap)
  #label.image = bitmap

  #def refresh():
  #  stream = io.BytesIO(device.display_data)
  #  image = Image.open(stream)
  #  bitmap = ImageTk.PhotoImage(image)
  #  label.configure(image=bitmap)
  #  label.image = bitmap

  #Button(parent, text='update (Warning - takes ~ 5s!)',command=refresh).grid(row=2,column=0)


def addNewRigolTab(ip):
  name = 'Rigol at %s'%str(ip)
  tabs[name] = Frame(root)
  nb.add(tabs[name],text=name)
  drawRigolTab(tabs[name], ip)

def removeRigolTab(ip):
  name = 'Rigol at %s'%str(ip)
  nb.forget(tabs[name])
  tabs[name].destroy()
  tabs.pop(name)

rigols.onConnect(addNewRigolTab)
rigols.onDisconnect(removeRigolTab)


VCAP = IntVar()

VB1L = IntVar()
VB1U = IntVar()
VB2L = IntVar()
VB2U = IntVar()
VB3L = IntVar()
VB3U = IntVar()
VB4L = IntVar()
VB4U = IntVar()

VHV = IntVar()

bank_1_mode = StringVar()
bank_2_mode = StringVar()
bank_3_mode = StringVar()
bank_4_mode = StringVar()

charge_status = StringVar()

stepper_dist = IntVar()

class GUI:
  pass

class ResizingCanvas(Canvas):
  def __init__(self,parent,**kwargs):
    Canvas.__init__(self,parent,**kwargs)
    self.bind("<Configure>", self.on_resize)
    self.height = self.winfo_reqheight()
    self.width = self.winfo_reqwidth()

  def on_resize(self,event):
    # determine the ratio of old width/height to new width/height
    wscale = float(event.width)/self.width
    hscale = float(event.height)/self.height
    self.width = event.width
    self.height = event.height
    # rescale all the objects tagged with the "all" tag
    self.scale("all",0,0,wscale,hscale)




def stepper_fwd(*args):
  stepper.forward(stepper_dist.get())
def stepper_back(*args):
  stepper.backwards(stepper_dist.get())

def update(variable, key):
  state = bank.log.get_current_state()
  if key in state:
    variable.set( state[key])

def update_if_positive(variable, key):
  state = bank.log.get_current_state()
  if key in state:
    if state[key] >= 0:
      variable.set( state[key])

def setHV(*args):
  bank.invoke("!hvVoltage %d"%VHV.get())

def setPulseButtonState(val):
  GUI.pulseButton.configure(state=val)
  GUI.pulse1_Button.configure(state=val)
  GUI.pulse2_Button.configure(state=val)
  GUI.pulse3_Button.configure(state=val)
  GUI.pulse4_Button.configure(state=val)

has_connected = False

def status_handler(s):
  update_if_positive(VB1L, "bank_1_lower_voltage")
  update_if_positive(VB2L, "bank_2_lower_voltage")
  update_if_positive(VB3L, "bank_3_lower_voltage")
  update_if_positive(VB4L, "bank_4_lower_voltage")
  update_if_positive(VB1U, "bank_1_upper_voltage")
  update_if_positive(VB2U, "bank_2_upper_voltage")
  update_if_positive(VB3U, "bank_3_upper_voltage")
  update_if_positive(VB4U, "bank_4_upper_voltage")

  state = bank.log.get_current_state()
  charge_status.set('')
  if ('controller_state' in state.keys()):
    messageBar.message('state', 'Connected')
    GUI.mainpart.lift()
    setPulseButtonState(NORMAL)
    if 'charging' in state.keys():
      if state['charging']:
        charge_status.set('CHARGING')
        setPulseButtonState(DISABLED)
      else:
        charge_status.set('')
        setPulseButtonState(NORMAL)
    if 'requested_charge_power' in state.keys():
     if state['requested_charge_power'] == 1:
       chargepwr.setvalue('ON')
     else:
       chargepwr.setvalue('OFF')
    if 'requested_charge_enable' in state.keys():
     if state['requested_charge_enable'] == 1:
       chargeenable.setvalue('ON')
     else:
       chargeenable.setvalue('OFF')
  else:
    setPulseButtonState(DISABLED)







bank.add_status_callback( status_handler )

sequence_defaults = [ 50, 5000, 0, 100000, 0, 0, 0, 0, 5 ]
sequence = []
entryFields = []
field_headings = [
 'Cap_Voltage', 'HV_Voltage', 'HV_Pulse_Start', 'HV_Pulse_Stop', 'Bank1_Start', 'Bank2_Start', 'Bank3_Start', 'Bank4_Start', 'Stepper Position']

lower_bounds = [0,   0,     -1,     -1,    -1,     -1,     -1,     -1,     -150 ]
upper_bounds = [900, 25000, 10000, 200000, 100000, 100000, 100000, 100000, 150]





def pulse_all():
  bank.invoke('pulse')

def pulse_1():
  bank.invoke('pulse_single 1')

def pulse_2():
  bank.invoke('pulse_single 2')

def pulse_3():
  bank.invoke('pulse_single 3')

def pulse_4():
  bank.invoke('pulse_single 4')

def pulse_hv():
  bank.invoke('pulse_single 5')

def setHVEnable(s):
  if s=='ON':
    bank.invoke('!hvState 1')
  else:
    bank.invoke('!hvState 0')


def setChargePower(s):
  if s=='ON':
    bank.invoke('!chgPWR 1')
  else:
    bank.invoke('!chgPWR 0')

def setChargeEnable(s):
  if s=='ON':
    bank.invoke('!chgEnbl 1')
  else:
    bank.invoke('!chgEnbl 0')

output_dir = StringVar()
def set_output_dir(*args):
  d = filedialog.askdirectory()  
  if d:
    output_dir.set(d)

def readfile(*args):
  f = filedialog.askopenfile(mode='r', filetypes=(( "CSV Files", "*csv"),))
  if f:
    lines = f.readlines()
    count = 0
    for line in lines:
      count = count + 1
      if line.rstrip() != '' and line[0] != '#':
        try:
          elems = line.split(',')
          if len(elems) != len(field_headings):
            Pmw.displayerror("Not enough fields on line %d - should be %d"%(count, len(field_headings)))
            return
          for i in range(len(elems)):
            try:
              val = int(elems[i].rstrip())
              if val > upper_bounds[i] or val < lower_bounds[i]:
                raise Exception("Out of bounds")
            except:
              Pmw.displayerror('Illegal value %s for field %s on line %d : should be between %d and %d'%(elems[i],field_headings[i],count, lower_bounds[i], upper_bounds[i]))
              return
            
        except:
          Pmw.displayerror("Could not parse that file")
          return
    for line in lines:
      if line.rstrip() != '' and line[0] != '#':
        sequence.append([ int(i.rstrip()) for i in line.split(',')])
        create_row()

def savefile(*args):
  name = filedialog.asksaveasfilename(filetypes=(("CSV Files", "*.csv"),))
  if name != '':
    if name[-2:] == '.py':
      Pmw.displayerror("Refusing to overwrite code with csv")
      return
    f = open(name, 'w+')
    f.write('# %s'%( ', '.join(field_headings) ))
    for line in sequence:
      f.write( ', '.join([str(i) for i in line]) )
      f.write('\r\n')
    f.close()

def about(*args):
  pass


menuBar.addmenu('File', 'Read Command files, Exit')
menuBar.addmenuitem('File', 'command', 'read sequence from CSV', command = readfile, label='Open')
menuBar.addmenuitem('File', 'command', 'export sequence to CSV', command = savefile, label='Save')
menuBar.addmenuitem('File', 'separator')
menuBar.addmenuitem('File', 'command', 'Exit the application',
                command = root.destroy,
                label = 'Exit')
menuBar.addmenu('Help', 'Get more information', side='right')
menuBar.addmenuitem('Help', 'command', 'About This Program', command=about, label='About')


def charge(*args):
  print("Charging bank to %d V"%(int(VCAP.get())))
  bank.invoke('charge_V %d'%int(VCAP.get()))


step_delay = IntVar()
step_delay.set(10)



output_dir.set("c:\data")

bank_1_mode.set('OFF')
bank_2_mode.set('OFF')
bank_3_mode.set('OFF')
bank_4_mode.set('OFF')

VB1L.set(0)
VB1U.set(0)
VB2L.set(0)
VB2U.set(0)
VB3L.set(0)
VB3U.set(0)
VB4L.set(0)
VB4U.set(0)




mainpart = tabs['Manual Control']
GUI.mainpart = mainpart
GUI.mainpart.lower()
seqframe = tabs['Sequencing']
#mainpart.pack(fill = 'both', expand = 1,side=TOP)

nb.select(0)

# Add Cap Bank Controls
capbankframe = LabelFrame(mainpart,text="Cap Bank")
capbankframe.pack(fill='x',expand=1,side=TOP)
capbankframe.columnconfigure(1,weight=1)
capbankframe.rowconfigure(1,weight=1)

capbankcanvas = ResizingCanvas(capbankframe,bg='black')
capbankcanvas.grid(row=0,column=0,columnspan=3,padx=10,sticky=(W,E))
def redrawCapBank():
  c = capbankcanvas
  c.delete("all")
  w  = c.width
  h = c.height
  
  h1 = h - 20

  sf = h1 / 1000.0

  w1 = (w - 20) / 4

  pad = 2

  if (charge_status.get() != ''):
    c.create_text(w/2, 10, text="BANK VOLTAGES (CHARGING)", fill='red')
  else:
    c.create_text(w/2, 10, text="BANK VOLTAGES", fill='lightgrey')
  
  def draw_bank(N, v_upper, v_lower):
    vt = v_upper + v_lower
    L = 10 + (N-1)*w1
    R = 10 + N*w1
    c.create_rectangle(L + pad, h1 - int(vt*sf), R - pad,h1 , fill='orange')
    c.create_rectangle(L + pad, h1 - int(v_lower*sf), R - pad,h1 , fill='orange')
    c.create_text(L + w1/2, h1 - int( sf*(vt + v_lower)/2.0),  text = str(v_upper))
    c.create_text(L + w1/2, h1 - int( sf*(v_lower)/2.0),  text = str(v_lower))
    c.create_text(L + w1/2, h1 - int( sf*(vt) ) - 10,  text = str(vt), fill='orange')
    c.create_text(L + w1/2, h-10,  text = str(N), fill='white')

  draw_bank(1, VB1U.get(), VB1L.get())
  draw_bank(2, VB2U.get(), VB2L.get())
  draw_bank(3, VB3U.get(), VB3L.get())
  draw_bank(4, VB4U.get(), VB4L.get())
  c.after(50, redrawCapBank)
  
redrawCapBank()

f = Frame(capbankframe)
f.grid(row=1,column=0,columnspan=3,sticky=(W,E),padx=20)
f.columnconfigure(0,weight=1)
Label(f, textvariable=bank_1_mode).pack(side='left',expand=1)
Label(f, textvariable=bank_2_mode).pack(side='left',expand=1)
Label(f, textvariable=bank_3_mode).pack(side='left',expand=1)
Label(f, textvariable=bank_4_mode).pack(side='left',expand=1)

Label(capbankframe, text='Charge Power').grid(row=2,column=0)
chargepwr = Pmw.RadioSelect(capbankframe, command=setChargePower, 
                            orient='horizontal',hull_borderwidth=2,hull_relief='ridge')
chargepwr.add('OFF',bg='green',font=bolder )
chargepwr.add('ON',bg='red',font=bolder)
chargepwr.grid(row=2,column=1,sticky=(W,E),padx=10)

Label(capbankframe, text='Charge Enable').grid(row=3,column=0)
chargeenable = Pmw.RadioSelect(capbankframe, command=setChargeEnable,
                               orient='horizontal',hull_borderwidth=2,hull_relief='ridge')
chargeenable.add('OFF',bg='green',font=bolder)
chargeenable.add('ON',bg='red',font=bolder)
chargeenable.grid(row=3,column=1,sticky=(W,E),padx=10)

caplabel = Label(capbankframe,text='Target Voltage').grid(column=0,row=4)
capctrl = Scale(capbankframe,variable=VCAP,from_=0,to=800,tickinterval=200,orient='horizontal')
capctrl.grid(row=4,column=1,sticky=(W,E),padx=10)
chargeButton = Button(capbankframe, text="Charge",command=charge)
chargeButton.grid(row=4,column=2,sticky=(W,E))

f = LabelFrame(capbankframe,text='Manual Pulse Control')
f.grid(row=5,column=0,columnspan=3,sticky=(W,E))
f.columnconfigure(0,weight=1)
f.columnconfigure(1,weight=1)
f.columnconfigure(2,weight=1)
f.columnconfigure(3,weight=1)
GUI.pulse1_Button = Button(f, text='Pulse 1',command=pulse_1,state=DISABLED)
GUI.pulse1_Button.grid(row=0,column=0,sticky=(W,E))
GUI.pulse2_Button = Button(f, text='Pulse 2',command=pulse_2,state=DISABLED)
GUI.pulse2_Button.grid(row=0,column=1,sticky=(W,E))
GUI.pulse3_Button = Button(f, text='Pulse 3',command=pulse_3,state=DISABLED)
GUI.pulse3_Button.grid(row=0,column=2,sticky=(W,E))
GUI.pulse4_Button = Button(f, text='Pulse 4',command=pulse_4,state=DISABLED)
GUI.pulse4_Button.grid(row=0,column=3,sticky=(W,E))
GUI.pulseButton = Button(f, text="Pulse All", command=pulse_all,state=DISABLED)
GUI.pulseButton.grid(row=1,column=0,columnspan=4,sticky=(W,E))

# Add HV Controls
hvframe = LabelFrame(mainpart,text="HV Controls")
hvframe.pack(fill='x',expand=1,side=TOP)
hvframe.columnconfigure(1,weight=1)

hvenable = Pmw.RadioSelect(hvframe, command=setHVEnable,
                               orient='horizontal',hull_borderwidth=2,hull_relief='ridge')
hvenable.add('OFF',bg='green',font=bolder)
hvenable.add('ON',bg='red',font=bolder)
hvenable.grid(row=0,column=0,columnspan=3,sticky=(W,E))

hvlabel = Label(hvframe,text='Target Voltage').grid(column=0,row=2)
hvctrl = Scale(hvframe,variable=VHV, from_=0,to=25000,tickinterval=10000,orient='horizontal')
hvctrl.grid(row=2,column=1,sticky=(W,E),padx=10)
hvSetButton = Button(hvframe, text="Set", command=setHV)
hvSetButton.grid(row=2,column=2,sticky=(W,E))
hvPulseButton = Button(hvframe, text="Pulse HV", command=pulse_hv)
hvPulseButton.grid(row=3,column=1,sticky=(W,E))

stepper_frame = LabelFrame(mainpart, text="Stepper Controls")
stepper_frame.pack(fill='x',expand=1)
stepper_frame.columnconfigure(0,weight=1)
stepper_frame.columnconfigure(1,weight=1)
stepper_frame.rowconfigure(1,weight=1)
Scale(stepper_frame, variable=stepper_dist, label="STEP SIZE (mm)", from_=0, to=150, tickinterval=10, orient='horizontal').grid(column=0,row=0,columnspan=2,sticky=(W,E),pady=5,padx=10)
Button(stepper_frame, text="Forward",command=stepper_fwd).grid(row=1,column=0,sticky=(W,E))
Button(stepper_frame, text="Back",command=stepper_back).grid(row=1,column=1,sticky=(W,E))

# Create and pack the MessageBar.

messageBar.pack(fill = 'x', padx = 10, pady = 10)
messageBar.message('state', 'Connecting to bank')

balloon.configure(statuscommand = messageBar.helpmessage)

seq_ctrl_frame = LabelFrame(seqframe, text='Sequence Control')
seq_ctrl_frame.pack(side='top',fill='x',expand=1)
seq_ctrl_frame.columnconfigure(0,weight=1)
seq_ctrl_frame.columnconfigure(1,weight=1)
seq_ctrl_frame.columnconfigure(2,weight=1)
seq_ctrl_frame.columnconfigure(3,weight=1)


def start_sequence(*args):
  sequence = updateSequence()
  if (not sequence == []):
    speaker.Speak("Starting sequence in: ")
    for count in range(5,0,-1):
      speaker.Speak('%d'%(count))
  else:
    print("Empty sequence - refusing to proceed")
    return
  sequencer.set_delay(step_delay.get())
  sequencer.stop()
  sequencer.set(sequence)
  sequencer.start()

def stop_sequence(*args):
  reset_step_indicators()
  sequencer.stop()
  sequencer.set_step(0)
  indicate_current_step(-1)

def pause_sequence(*args):
  sequencer.stop()

def set_step_delay(*args):
  sequencer.set_delay(step_delay.get())

def reset_step_indicators():
  for l in line_labels:
    l.configure(font=NORMAL, fg='black')

def indicate_current_step(n):
  print("Showing active step %d"%(n))
  reset_step_indicators()
  if (n > 0):
    line_labels[n-1].configure(font=bolder, fg='red')

def wait_for_bank():
  while( not bank.ready() ):
    time.sleep(0.1)

def shouldAbort():
  return not sequencer.running()

def run_step(step, n):
  reset_step_indicators()
  if shouldAbort():
    return
  indicate_current_step(n)
  
  print("Running step %s"%str(step))
  while( not stepper.ready() ):
    print("Waiting for stepper control")
    if shouldAbort():
      return
    time.sleep(3)

  if shouldAbort():
    return
  stepper.go(step[8])

  if shouldAbort():
    return
  wait_for_bank()
  if shouldAbort():
    return
  # Charge Capacitor Bank
  VCAP.set(step[0])

  if shouldAbort():
    return
  charge()
  wait_for_bank()

  # Set HV
  VHV.set(step[1])
  setHV()
  wait_for_bank()

  if shouldAbort():
    return

  # Set HV pulse start
  bank.invoke('!bd 5 %d'%step[2])
  wait_for_bank()

  # Set HV pulse width
  bank.invoke('!bpw 5 %d'%(step[3] - step[2]))
  wait_for_bank()

  bank.invoke('!bd 1 %d'%step[4]);
  bank.invoke('!bd 2 %d'%step[5]);
  bank.invoke('!bd 3 %d'%step[6]); 
  bank.invoke('!bd 4 %d'%step[7]); 
  wait_for_bank()

  if shouldAbort():
    return

  pulse_all()

  wait_for_bank()

  # write data
  data = rigols.scope_screen_contents()
  print(data.keys())
  seq = '{0:03d}'.format(n)
  outdir = os.path.join(output_dir.get(), seq)
  if not os.path.exists(outdir):
    os.makedirs(outdir)
  for scope in data.keys():
    print("Writing data for scope %s"%scope)
    this_scope_data = data[scope]
    outfile = os.path.join(outdir, "%s.csv"%scope)
    with open(outfile,"w") as csvfile:
      writer =  csv.writer(csvfile)
      # get length of time series
      length = len(data[scope]['Channel_1'][0])
      for i in range(length):
        line = []
        line.append(data[scope]['Channel_1'][1][i])
        for channel in sorted(this_scope_data.keys()):
          line.append(data[scope][channel][0][i])
        writer.writerow(line)

  if n==len(sequence):
    reset_step_indicators()
  

sequencer.register_execution_callback(run_step)

Button(seq_ctrl_frame, text='Start', command = start_sequence).grid(row=0,column=0,sticky=(W,E))
Button(seq_ctrl_frame, text='Pause', command = pause_sequence).grid(row=0,column=1,sticky=(W,E))
Button(seq_ctrl_frame, text='Stop', command = stop_sequence).grid(row=0,column=2,sticky=(W,E))

Label(seq_ctrl_frame, text='Output Directory:').grid(row=1,column=0)
Entry(seq_ctrl_frame, textvariable=output_dir).grid(row=1,column=1,columnspan=2,sticky=(W,E))
Button(seq_ctrl_frame, text='Select', command=set_output_dir).grid(row=1,column=3)
step_delay_slider = Scale(seq_ctrl_frame, command=set_step_delay, label="Delay between steps (s)", from_=0, to=300, tickinterval=60, orient='horizontal', variable=step_delay)
step_delay_slider.grid(column=0,row=2,columnspan=5,sticky=(W,E),pady=5,padx=10)


seq_edit_frame = LabelFrame(seqframe, text='Sequence Editor')
seq_edit_frame.pack(side='top', fill='x', expand=1)
sf = Pmw.ScrolledFrame(seq_edit_frame,
                       hull_height = 220)
sf.pack(fill='both', expand=1)

frm = sf.interior()
Label(frm, text='Seq#').grid(row=0,column=0,sticky=(W,E), padx=5)
Label(frm, text='Cap_Voltage').grid(row=0,column=1,sticky=(W,E), padx=5)
Label(frm, text='HV_Voltage').grid(row=0,column=2,sticky=(W,E), padx=5)
Label(frm, text='HV_Pulse_Start').grid(row=0,column=3,sticky=(W,E), padx=5)
Label(frm, text='HV_Pulse_Stop').grid(row=0,column=4,sticky=(W,E), padx=5)
Label(frm, text='Bank1_Start').grid(row=0,column=5,sticky=(W,E), padx=5)
Label(frm, text='Bank2_Start').grid(row=0,column=6,sticky=(W,E), padx=5)
Label(frm, text='Bank3_Start').grid(row=0,column=7,sticky=(W,E), padx=5)
Label(frm, text='Bank4_Start').grid(row=0,column=8,sticky=(W,E), padx=5)
Label(frm, text='Stepper Position').grid(row=0,column=9,sticky=(W,E), padx=5)

line_labels = []

def create_row():
  entryFields.append([])
  row = len(sequence) -1
  line_labels.append(Label(frm, text=int(row+1)))
  line_labels[-1].grid(row=row+1, column=0, sticky=(W,E), padx=5)
  line = sequence[-1]
  for ix in range(len(line)):
    entryFields[row].append( Pmw.EntryField(frm,value=int(line[ix]),command=updateSequence, validate={'validator' : 'integer', 'min' : lower_bounds[ix], 'max' : upper_bounds[ix]} ))
    entryFields[row][ix].grid(row=row+1, column=ix+1,sticky=(W,E), padx=5)


def add_step():
  if len(sequence) > 0:
    sequence.append(sequence[-1])
  else:
    sequence.append(sequence_defaults)
  create_row()

def remove_step():
  for t in entryFields[-1]:
    t.destroy()
  line_labels[-1].destroy()
  line_labels.pop()
  entryFields.pop()
  sequence.pop()

def updateSequence():
  new_sequence = []
  for row in range(len(entryFields)):
    new_sequence.append([])
    line = entryFields[row]
    for ix in range(len(line)):
      new_sequence[row].append(int(entryFields[row][ix].getvalue()))
  sequence = new_sequence
  return new_sequence

Button(seq_edit_frame, text='Add Step', command=add_step).pack(side='left', expand=1, fill='x')
Button(seq_edit_frame, text='Remove Step', command=remove_step).pack(side='left', expand=1, fill='x')

root.mainloop()
