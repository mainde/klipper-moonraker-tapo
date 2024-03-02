# klipper-moonraker-tapo
How to control a Tapo Smart Plug via Moonraker

![image](https://github.com/mainde/klipper-moonraker-tapo/assets/14027750/0227d972-d46c-45f4-98c7-80764b22b9da)

👎 There's no proper support for Tapo smart plugs in Moonraker, the only solution I've seen wanted me to install Home Assistant which feels a bit much. 

👎 There is a Python library for controlling Tapo smart plugs which is extremely easy to use and works well, however somehow Moonraker does not allow running arbitrary script on its host, or I couldn't find a way to do it, which is quite bizarre. 

👎 Klipper can run macros, but these only run if the MCU is connected, which requires the power to be on in the first place. 

🍀 Luckily the `power` section of Moonraker's config allows arbitrary http requests (even if `type: http` is, confusingly, not explicitly called out as supported in the documentation), a Python script with a tiny HTTP server attached can be used to control the smart plug, creating the following abomination:

![image](https://github.com/mainde/klipper-moonraker-tapo/assets/14027750/53c66c34-07c6-4b11-ad28-6f5695ebb6e8)

# Here's how:
1. Install the Python package "PyP100", specifically this fork https://github.com/almottier/TapoP100 because https://pypi.org/project/PyP100/ is unmaintained and does not work anymore due to changes to the Tapo authentication mechanism.
   
   `pip3 install git+https://github.com/almottier/TapoP100.git@main`
2. Save this script somewhere, for example `/home/pi/tapo/server.py`, then edit the `TAPO_ADDRESS`, `TAPO_USERNAME`, `TAPO_PASSWORD` fields appropriately.

⚠ **Note:** this is the code for the `P110`, you'll probably need to read the PyP100 docs and change a couple of lines if your plug is not the same.
  ```python3
  #!/usr/bin/python3
  
  import json
  import signal
  from http.server import SimpleHTTPRequestHandler, HTTPServer
  from PyP100 import PyP110
  
  TAPO_ADDRESS = "192.168.x.x"
  TAPO_USERNAME = "your.email@address"
  TAPO_PASSWORD = "hunter2"
  
  p100 = PyP110.P110(TAPO_ADDRESS, TAPO_USERNAME, TAPO_PASSWORD)
  p100.handshake()
  p100.login()
  
  running = True
  
  def exit_gracefully(*args, **kwargs):
      print("Terminating..")
      global running
      running = False
  
  signal.signal(signal.SIGINT, exit_gracefully)
  signal.signal(signal.SIGTERM, exit_gracefully)
  
  
  class MyHttpRequestHandler(SimpleHTTPRequestHandler):
  
      def do_GET(self):
          self.send_response(200)
          self.send_header('Content-type', 'application/json')
          self.end_headers()
  
          try:
             if self.path == "/on":
                 p100.turnOn()
             elif self.path == "/off":
                 p100.turnOff()
          except Exception as e:  # YOLO
             p100.handshake()
             p100.login()
             if self.path == "/on":
                 p100.turnOn()
             elif self.path == "/off":
                 p100.turnOff()
 
          self.wfile.write(json.dumps(p100.getDeviceInfo()).encode("utf-8"))
          return
  
  
  if __name__ == '__main__':
      server_class = HTTPServer
      handler_class = MyHttpRequestHandler
      server_address = ('127.0.0.1', 56427)
  
      httpd = server_class(server_address, handler_class)
      # intentionally making it slow, it doesn't need to react quickly
      httpd.timeout = 1  # seconds
  
      try:
          while running:
              httpd.handle_request()
      except KeyboardInterrupt:
          pass
  ```
3. Make the script executable `chmod +x /home/pi/tapo/server.py`.
4. Make the script autostart, create a service with your editor of choice, e.g. `sudo nano /etc/systemd/system/tapo.service`
  ```
  [Unit]
  Description=Tapo HTTP server
  Wants=network.target
  After=network.target
  
  [Service]
  User=pi
  Group=pi
  ExecStartPre=/bin/sleep 10
  ExecStart=/home/pi/tapo/server.py
  Restart=always
  
  [Install]
  WantedBy=multi-user.target
 ```
5. Start your service `service tapo start`, if something goes wrong you can check status `service tapo status` and logs `journalctl -u tapo`. Then enable it so it autostarts `systemctl enable tapi.service`
6. Open in Mainsail/Fluidd your `Moonraker.cfg`, add this at the end (and maybe customise the device name just after "power"):
```
[power Printer TapoP110]
type: http
on_url: http://localhost:56427/on
off_url: http://localhost:56427/off
status_url: http://localhost:56427/
response_template:
  {% set resp = http_request.last_response().json() %}
  {% if resp["device_on"] %}
    {"on"}
  {% else %}
    {"off"}
  {% endif %}
```
7. Restart Moonraker and that should be all.

Optional goodies for `Moonraker.cfg`, to add below `[power Printer TapoP110]`
```
off_when_shutdown: True
locked_while_printing: False
restart_klipper_when_powered: True
on_when_job_queued: True
```

Optional Klipper auto power off, courtesy of https://github.com/Arksine/moonraker/issues/167#issuecomment-1094223802

Add to `Printer.cfg` or any Klipper config, adjust device name if needed:
```
[idle_timeout]
timeout: 600
gcode:
  MACHINE_IDLE_TIMEOUT

# Turn on PSU
[gcode_macro M80]
gcode:
  # Moonraker action
  {action_call_remote_method('set_device_power',
                             device='Printer TapoP110',
                             state='on')}

# Turn off PSU
[gcode_macro M81]
gcode:
  # Moonraker action
  {action_call_remote_method('set_device_power',
                             device='Printer TapoP110',
                             state='off')}

[gcode_macro MACHINE_IDLE_TIMEOUT]
gcode:
  M84
  TURN_OFF_HEATERS
  M81
```
