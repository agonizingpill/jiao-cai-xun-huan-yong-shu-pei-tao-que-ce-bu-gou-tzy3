from datetime import date,timedelta
from sqlalchemy import select
from fastapi import HTTPException
from .models import Purchase,ReceiveBatch,PackLine,Pack,Edition
from .common import lock,pack,audit

def promise(s,id,d,u):
    po=lock(s,Purchase,id)
    if po.state!='open':raise HTTPException(409,'补购单已收齐关闭，承诺日不再改期')
    first=po.promised_date is None
    if po.original_promised_date is None:po.original_promised_date=d.promised_date
    po.promised_date=d.promised_date
    audit(s,u,('登记补购承诺日 PO' if first else '补购改期 PO')+str(po.id)+' → '+d.promised_date.isoformat()+'，原承诺保留供历史估计')
    return pack(po)
def _history(s):
    pos=s.scalars(select(Purchase).where(Purchase.state=='received',Purchase.original_promised_date.isnot(None)).order_by(Purchase.id)).all()
    batches={}
    if pos:
        for b in s.scalars(select(ReceiveBatch).where(ReceiveBatch.purchase_id.in_([p.id for p in pos]))):batches.setdefault(b.purchase_id,[]).append(b)
    return [(p,batches[p.id])for p in pos if p.id in batches]
def _estimate(po,hist,today):
    lead=(po.promised_date-today).days;cohort=[]
    for h,bs in hist:
        cutoff=h.original_promised_date-timedelta(days=lead)
        got=sum(b.quantity for b in bs if b.received_on<=cutoff)
        cohort.append((got/h.ordered,max(b.received_on for b in bs)<=h.original_promised_date))
    if lead<0:po.risk_level,po.risk_score,po.risk_samples='high',100,len(cohort)
    elif not cohort:po.risk_level,po.risk_score,po.risk_samples=None,None,0
    else:
        peers=[c for c in cohort if c[0]<=po.received/po.ordered]or cohort
        score=round(sum(1 for _,on in peers if not on)/len(peers)*100)
        po.risk_level,po.risk_score,po.risk_samples=('high' if score>=50 else 'mid' if score>=20 else 'low'),score,len(peers)
    po.risk_received=po.received;po.risk_ordered=po.ordered;po.risk_promised=po.promised_date
def estimate_all(s,u):
    today=date.today();hist=_history(s)
    opens=s.scalars(select(Purchase).where(Purchase.state=='open',Purchase.promised_date.isnot(None)).order_by(Purchase.id).with_for_update()).all()
    for po in opens:_estimate(po,hist,today)
    audit(s,u,'按历史同提前天数实收进度重估补购风险 '+str(len(opens))+' 单');return len(opens)
def chasing(s):
    today=date.today();rows=[]
    for po in s.scalars(select(Purchase).where(Purchase.state=='open').order_by(Purchase.id)):
        line=s.get(PackLine,po.line_id);p=s.get(Pack,line.pack_id);e=s.get(Edition,line.edition_id)
        lead=(po.promised_date-today).days if po.promised_date else None
        stale=bool(po.risk_level and(po.risk_received!=po.received or po.risk_ordered!=po.ordered or po.risk_promised!=po.promised_date))
        rows.append(pack(po)|{'edition_title':e.title,'edition_version':e.version,'pack_code':p.code,'term':p.term,'remaining':po.ordered-po.received,'lead_days':lead,'stale':stale})
    rows.sort(key=lambda r:(2,0,0)if r['promised_date']is None else(1,r['lead_days'],0)if r['risk_score']is None else(0,-r['risk_score'],r['lead_days']))
    return {'today':today.isoformat(),'orders':rows}
