import serial
import syslog
import paho.mqtt.client as mqtt
import time
import yaml
import sys

def log(message):
    print(message)
    syslog.syslog(message)  

log("AIMSPowerInverterMQTT by Steve Sinchak")
log("Opening config.yaml file at /opt/AIMSPowerInverterMQTT")
with open('/opt/AIMSPowerInverterMQTT/config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    log("Config file loaded!")

mqttHost=config["mqttHost"]
mqttPort=int(config["mqttPort"])
mqttUser=config["mqttUser"]
mqttPass=config["mqttPass"]

baseTopic=config["baseTopic"]
modelTopic=config["modelTopic"]
expireAfter=str(config["expireAfter"])
deviceDetailsJSON=str(config["deviceDetailsJSON"])

try:
    #Baudrate must be set to 2400 according to AIMS power specifications!
    log("Attempting to communicate with local serial port controller")
    serialPort = serial.Serial(config["serialPort"], baudrate=2400, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=1)
    serialDataText = "Q1\n".encode("ascii")
    log("Sending Serial Command to Inverter:"+str(serialDataText))
    serialPort.write(serialDataText)
    
    serialResponse = serialPort.readline()
    serialResponseRawDecoded=serialResponse.decode("ascii")

    log("Inverter Serial Response:"+str(serialResponseRawDecoded))

    serialPort.close()

    #Inverter Response Specification 
    # (MMM.M NNN.N PPP.P QQQ RR.R S.SS TT.T b7b6b5b4b3b2b1b0<cr>
    # The meaning of each field is list as followed: 
    # Start byte : ( 
    # I/P voltage: MMM.M (M is an integer number ranging from 0 to 9. The unit is Volt) 
    # I/P fault voltage : NNN.N (N is an integer number ranging from 0 to 9. The unit is Volt) 
    # O/P voltage : PPP.P (P is an integer number ranging form 0 to 9. The unit is Volt) 
    # O/P current : QQQ (QQQ is a percentage of maximum current, not an absolute value) 
    # O/P frequency : RR.R (R is an integer number ranging from 0 to 9. The unit is Hz) 
    # Battery voltage : SS.S or S.SS 
    #  S is an integer number ranging from 0 to 9. For on-line units battery voltage/cell is provided 
    #  in the form S.SS. For standby units actual battery voltage is provided in the form SS.S. UPS 
    #  type in UPS status will determine which reading was obtained. 
    # Temperature : TT.T (T is an integer number ranging form 0 to 9. The unit is degree celsius) 
    # UPS Status : <U> 
    #  
    #  <U> is one byte of binary information such as <b7b6b5b4b3b2b1b0>. Where bn is a 
    #  ASCII character ‘0’ or ‘1’. 
    #  UPS status : 
    #   Bit Description 
    #   7 1 : Utility Fail (Immediate) 
    #   6 1 : Battery Low 
    #   5 1 : AVR 0: NORMAL 
    #   4 1 : UPS Failed 
    #   3 1 : UPS Type is Line-Interactive (0 is On_line) 
    #   2 1 : Test in Progress 
    #   1 1 : Shutdown Active 
    #   0 1 : Beeper On 
    # Stop Byte : <cr> 

    # Reference Responses 
    #response=" (000.0 110.0 120.0 023 60.0 12.1 00.0 10001011"  #power out bad situation
    #response=" (111.0 111.0 112.0 000 60.0 13.5 00.0 00001001"  #good normal situation
    
    log("Processing Inverter Response")
    response=serialResponseRawDecoded.strip()
    response=response[1:]
    inverter_params=response.split()

    # inverter_params specs:
    # 0: Line Input Voltage
    # 1: Line Input Voltage Fault
    # 2: Inverter Output Voltage
    # 3: Inverter Output Max Current Percentage / UPS Load Percentage
    # 4: Inverter Output Frequency (Hz)
    # 5: Battery Voltage
    # 6: Temperature (c)
    # 7: UPS Status Bits (must be decoded further)

    line_voltage=inverter_params[0]
    line_voltage_fault=inverter_params[1]
    inverter_output_voltage=inverter_params[2]
    inverter_output_max_current_percentage=inverter_params[3] #aka load percentage
    inverter_output_frequency=inverter_params[4]
    battery_voltage=inverter_params[5]
    temperature=inverter_params[6]
    ups_status=list(inverter_params[7])

    # ups_status specs:
    # 0: 1 : Utility Fail (Immediate) 
    # 1: 1 : Battery Low 
    # 2: 1 : AVR 0: NORMAL 
    # 3: 1 : UPS Failed 
    # 4: 1 : UPS Type is Line-Interactive (0 is On_line) 
    # 5: 1 : Test in Progress 
    # 6: 1 : Shutdown Active 
    # 7: 1 : Beeper On 

    ups_status_utility_fail=bool(int(ups_status[0]))
    ups_status_battery_low=bool(int(ups_status[1]))
    ups_status_avr_active=bool(int(ups_status[2]))
    ups_status_ups_failed=bool(int(ups_status[3]))
    ups_status_ups_type_line_interactive=bool(int(ups_status[4]))
    ups_status_testing=bool(int(ups_status[5]))
    ups_status_shutdown=bool(int(ups_status[6]))
    ups_status_beep_enabled=bool(int(ups_status[7]))

    log("Sending Inverter Data to Home Assistant over MQTT")

    client = mqtt.Client()
    client.username_pw_set(username=mqttUser,password=mqttPass)
    log("Connecting to MQTT Server")
    client.connect(mqttHost, mqttPort, 60)
    client.loop_start()
    time.sleep(1)
    client.loop_stop()
    log("Connected")

    def mqttStateValuePub(client, base, model, name, value):
        stateTopic=base.lower().replace(" ", "")+"/"+model.lower().replace(" ", "")+"/"+name.lower().replace(" ", "")

        # if value is boolean, convert to on/off for Home Assistant
        # ON / OFF is case sensitive in HA!
        if type(value)==bool:
            if value:
                value="ON"
            else:
                value="OFF"

        log("Sending '"+str(value)+"' to "+ stateTopic)
        ret=client.publish(stateTopic,value,qos=0,retain=False)
        log("Result:"+str(ret))

    def mqttHAAutodiscoveryPub(client, base, model, name, HAComponentType, deviceClass, unitOfMeasure, stateClass, expireAfter, deviceDetailsJSON):
        topic="homeassistant/"+HAComponentType+"/"+model.lower().replace(" ", "")+"/"+name.lower().replace(" ", "")+"/config"
        uniqueID=name.lower().replace(" ", "_")+"_"+model.lower().replace(" ", "_")+"_"+baseTopic.lower().replace(" ", "_")
        stateTopic=base.lower().replace(" ", "")+"/"+model.lower().replace(" ", "")+"/"+name.lower().replace(" ", "")
        
        message='{"unique_id": "'+uniqueID+'", "name": "'+name+'", '
        if deviceClass is not None: message=message+'"device_class": "'+deviceClass+'", '
        if unitOfMeasure is not None: message=message+'"unit_of_measurement": "'+unitOfMeasure+'", '
        if stateClass is not None: message=message+'"state_class": "'+stateClass+'", '
        message=message+'"expire_after": '+expireAfter+', "state_topic": "'+stateTopic+'", "device": '+deviceDetailsJSON+'}'
        
        log("Sending '"+message+"' to "+ topic)
        ret=client.publish(topic,message,qos=0,retain=True)
        log("Result:"+str(ret))

    #Line Voltage
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Utility Line Voltage","sensor","voltage","V","measurement",expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Utility Line Voltage",line_voltage)

    #Line Voltage Fault Level
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Utility Line Voltage Fault","sensor","voltage","V","measurement",expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Utility Line Voltage Fault",line_voltage_fault)

    #Inverter Output Voltage
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter Output Voltage","sensor","voltage","V","measurement",expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter Output Voltage",inverter_output_voltage)

    #Battery Voltage
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Battery Voltage","sensor","voltage","V","measurement",expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Battery Voltage",battery_voltage)

    #Inverter Load Percentage
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter Load Percentage","sensor","power_factor","%","measurement",expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter Load Percentage",int(inverter_output_max_current_percentage))

    #Inverter Output Frequency
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter Output Frequency","sensor","frequency","Hz","measurement",expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter Output Frequency",float(inverter_output_frequency))

    #Temperature
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter Temperature","sensor","temperature","°C","measurement",expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter Temperature",float(temperature))

    #Decoded Binary Utility Line Power
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Utility Line Power","binary_sensor","power",None,None,expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Utility Line Power",not ups_status_utility_fail)

    #Decoded Binary Battery Low
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Battery Status","binary_sensor","battery",None,None,expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Battery Status",ups_status_battery_low)

    #Decoded Binary AVR Active
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter AVR Active","binary_sensor",None,None,None,expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter AVR Active",ups_status_avr_active)

    #Decoded Binary UPS Failed
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter UPS Failed","binary_sensor",None,None,None,expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter UPS Failed",ups_status_ups_failed)

    #Decoded Binary UPS Line Interactive Type
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter UPS Line Interactive","binary_sensor",None,None,None,expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter UPS Line Interactive",ups_status_ups_type_line_interactive)

    #Decoded Binary Testing
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter UPS Testing","binary_sensor",None,None,None,expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter UPS Testing",ups_status_testing)

    #Decoded Binary Shutdown Trigger (although provides little value as it turns on immediatly upon utility line power loss)
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter UPS Shutdown Trigger","binary_sensor",None,None,None,expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter UPS Shutdown Trigger",ups_status_shutdown)

    #Decoded Binary Beep Enabled
    mqttHAAutodiscoveryPub(client,baseTopic,modelTopic,"Inverter UPS Beep Enabled","binary_sensor",None,None,None,expireAfter,deviceDetailsJSON)
    mqttStateValuePub(client,baseTopic,modelTopic,"Inverter UPS Beep Enabled",ups_status_beep_enabled)

    #clean up
    log("Disconnecting...")
    client.disconnect()
    log("All Done!")

except IOError:
    log("Exception Occurred: Serial Error")
except UnicodeDecodeError:
    log("Exception Occurred: Serial response decoder error (probably junk reply from inverter)")
except Exception as error:
    exception_type, exception_obj, exception_traceback = sys.exc_info()
    log("Exception Occurred: "+ str(error))
    log("Type:"+str(exception_type))
    log("File:"+str(exception_traceback.tb_frame.f_code.co_filename))
    log("Line:"+str(exception_traceback.tb_lineno))