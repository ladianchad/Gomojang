from omnitor.devices.arduino import SerialSingleton

def update_serial_data():
  serial = SerialSingleton.instance()
  current_data = serial.get_current_data()
  if current_data :
    ### model update
    pass

def send_command(command: int):
  serial = SerialSingleton.instance()
  serial.command(command)
