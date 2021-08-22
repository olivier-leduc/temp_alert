#! /usr/bin/python3
# Take temperature, humidity and Air quality measurements and write to a Google spreadsheet.
#
# Utilize the following hardware:
#* A raspberry pi (I use a raspberri pi zero).
#* One or two DS18B20 sensors for accurate temperature measurements.
#* One DHT22 for humidity (can also use the builtin temp sensor but I found it to be less accurate, let alone the fact that I can't put it in the freezer.)
#* One Nova PM sensor SDS011 for air quality
#
#
# temp_alert does the following:
# 1) logs temperature onto a Google spreadsheet and optionally to a local log file.
# 2) Sends an email when temperature or airquality goes out of bounds.

from datetime import datetime
from decimal import Decimal
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
parser.add_argument('--frequency', dest='freq')
parser.add_argument('--alertable', dest='alert', action='store_true')
parser.add_argument('--writetolog', dest='writetolog', action='store_true')
parser.add_argument('--debug', dest='debug', action='store_true')
flags = parser.parse_args()

DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 3
# Temperature bounds.
ROOM_TEMP_MIN_MAX = [62, 99]
FREEZER_TEMP_MIN_MAX = [-30, 5]
# Air quality threshold.
AIR_QUAL_THRESHOLD = 100
# Path of local CSV file.
OUTPUT_FILE = "/home/pi/freezer_room_temp.csv"
# Max number of rows in Google spreadsheet, before starting to clear the last row
MAX_ROWS = 300
# Email alert addresses.
TO_ADDRESS = '4154121947@vtext.com, 4157307200@vtext.com'
FROM_ADDRESS = 'kenjileduc@gmail.com'
# ALERT_FREQ = flags.freq x 4 = Wait time between each alert`
ALERT_FREQ = 4
# Replace with bogus value when no reading on sensor.
NO_READING = "-999"

class TempAlert(object):
  def __init__(self, sensor_path_list):
    self.end = False
    self.sensor_path_list = sensor_path_list

  def run(self):
    count = 0
    while not self.end:
      temp_1 = temp_2 = NO_READING
      if self.sensor_path_list:
        temp_1 = self.ReadTemp(self.sensor_path_list[0])
        if len(self.sensor_path_list) == 2:
          temp_2 = self.ReadTemp(self.sensor_path_list[1])
      humidity, dht22_temp = self.ReadHumidityTemp()
      air_quality = self.ReadAirQuality()
      # Air quality sensors sometimes reports high bogus values, in that case, run again.
      if Decimal(air_quality) >= 200:
        time.sleep(3)
        air_quality = self.ReadAirQuality()
      msg_time  = datetime.now(tz=pytz.timezone(("America/Chicago"))).strftime('%H:%M:%S %m-%d')
      logging.info("time: %s, freezerTemp: %s, roomTemp: %s, dht22_temp: %s, humidity: %s, airquality: %s", msg_time, temp_1, temp_2, dht22_temp, humidity, air_quality)
      if flags.writetolog:
        with open(OUTPUT_FILE, "a") as log:
          log.write("{0}, {1}, {2}, {3}, {4}\n".format(msg_time, temp_1, dht22_temp, humidity, air_quality))
      # Send data to Google Spreadsheet.
      row = [[msg_time, temp_1, dht22_temp, humidity, air_quality],]
      self.WriteToSheet(row)
      t1 = time.time()
      count = 0 if count == ALERT_FREQ else count  # Reset counter
      count += 1
      if flags.alert and count == 1:  # Only run the alerts once every ALERT_FREQ
        temp_reads = {}
        if temp_1 != NO_READING:
          temp_reads['freezer'] = temp_1
        if temp_2 != NO_READING:
          temp_reads['room2'] = temp_2
        if dht22_temp != NO_READING:
          temp_reads['Garage'] = dht22_temp
        for room, temp in temp_reads.items():
          if room == 'freezer': 
            if self.CheckTempRanges(room, temp, FREEZER_TEMP_MIN_MAX):  # Send temperature alert if needed
              # CheckTempRanges returns True if temp is out of bounds
              time.sleep(2)
        if air_quality != NO_READING:
            self.CheckAirQualityRanges(air_quality)  # Send AirQual alert if needed
      time.sleep(int(flags.freq)*60)

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
        return NO_READING
    except Exception as err:
        print("Failed to retrieve data from air quality sensor: %s" % err)
        return NO_READING
    #return str(pmtwofive)
    return float(pmten)

  def ReadHumidityTemp(self):
    try:
      humidity, dht22_temp_c = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
      if not humidity or not dht22_temp_c:
        print("Failed to retrieve data from humidity sensor")
        return NO_READING, NO_READING
    except Exception as err:
      print("Failed to retrieve data from humidity sensor" % err)
      return NO_READING, NO_READING
    # Convert the temperature from Fahrenheit to Celsius.
    dht22_temp = round((dht22_temp_c * 9.0 / 5.0 + 32.0), 1)
    humidity = round(humidity, 1)
    return float(humidity), float(dht22_temp)

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
      return round(temp_f, 1)
    else:
      return NO_READING
  
  def CheckAirQualityRanges(self, air_quality):
    if Decimal(air_quality) > AIR_QUAL_THRESHOLD:
      subject = 'Air Quality alert: ' + str(air_quality) + ' (UNHEALTHY) '
      message = 'http://shorturl.at/uPVY4'
      self.SendEmailAlert(subject, message)

  def CheckTempRanges(self, room, temperature, temp_min_max):
    #message = 'http://shorturl.at/tyFGNo'
    message = ''  # Verizon filters text with URLs in body.
    if Decimal(temperature) >= Decimal(temp_min_max[1]):
      cold_or_warm = 'warm! '
    elif Decimal(temperature) <= Decimal(temp_min_max[0]) and temperature != NO_READING:
      cold_or_warm = 'cold! '
    else:
      return False
    logging.info('Temp too %s in %s: %s', cold_or_warm, room, str(temperature)) 
    subject = '[Temperature alert] ' + room + ' too  ' + cold_or_warm.upper() + str(temperature)
    logging.info('Sending alert messages to %s', TO_ADDRESS)
    self.SendEmailAlert(subject, message)
    return True

  def SendEmailAlert(self, subject, message):
    service = google_lib.InitGoogleService('gmail', 'v1', flags)
    logging.info('Google_lib service: %s', service)
    email = google_lib.CreateMessage(FROM_ADDRESS, TO_ADDRESS, subject, message)
    google_lib.SendMessage(service, "me", email)

  def WriteToSheet(self, row):
    sheet_content = ''
    try:
      sheetservice = google_lib.InitGoogleService('sheets', 'v4', flags)
      sheet_content = list(sheetservice.spreadsheets().values().get(spreadsheetId=flags.sheetid, range="Sheet1!A1:E").execute().values())
    except Exception as err:
      logging.error("Exception with sheet: %s", err)
      return
    for item in sheet_content:
      if type(item) == list:
        sheet_content = item
        break
    try:
      if sheet_content and len(sheet_content) > MAX_ROWS:
        logging.info('Reached row %s in Google spreadsheet, deleting that row.', MAX_ROWS)
        delete_row_body = {
          "requests" : [
            {
              "deleteDimension": {
                "range": {
                  "sheetId": 0,
                  "dimension": "ROWS",
                  "startIndex": MAX_ROWS,
                  "endIndex": MAX_ROWS + 1
                }
              }
            }
          ]
        }
        sheetservice.spreadsheets().batchUpdate(
          spreadsheetId=flags.sheetid,
          body=delete_row_body).execute()
      spreadsheet_request_body = {
        "requests": [
          {
            "insertDimension": {
              "range": {
                "sheetId": 0,
                "dimension": "ROWS",
                "startIndex": 1,
                "endIndex": 2
            }  ,
            "inheritFromBefore": False
            }
          }
        ]
      }
      sheetservice.spreadsheets().batchUpdate(
        spreadsheetId=flags.sheetid,
        body=spreadsheet_request_body).execute()
      body = {
        'values': row
      }
      sheetservice.spreadsheets().values().update(
        spreadsheetId=flags.sheetid, range='A2:XX',
        valueInputOption='RAW', body=body).execute()
    except Exception as err:
      logging.error("Exception with sheet: %s", err)
      return

def LoadSensors():
  # need to be root to do this
  os.system('modprobe w1-gpio')
  os.system('modprobe w1-therm')
  base_dir = '/sys/bus/w1/devices/'
  sensor_path_list = []
  try:
    for device_folder in glob.glob(base_dir + '28*'):
      sensor_path_list.append(device_folder + '/w1_slave')
    if flags.debug:
        print("sensor path list:", sensor_path_list)
    return sensor_path_list
  except:
    print("Error reading temperature sensor file, sensors connected?")
    return None
 

def main():
  logging.basicConfig(level=logging.INFO)
  log = logging.getLogger('example')
  sensor_path_list = LoadSensors()
  time.sleep(.5)
  tempalert = TempAlert(sensor_path_list)
  tempalert.run()

if __name__ == "__main__":
  main()
