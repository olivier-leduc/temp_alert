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

from datetime import datetime, timedelta
from decimal import Decimal
from plant_monitor import PlantMonitor
import serial
import time

import board
from adafruit_bme280 import basic as adafruit_bme280

import argparse
import pytz
import gc
import os
import glob
import logging
import threading
import google_lib
#import Adafruit_DHT
from oauth2client import tools

parser = argparse.ArgumentParser(parents=[tools.argparser], description='')
parser.add_argument('--sheetid', dest='sheetid')
parser.add_argument('--frequency', dest='freq')
parser.add_argument('--toemail', dest='toemail')
parser.add_argument('--fromemail', dest='fromemail')
parser.add_argument('--tempmin', dest='tempmin')
parser.add_argument('--tempmax', dest='tempmax')
parser.add_argument('--dht22', dest='dht22', action='store_true')
parser.add_argument('--bme280', dest='bme280', action='store_true')
parser.add_argument('--ds18b20', dest='ds18b20', action='store_true')
parser.add_argument('--airqual', dest='airqual', action='store_true')
parser.add_argument('--si7021', dest='si7021', action='store_true')
parser.add_argument('--plantmonitor', dest='plantmonitor', action='store_true')
parser.add_argument('--alertable', dest='alert', action='store_true')
flags = parser.parse_args()

#DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 3
# Default temperature bounds.
TEMP_MIN_MAX = {"room":(62, 95), "freezer":(-30, 5)}
# Air quality threshold.
AIR_QUAL_THRESHOLD = 100
# Path of local CSV file.
OUTPUT_FILE = "/home/kenjidnb/freezer_room_temp.csv"
# Max number of rows in Google spreadsheet, before starting to clear the last row
MAX_ROWS = 300
# Replace with bogus value when no reading on sensor.
NO_READING = "-999"
TEMPSENSOR1 = "outside"
TEMPSENSOR2 = "room"
TEMPSENSOR3 = "freezer"


def LoadDS18B20Sensors():
  # need to be root to do this
  base_dir = '/sys/bus/w1/devices/'
  sensor_path_list = []
  try:
    for device_folder in glob.glob(base_dir + '28*'):
      sensor_path_list.append(device_folder + '/w1_slave')
  except:
    print("Error reading temperature sensor file, sensors connected?")
  return sensor_path_list

def GetDS18B20Temps():
 sensor_path_list = LoadDS18B20Sensors()
 if sensor_path_list:
   temp_2 = ReadDS18B20Temp(sensor_path_list[0])
   if len(sensor_path_list) == 2:
     temp_3 = ReadDS18B20Temp(sensor_path_list[1])
 return temp_2, temp_3

def ReadAirQuality():
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
  # Air quality sensors sometimes reports high bogus values, in that case, run again.
  air_quality = float(pmten)
  if Decimal(float(pmten)) >= 200:
      air_quality = NO_READING
  return air_quality

def ReadPreciseHumidityTempPressure(sensor):
  try:
    sensor.sea_level_pressure = 1013.25
    temp_c = sensor.temperature
    humidity = sensor.relative_humidity
    pressure = sensor.pressure
    if not humidity or not temp_c:
      print("Failed to retrieve data from humidity sensor")
      return NO_READING, NO_READING
  except Exception as err:
    print("Failed to retrieve data from humidity sensor" % err)
    return NO_READING, NO_READING
  # Convert the temperature from Celsius to Fahrenheit.
  temp_f = round((temp_c * 9.0 / 5.0 + 32.0), 1)
  humidity = round(humidity, 1)
  return float(humidity), float(temp_f), float(pressure)


def ReadDHT22HumidityTemp():
  try:
    humidity, temp_c = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
    if not humidity or not temp_c:
      print("Failed to retrieve data from humidity sensor")
      return NO_READING, NO_READING
  except Exception as err:
    print("Failed to retrieve data from humidity sensor" % err)
    return NO_READING, NO_READING
  # Convert the temperature from Celsius to Fahrenheit.
  temp_f = round((temp_c * 9.0 / 5.0 + 32.0), 1)
  humidity = round(humidity, 1)
  return float(humidity), float(temp_f)

# reads the actual files where the DS18B20 temp sensor records it.
def ReadRawTemp(sensor_path):
  f = open(sensor_path, 'r')
  lines = f.readlines()
  f.close()
  return lines

def ReadDS18B20Temp(sensor_path):
  lines = ReadRawTemp(sensor_path)
  while lines[0].strip()[-3:] != 'YES':
    time.sleep(1)
    lines = ReadRawTemp(sensor_path)
  equals_pos = lines[1].find('t=')
  if equals_pos != -1:
    temp_string = lines[1][equals_pos+2:]
    temp_c = float(temp_string) / 1000.0
    temp_f = temp_c * 9.0 / 5.0 + 32.0
    return round(temp_f, 1)
  else:
    return NO_READING

def CheckAirQualityRanges(air_quality):
  if air_quality != NO_READING and (Decimal(air_quality) > AIR_QUAL_THRESHOLD):
    subject = 'Air Quality alert: ' + str(air_quality) + ' (UNHEALTHY) '
    message = 'http://shorturl.at/uPVY4'
    SendEmailAlert(subject, message)
    return True
  else:
    return False

def CheckTempRanges(tempsensor, temperature, temp_min_max):
  '''returns true if alert fires'''
  if temperature == NO_READING:
    return False
  #message = 'http://shorturl.at/tyFGNo'
  message = ''  # Verizon filters text with URLs in body.
  if flags.tempmin and flags.tempmax:
    temp_min_max = (int(flags.tempmin), int(flags.tempmax))
  if Decimal(temperature) >= Decimal(temp_min_max[1]):
    cold_or_warm = 'warm! '
  elif Decimal(temperature) <= Decimal(temp_min_max[0]) and temperature != NO_READING:
    cold_or_warm = 'cold! '
  else:
    return False
  subject = 'Temp too {}, "{}": {}'.format(cold_or_warm, tempsensor, str(temperature)) 
  logging.info(subject)
  logging.info('Sending alert messages to %s', flags.toemail)
  SendEmailAlert(subject, message)
  time.sleep(2) # Can't remember why I put this timer.
  return True

def SendEmailAlert(subject, message):
  service = google_lib.InitGoogleService('gmail', 'v1', flags)
  logging.info('Google_lib service: %s', service)
  email = google_lib.CreateMessage(flags.fromemail, flags.toemail, subject, message)
  google_lib.SendMessage(service, "me", email)

def WriteToSheet(temp_reads, humidity, pressure, air_quality, wetness):
  # Log everything
  msg_time  = datetime.now(tz=pytz.timezone(("America/Chicago"))).strftime('%H:%M:%S %m-%d')
  logging.info("time: %s, tempsensor1: %s, humidity: %s, pressure: %s, tempsensor2: %s, tempsensor3: %s, airquality: %s, wetness: %s", msg_time, temp_reads[TEMPSENSOR1], humidity, pressure, temp_reads[TEMPSENSOR2], temp_reads[TEMPSENSOR3], air_quality, wetness)
  with open(OUTPUT_FILE, "a") as log:
    log.write("{0}, {1}, {2}, {3}, {4}, {5} {6}\n".format(msg_time, temp_reads[TEMPSENSOR1], humidity, pressure, temp_reads[TEMPSENSOR2], temp_reads[TEMPSENSOR3], air_quality, wetness))
  row = [[msg_time, temp_reads[TEMPSENSOR1], humidity, pressure, temp_reads[TEMPSENSOR2], temp_reads[TEMPSENSOR3], air_quality, wetness],]
  sheet_content = ''
  try:
    sheetservice = google_lib.InitGoogleService('sheets', 'v4', flags)
    sheet_content = list(sheetservice.spreadsheets().values().get(spreadsheetId=flags.sheetid, range="Sheet1!A1:H").execute().values())
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

def run():
  # Create sensor object, using the board's default I2C bus.
  temp_reads = {TEMPSENSOR1: NO_READING, TEMPSENSOR2: NO_READING, TEMPSENSOR3: NO_READING}
  alert_time = datetime.now()
  if flags.bme280 or flags.ic7021:
    i2c = board.I2C()  # uses board.SCL and board.SDA
  while True: # This thing runs 24/7
    if flags.bme280:
      bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)
      humidity, temp_reads[TEMPSENSOR1], pressure = ReadPreciseHumidityTempPressure(bme280)
    elif flags.si7021:
      si7021 = adafruit_si7021.SI7021(board.I2C())
      humidity, temp_reads[TEMPSENSOR1], pressure = ReadPreciseHumidityTempPressure(si7021)
    elif flags.ds18b20:
      temp_reads[TEMPSENSOR2], temp_reads[TEMPSENSOR3] = GetDS18B20Temps()
    elif flags.dht22:
      humidity, temp_reads[TEMPSENSOR3] = ReadDHT22HumidityTemp()
    if flags.airqual:
      # Get air quality from SDS011
      air_quality = ReadAirQuality()
    else:
      air_quality = NO_READING
    if flags.plantmonitor:
        # Get wetness from plantmonitor
        pm=PlantMonitor()
        wetness = str(pm.get_wetness())
    else:
        wetness = NO_READING
    # Send data to Google Spreadsheet.
    WriteToSheet(temp_reads, humidity, pressure, air_quality, wetness)
    # Run the alert routine
    if flags.alert and (datetime.now() - alert_time) > timedelta(seconds=3600):  # One alert per hour max.
        for tempsensor, temp in temp_reads.items():
            # Send temperature alert if needed. CheckTempRanges returns True and sends alert if temp is out of bounds
            tempalert_fired = CheckTempRanges(tempsensor, temp, TEMP_MIN_MAX)
        airqualalert_fired = CheckAirQualityRanges(air_quality)  # Send AirQual alert if needed
        if tempalert_fired or airqualalert_fired:
            logging.info("Alerts fired, continuing to monitor")
            alert_time = datetime.now()
    logging.info('Monitoring cycle complete, waiting %s seconds before starting a new cycle', flags.freq)
    time.sleep(int(flags.freq))


def main():
  logging.basicConfig(level=logging.INFO)
  #log = logging.getLogger('example')
  time.sleep(.5)
  run()

if __name__ == "__main__":
  main()
