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

         global p100  # hack to fight Tapo session expiry, somehow just redoing handhsake and login doesn't work
         try:
             if self.path == "/on":
                 p100.turnOn()
             elif self.path == "/off":
                 p100.turnOff()
             self.wfile.write(json.dumps(p100.getDeviceInfo()).encode("utf-8"))
         except Exception as e:  # YOLO
             p100 = PyP110.P110(TAPO_ADDRESS, TAPO_USERNAME, TAPO_PASSWORD)
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
