# temp_alert

## What does it do

Take temperature, humidity, soil wetness and Air quality measurements and write to a Google spreadsheet.

## Hardware

* A raspberry pi (I use a raspberri pi zero).
* Various options for temperature and humidity:
  * One or two DS18B20 sensors for high range temperature measurements(eg. freezer).
  * DHT22, the cheaper less accurate alternative. humidity sensor built-in.
  * bme280, precise temp and humidity sensor.
* Plant monitor for soil wetness monitoring.
* One Nova PM sensor SDS011 for air quality

## Prerequisites


### Wiring

DHT22:
  * +: 3.3V
  * data: GPIO3
  * -: ground

### Enable modprobe
```
sudo echo "
# OneWire support for temp sensor
dtoverlay=w1-gpio" >> /boot/config.txt

sudo reboot

sudo modprobe w1-gpio
sudo modprobe w1-therm
```


### Install pip3 modules
```
pip3 install -r requirements.txt
```

### Enable Google spreadsheet API from your Google Cloud console
 This is fairly well documented online but essentially you would need to create a project from the Google cloud console, this project should allow the use of the Gmail API and the Google spreadsheet API to your account.
Then create credentials to access the API, at the time of writing the creds are in OAuth 2.0 format. Download the json file into the temp_alert folder and name it credentials.json.

### First run
We need to allow the script to access your google account. In order to allow the Google API to access your account, we need to run the authorization workflow, wich requires login in to your google account. Browsing that URL can only work from the same machine where the script runs from. Given that this is most likely a headless computer (e.g. a raspberry pi), you would need to either use ssh tunnel, or X window. I used X window as it was the most straightforward option. 

Run the command for the first time from the CLI will trigger the auth workflow.
```
python3 temp_alert.py --sheetid 1ZBNVL7OTabZZkPO_8sc_f3FzerB-VQrGj1sS_BVybgc --frequency 15
```

### Create as service so it will auto start at boot time:

sudo vi /lib/systemd/system/temp_alert.service
```
[Unit]
Description=TempAlert
After=multi-user.target

[Service]
ExecStart=/usr/bin/python3 /home/<replace_with_username>/temp_alert/temp_alert.py --sheetid 1n44bjHaKoMzoYmxDiink791TIWgy_5Ga7VFg9W1GhFY --frequency '15' --alertable
Restart=always
User=<replace_with_username>

[Install]
WantedBy=multi-user.target

```

