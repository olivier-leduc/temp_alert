# temp_alert

## What does it do

Measure temperature using the DS18B20 temperature sensor
on raspberry pi.

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
