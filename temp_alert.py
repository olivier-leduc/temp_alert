# !/usr/bin/python3
# This script uses a Raspberry Pi zero W and support up to 2x DS18B20
# temperature sensors.
#
# A minimum of one sensor is needed for the script to startup.
# temp_alert does the following:
# 1) logs temperature into a local textfile and a Google spreadsheet.
# 2) Sends an email when temperature goes out of bounds.

from datetime import datetime
from decimal import Decimal
#from memory_profiler import profile
import serial
import time

import argparse
import pytz
import gc
import os
import glob
import logging
import threading
import google_lib
import Adafruit_DHT
from oauth2client import tools

parser = argparse.ArgumentParser(parents=[tools.argparser], description='')
parser.add_argument('--sheetid', dest='sheetid')
parser.add_argument('--alertable', dest='alert', action='store_true')
parser.add_argument('--writetolog', dest='writetolog', action='store_true')
flags = parser.parse_args()

DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 4
# Temperature bounds.
ROOM_TEMP_MIN_MAX = [62, 99]
FREEZER_TEMP_MIN_MAX = [-30, 5]
# Path of local CSV file.
OUTPUT_FILE = "/home/pi/freezer_room_temp.csv"
# Max number of rows in Google spreadsheet, before sheet gets cleared.
# Each row is a temperature measurement cycle (ref. TEMP_WAIT)
MAX_ROWS = 288
# Email alert addresses.
TO_ADDRESS = 'oleduc-pager@google.com'
FROM_ADDRESS = 'kenjileduc@gmail.com'
# Time to wait between each temperature measurement.
TEMP_WAIT = 150
# Time to wait after temperature reached bound limit.
ALERT_WAIT = 3600

class TempAlert(object):
    def __init__(self, sensor_path_list):
        self.end = False
        self.sensor_path_list = sensor_path_list

    def run(self):
        t0 = time.time() - ALERT_WAIT  # set the starttime
        while not self.end:
            with open(OUTPUT_FILE, "a") as log:
                temp_2 = "0"
                if len(self.sensor_path_list) > 1:
                    temp_2 = self.ReadTemp(self.sensor_path_list[1])
                temp_1 = self.ReadTemp(self.sensor_path_list[0])
                humidity, dht22_temp = self.ReadHumidityTemp()
                air_quality = self.ReadAirQuality()
                msg_time  = datetime.now(tz=pytz.timezone(("America/Los_Angeles"))).strftime('%Y-%m-%d %H:%M:%S')
                logging.info("time: %s, roomTemp: %s(%s), freezerTemp: %s(%s), dht22_temp: %s(%s), humidity: %s(%s), airquality: %s(%s)", msg_time, temp_1, type(temp_1), temp_2, type(temp_2), dht22_temp, type(dht22_temp), humidity, type(humidity), air_quality, type(air_quality))
                if flags.writetolog:
                    log.write("{0}, {1}, {2}, {3}, {4}\n".format(msg_time, temp_1, dht22_temp, humidity, air_quality))
                row = [[msg_time, float(temp_2), float(temp_1), float(humidity), float(air_quality)]]
                self.WriteToSheet(row)
                t1 = time.time()
                if t1 - t0 > ALERT_WAIT:
                    if self.CheckTempRanges(temp_1, ROOM_TEMP_MIN_MAX, 'room'):
                        # CheckTempRanges returns True if temp is out of bounds
                        t0 = time.time()  # This make sure we wait until ALERT_WAIT is complete until we check temp again and send an alert.
                        time.sleep(2)
                    if temp_2:
                        if self.CheckTempRanges(temp_2, FREEZER_TEMP_MIN_MAX, 'freezer'):
                            # CheckTempRanges returns True if temp is out of bounds
                            t0 = time.time()  # This make sure we wait until ALERT_WAIT is complete until we check temp again and send an alert.
                            time.sleep(2)
                time.sleep(TEMP_WAIT)

    def stop(self):
            self.end = True

    def ReadAirQuality(self):
        try:
            s = serial.Serial('/dev/ttyUSB0')
            data = []
            for index in range(0, 10):
                d = s.read()
                data.append(d)
            pmtwofive = int.from_bytes(b''.join(data[2:4]), byteorder='little') / 10
            pmten = int.from_bytes(b''.join(data[4:6]), byteorder='little') / 10
            if not pmtwofive:
                return "0"
        except Exception as err:
                print("Failed to retrieve data from air quality sensor: %s" % err)
                return "0"
        #return str(pmtwofive)
        return str(pmten)

    def ReadHumidityTemp(self):
        try:
            humidity, dht22_temp_c = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
            if not humidity or not dht22_temp_c:
                print("Failed to retrieve data from humidity sensor")
                return "0", "0"
        except Exception as err:
            print("Failed to retrieve data from humidity sensor" % err)
            return "0", "0"
	# Convert the temperature from Fahrenheit to Celsius.
        dht22_temp = dht22_temp_c * 9.0 / 5.0 + 32.0
        return str(humidity), str(dht22_temp)

    # reads the actual files where the DS18B20 temp sensor records it.
    def ReadRawTemp(self, sensor_path):
        f = open(sensor_path, 'r')
        lines = f.readlines()
        f.close()
        return lines
    
    def ReadTemp(self, sensor_path):
        lines = self.ReadRawTemp(sensor_path)
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(1)
            lines = self.ReadRawTemp(sensor_path)
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            return str(temp_f)[:5]
        else:
            return "0"
    
    def CheckTempRanges(self, temperature, temp_min_max, wherethesensoris):
        message = ''
        if Decimal(temperature) >= Decimal(temp_min_max[1]):
            cold_or_warm = 'warm! '
        elif Decimal(temperature) <= Decimal(temp_min_max[0]):
            cold_or_warm = 'cold! '
        else:
          return False
        print('Temp too ' + cold_or_warm + str(temperature)) 
        if flags.alert:
            subject = '[Temperature Alert] : ' + wherethesensoris + ' too  ' + cold_or_warm + str(temperature)
            self.SendEmailAlert(subject)
        return True

    def SendEmailAlert(subject):
        service = google_lib.InitGoogleService('gmail', 'v1', flags)
        email = google_lib.CreateMessage(TO_ADDRESS, FROM_ADDRESS, subject, message)
        google_lib.SendMessage(service, "me", email)

#    @profile(precision=4)
    def WriteToSheet(self, row):
        sheet_content = ''
        try:
            sheetservice = google_lib.InitGoogleService('sheets', 'v4', flags)
            sheet_content = list(sheetservice.spreadsheets().values().get(spreadsheetId=flags.sheetid, range="Sheet1!A2:E").execute().values())[1]
        except Exception as err:
            logging.error("Exception with sheet: %s", err)
            return
        if sheet_content and len(sheet_content) > MAX_ROWS:
            logging.info('Reached cell %s in Google spreadsheet, clearing sheet', MAX_ROWS)
            google_lib.ClearSheet(sheetservice, flags.sheetid)
        google_lib.AppendGsheet(sheetservice, row, flags.sheetid)

def main():
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('example')
    # need to be root to do this
    os.system('modprobe w1-gpio')
    os.system('modprobe w1-therm')
    base_dir = '/sys/bus/w1/devices/'
    sensor_path_list = []
    try:
        for device_folder in glob.glob(base_dir + '28*'):
            sensor_path_list.append(device_folder + '/w1_slave')
    except:
        print("Error reading temperature sensor file, sensors connected?")
        exit(1)  
    time.sleep(3)
    tempalert = TempAlert(sensor_path_list)
    tempalert.run()


if __name__ == "__main__":
    main()
