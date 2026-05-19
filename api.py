#more info about the pump here: https://usermanual.wiki/Document/TecanCavroXCALIBURManual.265580342.pdf

from click import command
import serial #pip install pyserial !!!!!!!!!!!!!!!!!!!!!! not serial
import time

class Hub:
    pumps = []
    
    def __init__(self, com_port, baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=1):
        # baudrate can be either 9600 38400
        
        try:
            self.serial = serial.Serial(port=com_port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=timeout)
            print(f'Serial communication initialized!')
        except serial.SerialException as e:
            print(f"Error initializing serial connection: {e}")

    def close(self):
        self.serial.close()
        
    #to be checked
    #the address is refered in manual as 5F in hex and converted to -(minus), instead of _ which is correct ASCII conversion
    def send_command_all(self, command, execute=True):
        comm = f"/_{command}{"R" if execute else ""}\r"
        self.serial.write(comm)

        response = self.parse_response(self.read_response())
    
        #get status and error codes
        bits = bin(ord(response[1]))
        error_code = int(bits, 2) & 0b1111
        status = (int(bits, 2) >> 4) & 1

        return status, error_code, response[2]#data payload
        
    def read_response(self):
        try:
            response = self.serial.readall()
            #print(response)
            #print(response.decode()[0:-2])
            return response#.decode()#[0:-2]
        except serial.SerialException as e:
            print(f"Error reading from serial connection: {e}")
            return None
    
    def parse_response(self, raw_response):
            response_str = raw_response.decode('ascii', errors='ignore')
            #print(f"Decoded response: {response_str}")
 
                
            # Clean up standard formatting whitespace/newlines
            response_str = response_str.strip()
            
            # Check for minimal valid structural length (/0 + Status character)
            if not response_str.startswith('/') or len(response_str) < 3:
                return None

            # Strip out the ETX (0x03) character if it exists in the string
            response_str = response_str.replace('\x03', '')

            # Assign directly to variables based on string positions
            pump_address = response_str[1]       # Typically '0'
            status_character = response_str[2]   # Raw status byte character
            
            # Extract the data portion (ignoring a final trailing checksum byte if present)
            data_payload = response_str[3:].rstrip() 
            
            return pump_address, status_character, data_payload

    #not implemented
    # def send_command_two_pumps():
    # def send send_command_four_pumps():
        
        
    
    class Pump:
        
        #NOTES:
        #backlash compensation not implemented yet
        #pump configuration saving in non-volataile memory not implemented yet
        #handling of valve not implemented yet
        #syringe dead volume not implemented yet
        # non volataile EEPROM memory commands (computer free operation) not implemented yet
        

        #constants
        dict_addresses = {0:1, 1:2, 2:3, 3:4, 4:5, 5:6, 6:7, 7:8, 8:9, 9:":", "A":";", "B":"<", "C":"=", "D":">", "E":"?"}

        #syringe_volume = 0 # in microliters uL
        pump_id = 0
        start_speed = 900
        speed_slope = 14
        speed_top = 1400
        speed_cutoff = 900
        position = 0 #???
        high_precision = False # False = 3000 steps, True = 24000 steps for whole range
        #backlash_compensation = 0 # in steps
        
        def __init__(self, hub, pump_address, syringe_volume, high_precision=False ):#, backlash_compensation=0):
            #pump_address number on the address switch 0...E (0...15)
            #syringe volume in microliters uL

            if syringe_volume == 0:
                raise ValueError(f'[ERROR]: Syringe {pump_address} volume must be specified')
            else:
                self.syringe_volume = syringe_volume
            
            if pump_address is None:
                raise ValueError(f'[ERROR]: Pump address must be specified')
            else:
                self.pump_id = self.dict_addresses[pump_address]
            
            self.high_precision = high_precision
            
            
            #build the inicialization command sequence
            #we are using CW Clokcwise direction
            command = "Z"
            
            #initzialization forces setup
            if self.syringe_volume >= 1000: #if syringe volume over 1000 uL, set full force
                command+="0"
            elif self.syringe_volume == 250 or self.syringe_volume == 500: #if syringe volume is 250 or 500 uL, set half force
                command+="1"
            elif self.syringe_volume == 50 or self.syringe_volume == 100: #if syringe volume is 50 or 100 uL, set third force
                command+="2"
            
            self.hub = hub
            self.serial = hub.serial

            self.send_command(command) # init the pump
            
            if self.high_precision:
                self.send_command("N1") # set high precision mode
            
            # if backlash_compensation != 0:
            #     if high_precision:
            #         if backlash_compensation > 0 and backlash_compensation <=248:
            #             self.send_command(f"K{backlash_compensation}") # set backlash compensation in steps
            #         else:
            #             raise ValueError(f'[ERROR]: Backlash compensation must be between 0 and 248 steps in high precision mode')
            #     else:
            #         if backlash_compensation > 0 and backlash_compensation <= 31:
            #             self.send_command(f"K{backlash_compensation}") # set backlash compensation in steps
            #         else:
            #             raise ValueError(f'[ERROR]: Backlash compensation must be between 0 and 31 steps in normal mode')


        ########################################
        # LOW LEVEL COMMANDS
        ########################################
        
        #send a command to a single pump
        def send_command(self, command, execute=True):
            comm = f'/{self.pump_id}{command}{"R" if execute else ""}\r'
            self.serial.write(comm.encode('ascii'))

            response = self.hub.parse_response(self.hub.read_response())
            print(f"Sent command: {comm.strip()} | Received response: {response} | Status/Error: {self.convert_to_status_error(response[1]) if response else 'No response'}")

            return self.convert_to_status_error(response[1]), response[2]
        
        def calculate_steps(self, volume):
            # volume in microliters
            return int(int(3000 if not self.high_precision else 24000) * volume / self.syringe_volume)
        
        def convert_to_status_error(self, status_character):
            #convert resopnse byte to bits
            # 7 6 5 4 3 2 1 0
            # 0 1 X 0 Y Y Y Y
            
            # X - bit 5 is status bit 1-pump is idle and ready for new commands, 0- pump is executing a command
            # 1-go on, GOOD
            #0 - still working, WAIT
            
            # Y - 4 least significant bits are error bits
            bits = bin(ord(str(status_character)))
            error_code = int(bits, 2) & 0b1111
            status = (int(bits, 2) >> 5) & 1
            return status, error_code
        
        ########################################
        # HIGH LEVEL COMMANDS
        ########################################
        
        #### MOVE COMMANDS
        def go_to_position(self, position, steps=False):
            # steps = False => position in microliters
            # steps = True => position in steps
            command = f'A{position if steps else self.calculate_steps(position)}'
            self.send_command(command)
        
        def pick_up(self, volume, steps=False):
            # steps = False => pick up volume in microliters
            # steps = True => pick up volume in steps
            command = f'P{volume if steps else self.calculate_steps(volume)}'
            self.send_command(command)
        
        def dispense(self, volume, steps=False):
            # steps = False => dispense volume in microliters
            # steps = True => dispense volume in steps
            command = f'D{volume if steps else self.calculate_steps(volume)}'
            self.send_command(command)
        
        #### SPEED AND ACCELERATION COMMANDS
        def set_start_speed(self, speed=900):
            # speed 50...1000
            if speed < 50 or speed > 1000:
                raise ValueError(f'[ERROR]: Start speed must be between 50 and 1000 steps')
            self.start_speed = int(speed)
            self.send_command(f'v{int(speed)}')
        
        def set_speed_slope(self, slope=14):
            # slope 1...20
            #describes acceleration and deceleration of the pump
            if slope < 1 or slope > 20:
                raise ValueError(f'[ERROR]: Slope must be between 1 and 20')
            self.speed_slope = int(slope)
            self.send_command(f'L{int(slope)}')

        def set_speed_top(self, speed=1400):
            # speed 5...6000
            if speed < 5 or speed > 6000:
                raise ValueError(f'[ERROR]: Top speed must be between 5 and 6000 steps')
            self.speed_top = int(speed)
            self.send_command(f'V{int(speed)}')
        
        def set_cutoff_speed(self, speed=900):
            # speed 50...2700
            if speed < 50 or speed > 2700:
                raise ValueError(f'[ERROR]: Cutoff speed must be between 50 and 2700 steps')
            self.speed_cutoff = int(speed)
            self.send_command(f'c{int(speed)}')
            
        def set_constant_speed(self, speed=1400):
            # speed 5...6000
            if speed < 5 or speed > 6000:
                raise ValueError(f'[ERROR]: Constant speed must be between 5 and 6000 steps')
            self.speed_top = int(speed)
            self.start_speed = int(speed)
            self.speed_cutoff = int(speed)
            self.send_command(f'v{int(speed)}V{int(speed)}c{int(speed)}')
            

        #### CONTROL COMMANDS
        def execute_command(self):
            #used to run command that was send with flag execute=False
            #or to resumpt a command that was paused with the Terminate of Halt command
            self.send_command("R")
        
        def terminate_command(self):
            #used to pause a command that is running, can be resumed with execute_command
            #do not terminate valve controls
            self.send_command("T")
            self.send_command("Z") # reinitialize, as suggested in manual
        
        def halt_command(self, setting=0):
            # used to stop a command that is running
            # comman can be resumed
            # setting:
            # 0: resume when either input 1 (J4 in 7) or input 2 (J4 in 8) is pulled low
            # 1: resume when input 1 is pulled low
            # 2: resume when input 2 is pulled low
            self.send_command(f"H{int(setting)}")
        
        def execute_last_command_again(self):
             self.send_command("X")
        
        def repeat_command(self, command, times):
            # times 0...30000
            # times = 0 => repeat indefinitely until Terminate command is sent
            if times < 0 or times > 30000:
                raise ValueError(f'[ERROR]: Repeat times must be between 0 and 30000')
            self.send_command(f'{command}G{int(times)}')

        def delay_execution(self, delay):
            # delay in milliseconds, multiple of 5
            if delay < 0 or delay > 30000:
                raise ValueError(f'[ERROR]: Delay must be between 0 and 30000 milliseconds')
            self.send_command(f'M{round(delay / 5) * 5}')
           
        def set_auxilary_output(self, pin1 = 0, pin2 = 0, pin3 = 0):
            # used to control the auxilary output pins (J4 in 13,14,15)
            # 1 - high- for example +5V DC
            # 0 - low - for example GND
            if pin1 not in [0,1] or pin2 not in [0,1] or pin3 not in [0,1]:
                raise ValueError(f'[ERROR]: Pin values must be either 0 or 1')
            dict = {[0,0,0]:0, [0,0,1]:1, [0,1,0]:2, [0,1,1]:3, [1,0,0]:4, [1,0,1]:5, [1,1,0]:6, [1,1,1]:7}
            setting = dict.get([pin1, pin2, pin3], 0)
            self.send_command(f'J{setting}')
        
        #### REPORT COMMANDS
        def get_absolute_position(self):
            # returns absolute position in steps
            self.send_command("?P", execute=False)
            
            response = self.parse_response(self.read_response())
            return int(response[2]) if response else None
        
        def get_actual_position(self):
            # returns actual position in steps
            self.send_command("?4", execute=False)
            
            response = self.parse_response(self.read_response())
            return int(response[2]) if response else None
        
        def command_buffer_status(self):
            #returns if there is a command in the buffer
            # response = 1 => there is command in the buffer, response = 0 => there is no command in the buffer
            self.send_command("?10", execute=False)
            
            response = self.parse_response(self.read_response())
            return int(response[2]) if response else None
            
            #inf response = 1 => there is command in the buffer, response = 0 => there is no command in the buffer
            
        def auxilary_input_status(self, pin=1):
            # returns status of auxilary input pins (J4 in 7,8)
            self.send_command(("?13" if pin == 1 else "?14"), execute=False)
            
            response = self.parse_response(self.read_response())
            return int(response[2]) if response else None
            
            #response = 0 => pin is low, response = 1 => pin is high
        
        def pump_configuration(self):
            # returns pump configuration
            self.send_command("?76", execute=False)
            
            response = self.parse_response(self.read_response())
            return int(response[2]) if response else None
        
        def get_status_errors(self):
            # returns status of the pump and errors
            response = self.send_command("Q", execute=False)
            
            
            
            
            dict_errors = {0:"No Error", 1:"Initialization Error", 2:"Invalid Command", 3:"Invalid Operand", 4:"Invalid Command Sequence", 6:"EEPROM Failure", 7:"Device Not Initialized", 9:"Plunger Overload", 10:"Valve Overload", 11:"Plunger Move Not Allowed", 15:"Command Overflow"}
            # more info about errors in the manual page 81
            
            
            return response[0]
            #return {"status": "Executing" if response and int(response[2]) & 32 else "Idle", "error": dict_errors.get(int(response[2]) & 15)}
            
            
        
# class Test:
#     hub = Hub(port="COM3")
    
#     hub.pumps.append(hub.Pump(pump_address=0, syringe_volume=1000))
#     pumps = hub.pumps
    
#     #TEST 1 - test calculate steps function
#     if pumps[0].calculate_steps(1000) == 300:
#         print("[TEST 1]Test passed")
#     else:
#         print("[TEST 1]Test failed")


if __name__ == "__main__":
    hub = Hub(com_port="COM3")#, baudrate=38400)
    
    hub.pumps.append(hub.Pump(hub=hub, pump_address=0, syringe_volume=1000))
    pumps = hub.pumps
    
    pumps[0].get_status_errors()
    
    #time.sleep(8)
    #pumps[0].send_command("V1400A3000A0V400A3000A0V2700A3000A0")
    #print(pumps[0].get_status_errors())

    time.sleep(2)
    # on purpose cause error 2 - invalid command
    pumps[0].send_command("A566.0")
    pumps[0].get_status_errors()

    time.sleep(2)
    # on purpose cause error 2 - invalid command
    pumps[0].send_command("A566A0")
    #pumps[0].get_status_errors()
    for i in range(10):
        time.sleep(.5)
        pumps[0].get_status_errors()


    hub.serial.close()