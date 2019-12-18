# temp_alert

## What does it do

Take temperature, humidity and Air quality measurements and write to a Google spreadsheet.

## Hardware

* A raspberry pi (I use a raspberri pi zero).
* One or two DS18B20 sensors for accurate temperature measurements.
* One DHT22 for humidity (can also use the builtin temp sensor but I found it to be less accurate, let alone the fact that I can't put it in the freezer.)
* One Nova PM sensor SDS011 for air quality

## Prerequisites

[TODO]

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
