from apscheduler.schedulers.background import BackgroundScheduler


class SchedulerConfig:
    """Scheduler class..."""

    name = 'scheduler'

    def __init__(self):
        self.jobs = {}
        self.scheduler = BackgroundScheduler(timezone="Europe/Amsterdam")
        self.scheduler.start()

    def add_notifier(self, send_function, channel_id, turn_context, hour, minutes, minutes_left):
        self.scheduler.add_job(send_function, args=[turn_context, minutes_left, channel_id], 
                               trigger='cron', hour=hour, minute=minutes)


main_scheduler = SchedulerConfig()