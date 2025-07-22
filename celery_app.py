from celery import Celery

def make_celery(app=None):
  celery = Celery(
    app.import_name if app else __name__,
    backend=app.config['CELERY_RESULT_BACKEND'] if app else None,
    broker=app.config['CELERY_BROKER_URL'] if app else None)
  if app:
    celery.conf.update(app.config)
    task_base = celery.Task
    class ContextTask(task_base):
      def __call__(self, *args, **kwargs):
        with app.app_context():
          return task_base.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
  return celery