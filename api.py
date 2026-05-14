import serial #pip install pyserial !!!!!!!!!!!!!!!!!!!!!! not serial
import time

#communications
class SerialComm:
    def __init__(self, port, baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=1):
        self.ser = serial.Serial(port=port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=timeout)
        return self.ser

    def decompose_reply(reply):
        print(f"Decomposing reply: {reply}")
        address = int(reply[1:2].decode())
        status = str(chr(reply[2]))
        data = str(reply[3:].decode(errors="ignore"))[:-3]
        return address, status, data

    def send_command(self, command):
        #print(f"Sending command: {command}")
        self.ser.write(command)
        time.sleep(0.5) # wait for the response
        reply = self.ser.read_all()
        return self.decompose_reply(reply)
        #print(f"Received reply: {decompose_reply(reply)}")

    def close(self):
        self.ser.close()


#pump control
class Pump:
    def __init__(self, com_port, pump_id, baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=1):
        # baudrate can be either 9600 38400
        #pump_id number on the address selector 0...E (0...15)

        dict_ids = {0:1, 1:2, 2:3, 3:4, 4:5, 5:6, 6:7, 7:8, 8:9, 9:":", "A":";", "B":"<", "C":"=", "D":">", "E":"?"}
        self.pump_id = dict_ids[pump_id]

        try:
            self.serial = serial.Serial(port=com_port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=timeout)
        except serial.SerialException as e:
            print(f"Error initializing serial connection: {e}")

        send_command = f"ZR"
        self.serial.send_command(send_command)

    def close(self):
        self.serial.close()

    def send_command(self, command, execute=True):
        comm = f"/{self.pump_id}{command}{"R" if execute else ""}\r"
        self.serial.write(comm)




if __name__ == "__main__":
    com = SerialComm(port="COM3")


    pump = Pump(pump_id=1)
    pump.dispense(100)


    com.close()