import schedule

def add_shedule(id: str, second: float, job):
  schedule.every(second).seconds.do(job).tag(id)

def update_schedule(id: str, second: float, job):
  schedule.clear(id)
  schedule.every(second).seconds.do(job).tag(id)
