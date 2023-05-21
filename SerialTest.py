import serial

try:
    serialPort = serial.Serial("/dev/ttyAMA0", baudrate=2400, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=1)
    serialDataText = "Q1\n".encode("ascii")
    print ("Sending:",serialDataText)
    serialPort.write(serialDataText)
    
    serialResponse = serialPort.readline()
    serialResponseRawDecoded=serialResponse.decode("ascii")

    print ("Response:",serialResponseRawDecoded)

    serialPort.close()
except IOError:
    print ("Serial Error")
except UnicodeDecodeError:
    print ("Decoder Error, probably junk reply")

#decode the data further

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
#response="(000.0 110.0 120.0 023 60.0 12.1 00.0 10001011"  #power out bad situation
#response=" (111.0 111.0 112.0 000 60.0 13.5 00.0 00001001"  #good normal situation

response=serialResponseRawDecoded.strip()
response=response[1:]
inverter_params=response.split()

# invertar_params specs:
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

print("Battery Voltage:",battery_voltage)
