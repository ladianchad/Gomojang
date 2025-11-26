from .arduino import send_command
# from .camera import 
from .schedule import update_schedule

def image_logging():
  send_command(1)
  ## save camera image service
  send_command(2)
  ## save
  ...


def set_image_logging():
  ## get config
  update_schedule('image_logging', config.second, image_logging)

def update_iamge_logging():
  ### update config
  set_image_logging()