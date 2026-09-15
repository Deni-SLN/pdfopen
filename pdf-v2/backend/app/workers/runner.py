import time
try:
    import redis
    from rq import Queue, Worker
    from ..config import settings
    from ..database import SessionLocal
    redis_conn = redis.from_url(settings.REDIS_URL)
    q = Queue("sofia", connection=redis_conn)
    print("RQ worker starting, redis:", settings.REDIS_URL)
    w = Worker([q], connection=redis_conn)
    w.work()
except Exception as e:
    print("RQ not available, fallback loop:", e)
    import threading
    from .processor import process_job
    from ..database import SessionLocal
    from ..models import Job
    while True:
        db=SessionLocal()
        job=db.query(Job).filter(Job.status=="queued").order_by(Job.created_at).first()
        db.close()
        if job:
            try: process_job(job.id)
            except Exception as ex: print(ex)
        time.sleep(2)
