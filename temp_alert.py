# !/usr/bin/python
# This script uses a Raspberry Pi zero W and support up to 2x DS18B20
# temperature sensors.
#
# A minimum of one sensor is needed for the script to startup.
# temp_alert does the following:
# 1) logs temperature into a local textfile and a Google spreadsheet.
# 2) Sends an email when temperature goes out of bounds.

from datetime import datetime
from time import sleep, strftime, time
from decimal import Decimal

import argparse
import pytz
import os
import glob
import logging
import threading
import google_lib
from oauth2client import tools

parser = argparse.ArgumentParser(parents=[tools.argparser], description='')
parser.add_argument('--sheetid', dest='sheetid')
parser.add_argument('--alertable', dest='alert', action='store_true')
flags = parser.parse_args()

# Temperature bounds.
ROOM_TEMP_MIN_MAX = [62, 99]
FREEZER_TEMP_MIN_MAX = [-30, 5]
# Path of local CSV file.
OUTPUT_FILE = "/home/pi/freezer_room_temp.csv"
# Max number of rows in Google spreadsheet, before sheet gets cleared.
# Each row is a temperature measurement cycle (ref. TEMP_WAIT)
MAX_ROWS = 288
# Email alert addresses.
TO_ADDRESS = 'dstemailaddress'
FROM_ADDRESS = 'srcemailaddress'
# Time to wait between each temperature measurement.
TEMP_WAIT = 150
# Time to wait after temperature reached bound limit.
ALERT_WAIT = 3600

# Timer thread will kick off every xx seconds and measure the temperature
class TempAlert(threading.Thread):
    def __init__(self, sensor_path_list):
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.sensor_path_list = sensor_path_list

    def run(self):
        t0 = time() - ALERT_WAIT  # set the starttime
        while not self.event.is_set():
	    with open(OUTPUT_FILE, "a") as log:
		roomTemp = self.read_temp(self.sensor_path_list[0])
		freezerTemp = ''
		if len(self.sensor_path_list) > 1:
		    freezerTemp = self.read_temp(self.sensor_path_list[1])
		msg_time  = datetime.now(tz=pytz.timezone(("America/Los_Angeles")))
		log.write("{0}, {1}, {2}\n".format((msg_time.strftime('%Y-%m-%d %H:%M:%S')),str(freezerTemp),str(roomTemp)))
		row = [[msg_time.strftime('%Y-%m-%d %H:%M:%S'), float(freezerTemp), float(roomTemp)]]
		self.WriteToSheet(row)
		t1 = time()
		if t1 - t0 > ALERT_WAIT:
		    if self.checkTempRanges(roomTemp, ROOM_TEMP_MIN_MAX, 'room'):
			# checkTempRanges returns True if temp is out of bounds
			t0 = time()  # This make sure we wait until ALERT_WAIT is complete until we check temp again and send an alert.
			time.sleep(2)
		    if freezerTemp:
			if self.checkTempRanges(freezerTemp, FREEZER_TEMP_MIN_MAX, 'freezer'):
			    # checkTempRanges returns True if temp is out of bounds
			    t0 = time()  # This make sure we wait until ALERT_WAIT is complete until we check temp again and send an alert.
			    time.sleep(2)
		self.event.wait(TEMP_WAIT)

    def stop(self):
        self.event.set()


    # reads the actual files where the DS18B20 temp sensor records it.
    def read_raw_temp(self, sensor_path):
        f = open(sensor_path, 'r')
        lines = f.readlines()
        f.close()
        return lines
    
    def read_temp(self, sensor_path):
    	lines = self.read_raw_temp(sensor_path)
    	while lines[0].strip()[-3:] != 'YES':
    	    time.sleep(0.1)
    	    lines = self.read_raw_temp(sensor_path)
    	equals_pos = lines[1].find('t=')
    	if equals_pos != -1:
    	    temp_string = lines[1][equals_pos+2:]
    	    temp_c = float(temp_string) / 1000.0
    	    temp_f = temp_c * 9.0 / 5.0 + 32.0
    	return str(temp_f)[:5]
    
    def checkTempRanges(self, temperature, temp_min_max, wherethesensoris):
        message = ''
        if Decimal(temperature) >= Decimal(temp_min_max[1]):
	    cold_or_warm = 'warm! '
        elif Decimal(temperature) <= Decimal(temp_min_max[0]):
	    cold_or_warm = 'cold! '
        else:
          return False
	print ('Temp too ' + cold_or_warm + str(temperature)) 
        if flags.alert:
	    subject = '[Temperature Alert] : ' + wherethesensoris + ' too  ' + cold_or_warm + str(temperature)
	    self.SendEmailAlert(subject)
	return True

    def SendEmailAlert(subject):
	service = google_lib.InitGoogleService('gmail', 'v1', flags)
	email = google_lib.CreateMessage(TO_ADDRESS, FROM_ADDRESS, subject, message)
	google_lib.SendMessage(service, "me", email)

    def WriteToSheet(self, row):
        service = google_lib.InitGoogleService('sheets', 'v4', flags)
        sheet_content = service.spreadsheets().values().get(spreadsheetId=flags.sheetid, range="Sheet1!A2:B").execute().values()[1]
        if len(sheet_content) > MAX_ROWS:
	    logging.info('Reached cell %s in Google spreadsheet, clearing sheet', _MAX_ROWS)
	    google_lib.ClearSheet(service, flags.sheetid)
        google_lib.AppendGsheet(service, row, flags.sheetid)

def main():
    # need to be root to do this
    os.system('modprobe w1-gpio')
    os.system('modprobe w1-therm')
    base_dir = '/sys/bus/w1/devices/'
    sensor_path_list = []
    try:
	for device_folder in glob.glob(base_dir + '28*'):
	    sensor_path_list.append(device_folder + '/w1_slave')
    except:
	print "Error reading temperature sensor file, sensors connected?"
	exit(1)  
    sleep(3)
    tempalert = TempAlert(sensor_path_list)
    tempalert.start()

if __name__ == "__main__":
    main()
