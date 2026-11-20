import os,time,json,logging
from pathlib import Path
import redis
from sqlalchemy import select
from .db import Session
from .models import Pack,PackLine,Edition,HistoricalBasket
from .common import lock
from .basket_rules import recommend
q=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
while True:
    Path('/tmp/books-heartbeat').touch()
    try:
        item=q.blpop('book-baskets',timeout=2)
        if not item:continue
        with Session()as s:
            p=lock(s,Pack,int(item[1]))
            if p.ml_state!='queued':continue
            p.ml_state='running';s.commit()
            try:
                baskets=list(s.scalars(select(HistoricalBasket.subjects).order_by(HistoricalBasket.id)));subjects=list(s.scalars(select(Edition.subject).join(PackLine,PackLine.edition_id==Edition.id).where(PackLine.pack_id==p.id)));result=recommend(baskets,subjects);p.recommendation=result;p.ml_state='ready';p.error=None;Path(f'/artifacts/basket-{p.id}.json').write_text(json.dumps(result,ensure_ascii=False));s.commit()
            except Exception as ex:p.ml_state='failed';p.error=str(ex)[:450];s.commit();logging.exception('basket failed')
    except Exception:logging.exception('queue unavailable');time.sleep(1)
