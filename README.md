# temp_alert

## What does it do

Take temperature, humidity and Air quality measurements and write to a Google spreadsheet.

## Hardware

* A raspberry pi (I use a raspberri pi zero).
* One or two DS18B20 sensors for accurate temperature measurements.
* One DHT22 for humidity (can also use the builtin temp sensor but I found it to be less accurate, let alone the fact that I can't put it in the freezer.)
* One Nova PM sensor SDS011 for air quality

## Prerequisites


### Wiring

[Wiring of a single sensor to a Raspi2 (same wiring for the PiZero)](images/Raspberry-Pi-DS18B20.png)


### Enable modprobe
```
sudo echo "
# OneWire support for temp sensor
dtoverlay=w1-gpio" >> /boot/config.txt

sudo reboot

sudo modprobe w1-therm
```


### Install pip3 modules
```
pip3 install -r requirements.txt
```

### Enable Google spreadsheet API from your Google Cloud console
Lookup how to do this.

### Copy Google client-secret from Google Cloud console
```
echo <your_google_api_secret> > client_secret.json
```

### First run
We need to allow the script to access your google account. Add the 
 "--noauth_local_webserver" on the first run. Ex:
```
python3 temp_alert.py --sheetid 1ZBNVL7OTabZZkPO_8sc_f3FzerB-VQrGj1sS_BVybgc --frequency 15 --debug --noauth_local_webserver
```

### Run as startup script:

```
cat /etc/init.d/temp_alert.sh
#! /bin/sh
# /etc/init.d/temp_alert

### BEGIN INIT INFO
# Provides:          temp_alert.py
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start daemon at boot time
# Description:       Enable service provided by daemon.
### END INIT INFO

echo "starting temperature monitor"
/usr/bin/python3 /home/pi/temp_alert.py --sheetid 1n44bjHaKoMzoYmxDiink791TIWgy_5Ga7VFg9W1GhFY --alertable --frequency 15
exit 0

sudo update-rc.d temp_alert.sh defaults
sudo update-rc.d temp_alert.sh enable
```

