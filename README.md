# AIMSPowerInverterMQTT

This project was created to automatically monitor the [AIMS Power 1250W Power Inverter Charger (PICOGLF12W12V120AL)](https://amzn.to/41PUYct) and connected deep-cycle battery(s) via [Home Assistant](https://www.home-assistant.io/) using [MQTT](https://mqtt.org/) and the UART serial port pins of a [Raspberry Pi Zero W](https://www.raspberrypi.com/products/raspberry-pi-zero-w/) connected to the inverter RJ-45 port. This setup may be compatible with other AIMS Power inverter models that include a serial port accessible via the RJ-45 port.

The inverter and battery data published to Home Assistant can be used to create [custom automations](https://www.home-assistant.io/getting-started/automation/) to send notifications and take actions on other devices integrated into the [Home Assistant ecosystem](https://www.home-assistant.io/integrations/) such as automatically powering down devices when the inverter battery is low.

![Screenshot](https://raw.githubusercontent.com/stevesinchak/AIMSPowerInverterMQTT/main/screenshot.jpg)

The following data will be available in Home Assistant via an auto-discovered MQTT device once this app is fully setup and configured according to the instructions below:

- Battery Status (OK/Low)
- Battery Voltage (Volts)
- Utility Power Active (Yes/No)
- Utility Line Voltage (Volts)
- Utility Line Voltage Fault Level (Volts)
- Inverter Load Percentage (%)
- Inverter Output Voltage (Volts)
- Inverter Output Frequency (Hz)
- Inverter Temperature (c)*
- Inverter UPS Failed (Yes/No)
- Inverter UPS Testing (Yes/No)
- Inverter UPS Shutdown Flag (Yes/No)
- Inverter UPS Beep Enabled (Yes/No)
- Inverter UPS Line Interactive Mode (Yes/No)
- Inverter UPS AVR Active* 

\* not applicable for PICOGLF12W12V120AL

# The Quest to Automate Equipment Shutdowns

An AIMS power inverter combined with a large marine battery is a great way build your own UPS/battery backup that has significantly more capacity than your average APC, Tripp Lite, or CyberPower retail models to protect your home gear. The only problem is unlike packaged commercial UPS products, there is not an easy way to monitor battery health during a power outage to know when the battery is running low. This is a useful feature of commercial products that safely powers down your equipment before the battery is depleted to avoid major data integrity problems.  

After a long power outage and subsequent sudden power loss upon battery depletion caused problems with my gear, I was determined to find a solution to monitor the status of my custom UPS system so everything could shut down gracefully before the battery was fully depleted. After much googling, I found the RJ45 pin-out and serial protocol for an AIMS power inverter on the [Solar, Wind, and Battery Systems forum](https://secondlifestorage.com/index.php?threads/aims-lf-inverter-rj45-protocol-information.10348/). This was for a different model than I owned, but I figured it was worth exploring. 

## Proof of Concept

I dug up my [USB serial port adapter](https://amzn.to/3oi3RO4) and cut up an old patch cable to wire up the pins according to the spec and magically it worked! I simply typed in `Q1`,hit Enter and the inverter returned:
```
 (111.0 111.0 112.0 000 60.0 13.5 00.0 00001001
 ```  
After reviewing the protocol spec sheet again, I could see everything I needed was there and more in a very specific format I could easily parse programmatically:
```
 (MMM.M NNN.N PPP.P QQQ RR.R S.SS TT.T b7b6b5b4b3b2b1b0<cr>
The meaning of each field is list as followed: 
Start byte : ( 
I/P voltage: MMM.M (M is an integer number ranging from 0 to 9. The unit is Volt) 
I/P fault voltage : NNN.N (N is an integer number ranging from 0 to 9. The unit is Volt) 
O/P voltage : PPP.P (P is an integer number ranging form 0 to 9. The unit is Volt) 
O/P current : QQQ (QQQ is a percentage of maximum current, not an absolute value) 
O/P frequency : RR.R (R is an integer number ranging from 0 to 9. The unit is Hz) 
Battery voltage : SS.S or S.SS 
 S is an integer number ranging from 0 to 9. For on-line units battery voltage/cell is provided 
 in the form S.SS. For standby units actual battery voltage is provided in the form SS.S. UPS 
 type in UPS status will determine which reading was obtained. 
Temperature : TT.T (T is an integer number ranging form 0 to 9. The unit is degree celsius) 
UPS Status : <U> 
 
 <U> is one byte of binary information such as <b7b6b5b4b3b2b1b0>. Where bn is a 
 ASCII character ‘0’ or ‘1’. 
 UPS status : 
  Bit Description 
  7 1 : Utility Fail (Immediate) 
  6 1 : Battery Low 
  5 1 : AVR 0: NORMAL 
  4 1 : UPS Failed 
  3 1 : UPS Type is Line-Interactive (0 is On_line) 
  2 1 : Test in Progress 
  1 1 : Shutdown Active 
  0 1 : Beeper On
``` 
## Time To Build

Now that I knew how to get data out of the AIMS Power inverter via the RJ-45 interface serial port, I decided to build the automated solution using a Raspberry Pi Zero W since it is a cheap device that has a both Wi-Fi which is required to talk to my Home Assistant MQTT server and a hardware UART/serial controller with designated pins that would make talking to the AIMS Power inverter easy using Python.  The only catch I needed to solve for was a voltage problem between the Raspberry Pi operates at 3.3 volts and the inverter serial port operates at 5 volts. Connecting the 5v inverter serial port to the Raspberry Pi directly would fry the pi so a bi-directional multi-channel logic level converter is required between the devices (see required hardware below) so they play nice together. 

# Required Hardware & Software
- Raspberry Pi Zero W or other version of Raspberry PI
- Spare RJ-45 ethernet cord you don't mind destroying to make your custom cable
- At least a two channel 3.3V-5V Logic Level Converter ([Anmbest 4 channel on Amazon](https://amzn.to/45kIo7R) is what I used)
- Soldering Iron 
- Existing Home Assistant install with MQTT configured.  

# Hardware Build Instructions

These instructions will walk you through, at a high level, what is needed to physically connect the Raspberry Pi Zero W to the AIMS Power inverter.  

TODO: draw schematic 

# Software Build & Configuration Instructions

## Configuring the Raspberry Pi

Some prep work is needed to disable bluetooth so the UART controller can be fully utilized on the Raspberry Pi Zero W and potentially other Raspberry Pi models. These instructions will assume you already have a fully configured and updated Raspberry Pi Zero W that you can SSH into.  

1. Run the following commands on your Pi Zero W:
``` 
sudo systemctl disable hciuart.service
sudo systemctl disable bluetooth.service
``` 
2. Edit `/boot/config.txt` and add the following line:
``` 
dtoverlay=disable-bt
``` 
3. Reboot the Pi Zero W. 

When the system is back up, make sure `/dev/serial0` is mapped to `ttyAMA0` by running `ls -l /dev/serial*` as shown below:

``` 
ls -l /dev/serial*
lrwxrwxrwx 1 root root 7 Apr 30 21:03 /dev/serial0 -> ttyAMA0   <--- Good
lrwxrwxrwx 1 root root 5 Apr 30 21:03 /dev/serial1 -> ttyS0
``` 

## Configuring and installing this App

Install python3 pip and git

sudo apt-get install python3-pip git

Clone git repo

install python dependencies via requirements.txt
pip3 install -r requirements.txt



