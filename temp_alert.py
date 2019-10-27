#!/usr/bin/python
#This script now uses a Raspberry Pi zero W,
#two DS18B20 temp sensor to monitor the freezer and room temperature.

from datetime import datetime
from pytz import timezone
from time import sleep, strftime, time
from decimal import Decimal

import argparse
import pytz
import os
import glob
import logging
import signal
import traceback
import threading
import gmail_lib as gmail
toggledots = 0

parser = argparse.ArgumentParser(description='blah')
parser.add_argument('--alertable', dest='alert', action='store_true')

args = parser.parse_args()

# Global Variables
LOWROOM = 62
HIGHROOM = 99
LOWFREEZER = -30
HIGHFREEZER = 5
TO_ADDRESS = 'oleduc-pager@google.com'
FROM_ADDRESS = 'kenjileduc@gmail.com'
MESSAGE = ''
WAIT_TIME = 3600



# Timer thread will kick off every xx seconds and measure the temperature
class TimerClass(threading.Thread):
    def __init__(self, device_file, device_file_two, single_probe=None):
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.device_file = device_file
        self.device_file_two = device_file_two
        self.single_probe = single_probe

    def run(self):
        # set the starttime
        t0 = time() - WAIT_TIME
        while not self.event.is_set():
	    with open("/home/pi/freezer_room_temp.csv", "a") as log:
	            roomTemp = self.read_temp(1) # sensor 1 is the Room unit
                    freezerTemp = ''
                    if not self.single_probe:
	              freezerTemp = self.read_temp(2) # sensor 2 is the Freezer unit
		    msg_time  = datetime.now(tz=pytz.timezone(("America/Los_Angeles")))
	            log.write("{0},{1}, {2}\n".format(str(msg_time.strftime('%Y-%m-%d %H:%M:%S')),str(freezerTemp),str(roomTemp)))
	            t1 = time()
	            if t1 - t0 > WAIT_TIME and args.alert:
	                if self.checkTempRanges(roomTemp, freezerTemp):
	        	    # checkTempRanges returns True if temp is out of bounds
	                    t0 = time()  # This make sure we wait until WAIT_TIME is complete until we we check temp again.
	            	    time.sleep(2)
	            self.event.wait( 150 )

    def stop(self):
        self.event.set()


    # reads the actual files where the DS18B20 temp sensor records it.
    def read_raw_temp(self, sense):
        if sense == 1:
          f = open(self.device_file, 'r')
        else:
          f = open(self.device_file_two, 'r')
     
        lines = f.readlines()
        f.close()
        return lines
    
    def read_temp(self, sense):
    	lines = self.read_raw_temp(sense)
    	while lines[0].strip()[-3:] != 'YES':
    	    time.sleep(0.1)
    	    lines = self.read_raw_temp()
    	equals_pos = lines[1].find('t=')
    	if equals_pos != -1:
    	    temp_string = lines[1][equals_pos+2:]
    	    temp_c = float(temp_string) / 1000.0
    	    temp_f = temp_c * 9.0 / 5.0 + 32.0
    	return str(temp_f)[:5]
    
    def checkTempRanges(self, roomTemp, freezerTemp):
         if Decimal(roomTemp) >= Decimal(HIGHROOM):
           subject = '[Temperature Alert] : Room too warm! ' + str(roomTemp)
           gmail.GmailWorkflow(FROM_ADDRESS, TO_ADDRESS, subject, MESSAGE)
           print ("Temp too warm! Room: " + str(roomTemp)) 
           return True
         if freezerTemp:
           if Decimal(freezerTemp) >= Decimal(HIGHFREEZER):
             subject = '[Temperature Alert] : Freezer too warm! ' + str(freezerTemp)
             gmail.GmailWorkflow(FROM_ADDRESS, TO_ADDRESS, subject, MESSAGE)
             print ("Temp too warm! Freezer: " + str(freezerTemp)) 
             return True
         if Decimal(roomTemp) <= Decimal(LOWROOM):
           subject = '[Temperature Alert] : Room too cold! ' + str(roomTemp)
           gmail.GmailWorkflow(FROM_ADDRESS, TO_ADDRESS, subject, MESSAGE)
           print ("Temp too cold! Room: " + str(roomTemp)) 
           return True
         if freezerTemp:
           if Decimal(freezerTemp) <= Decimal(LOWFREEZER):
             subject = '[Temperature Alert] : Freezer too cold! ' + str(freezerTemp)
             gmail.GmailWorkflow(FROM_ADDRESS, TO_ADDRESS, subject, MESSAGE)
             print ("Temp too cold! Freezer: " + str(freezerTemp)) 
             return True
         return

def main():
  # need to be root to do this
  os.system('modprobe w1-gpio')
  os.system('modprobe w1-therm')
  
  base_dir = '/sys/bus/w1/devices/'
  try:
    single_probe = True
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
    if len(glob.glob(base_dir + '28*')) > 1:
      single_probe = None
      device_folder_two = glob.glob(base_dir + '28*')[1]
      device_file_two = device_folder_two + '/w1_slave'
  except:
    print "Error 23 reading temp sensor file, sensors connected?"
    exit(23)  
  
  room_min_max = "Room: %dF-%dF" % (LOWROOM,HIGHROOM)
  freezer_min_max = "\nFreezer:%dF-%dF" % (LOWFREEZER,HIGHFREEZER)
  sleep(3)
  tmr = TimerClass(device_file, device_file_two, single_probe=single_probe)
  tmr.start()  # start the timer thread which will wake up and measure temperature

if __name__ == "__main__":
    main()
