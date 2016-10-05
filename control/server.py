import time
import cherrypy
import os
import total_control
import json

page_skeleton = """
<!doctype html>

<html lang="en">
<head>
  <meta charset="utf-8">

  <title>Shielded-Grid Control</title>
  <meta name="description" content="Control System for Fusion device">
  <meta name="author" content="Shielded-Grid Fusion Team">

  <link rel="stylesheet" href="/static/css/bootstrap.min.css">
</head>

<body>
   <div class="container">
     <h1> Shielded-Grid System Control </h1>
     <button onclick="startup()">Startup</button>
     <button onclick="shutdown()">Shutdown</button>

     <div class="container">
     <label for="charge">Cap Bank Target Voltage</label>
     <input type="range" id="charge" min="0" value="0" max="800" step="10" oninput="setChargeVoltage(value)">
     <output for="charge" id="cap">0</output>
     <button onclick="charge()">Charge</button>
     </div>

     <div class="container">
       <button onclick="pulse()">Pulse</button>
     </div>


     <div class="container" id="status">
     </div>
   </div>
    
       <!-- Bootstrap core JavaScript
    ================================================== -->
    <!-- Placed at the end of the document so the pages load faster -->
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.0.0/jquery.min.js" integrity="sha384-THPy051/pYDQGanwU6poAc/hOdQxjnOEXzbT+OuUAFqNqFjL+4IGLBgCJC3ZOShY" crossorigin="anonymous"></script>
    <script>window.jQuery || document.write('<script src="../../assets/js/vendor/jquery.min.js"><\/script>')</script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tether/1.2.0/js/tether.min.js" integrity="sha384-Plbmg8JY28KFelvJVai01l8WyZzrYWG825m+cZ0eDDS1f7d/js6ikvy1+X+guPIB" crossorigin="anonymous"></script>
    <script src="../../dist/js/bootstrap.min.js"></script>
    <!-- IE10 viewport hack for Surface/desktop Windows 8 bug -->
    <script>
      function setChargeVoltage(v) {
        document.querySelector('#cap').value = v;
      }
      function charge() {
        $.post('/api', {cmd: "charge", voltage: document.querySelector('#cap').value })
      }
      function updateStatus() {
        
      }
      function startup() {
         $.post('/api',{cmd: "startup"})
      }
      function shutdown() {
         $.post('/api',{cmd: "shutdown"})
      }
      function pulse() {
         $.post('/api',{cmd: "pulse"})
      }
    </script>
    <script src="../../assets/js/ie10-viewport-bug-workaround.js"></script>
</body>
</html>

"""

class ControlAPI:
  exposed = True
  def __init__(self):
    self.c = total_control.TotalControl()

  @cherrypy.tools.accept(media='text/plain')

  def GET(self,*args,**kwargs):
    return self.c.bank.invoke("?status")

  def POST(self,*args,**kwargs):
    try:
      cmd = kwargs['cmd']
    except:
      return "Missing cmd argument"
    if cmd=='shutdown':
      return self.c.shutdown()
    elif cmd=='startup':
      return self.c.startup()
    elif cmd=='pulse':
      return self.c.pulse_all()
    elif cmd=='forward':
      try:
        mm = int(kwargs['mm'])
        return self.c.forward(mm)
      except:
        return "Missing or invalid argument (mm)"
    elif cmd=='backwards':
      try:
        mm = int(kwargs['mm'])
        return self.c.backwards(mm)
      except:
        return "Missing or invalid argument (mm)"
    elif cmd=='charge':
      try:
        V = int(kwargs['voltage'])
        return self.c.charge(V)
      except:
        return "Missing or invalid argument (voltage)"
    else:
      return "Ignoring unhandled command %s"%cmd
    

 

class Server:
  @cherrypy.expose
  def index(self):
    return page_skeleton


def main():
  conf = {
    '/': {
      'tools.sessions.on' : True,
      'tools.staticdir.root' : os.path.abspath(os.getcwd())
    },
    '/api': {
      'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
      'tools.response_headers.on': True,
      'tools.response_headers.headers': [('Content-Type', 'text/plain')],
    },
    '/static': {
      'tools.staticdir.on' : True,
      'tools.staticdir.dir' : './static'
    }

  }
  webapp = Server()
  webapp.api = ControlAPI()
  cherrypy.quickstart(webapp,'/',conf)

if __name__ == '__main__':
  main()
