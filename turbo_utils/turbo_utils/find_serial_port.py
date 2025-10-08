import serial.tools.list_ports

def find_serial_port(vendor_id, product_id, **kwargs):
    """! Finds the UNIX com port for a given device
    @param vendor_id    The vendor ID for the device
    @param product_id   The product ID for the device
    """
    ports = serial.tools.list_ports.comports()
    if "usb_port" in kwargs.keys():
        # connect to a specific device location
        for port in ports:
            if port.vid == vendor_id and port.pid == product_id and port.location == kwargs["usb_port"]:
                break
        
    else:
        # connect to the first available device
        for port in ports:
            if port.vid == vendor_id and port.pid == product_id:
                break
    
    return port.device

if __name__ == "__main__":
    arduino_vid = 0x2341
    arduino_pid = 0x0043
    arduino_location = "1-1.1:1.0"
    print(find_serial_port(arduino_vid, arduino_pid))