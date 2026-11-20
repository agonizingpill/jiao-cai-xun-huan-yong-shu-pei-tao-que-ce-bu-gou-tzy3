from sqlalchemy import select,func
from fastapi import HTTPException
from .models import Edition,Classroom,Pack,PackLine,Copy,Assignment,Purchase
from .common import inventory_lock,compatible,lock,add,pack,audit

def create(s,d,u):
    room=s.get(Classroom,d.classroom_id)
    if not room:raise HTTPException(404,'班级不存在')
    subjects=[]
    for line in d.lines:
        if not s.get(Edition,line.edition_id):raise HTTPException(404,'课程版次不存在')
        subjects.append(s.get(Edition,line.edition_id).subject)
        if line.quantity>room.size:raise HTTPException(409,'课程份数不能超过班级人数')
    if len(set(subjects))!=len(subjects):raise HTTPException(409,'同一课程不能用多个版次重复列入配套')
    x=Pack(code=d.code,classroom_id=d.classroom_id,term=d.term);s.add(x);s.flush()
    for line in d.lines:s.add(PackLine(pack_id=x.id,**line.model_dump()))
    s.flush();audit(s,u,'建立班级课程配套 '+d.code);return pack(x)
def reserve(s,id,u):
    inventory_lock(s);p=lock(s,Pack,id)
    if p.state in ('allocated','cancelled'):raise HTTPException(409,'完整配套不可重复领用，取消配套不可续办')
    missing=[];reserved=[]
    for line in s.scalars(select(PackLine).where(PackLine.pack_id==id).order_by(PackLine.id)):
        assigned=s.scalar(select(func.count()).select_from(Assignment).where(Assignment.line_id==line.id,Assignment.replacement_for_id.is_(None)))
        needed=max(0,line.quantity-assigned)
        copies=s.scalars(select(Copy).where(Copy.edition_id.in_(compatible(s,line.edition_id)),Copy.condition=='usable',Copy.state=='available').order_by(Copy.id).limit(needed).with_for_update()).all()if needed else[]
        for copy in copies:
            copy.state='reserved';a=Assignment(line_id=line.id,copy_id=copy.id,deposit_cents=s.get(Edition,line.edition_id).deposit_cents);s.add(a);s.flush();reserved.append(a.id)
        shortage=needed-len(copies)
        if shortage:
            po=s.scalar(select(Purchase).where(Purchase.line_id==line.id))
            if po:po.ordered=max(po.ordered,po.received+shortage);po.state='open'if po.received<po.ordered else'received'
            else:s.add(Purchase(line_id=line.id,ordered=shortage))
            missing.append({'line_id':line.id,'quantity':shortage})
    p.state='partial'if missing else'allocated';audit(s,u,'锁定可用单本并登记缺册 '+p.code);return pack(p)|{'new_assignment_ids':reserved,'shortages':missing}
def receive(s,id,d,u):
    inventory_lock(s);po=lock(s,Purchase,id);line=s.get(PackLine,po.line_id);p=lock(s,Pack,line.pack_id)
    if p.state=='cancelled' or po.state!='open' or d.quantity>po.ordered-po.received:raise HTTPException(409,'补购数量超过未收缺册或订单已关闭')
    for n in range(d.quantity):s.add(Copy(barcode=d.barcode_prefix+'-'+str(po.received+n+1),edition_id=line.edition_id,condition='usable',state='available',source='缺册补购PO'+str(po.id)))
    po.received+=d.quantity
    if po.received==po.ordered:po.state='received'
    s.flush();audit(s,u,'补购到货验收 '+str(po.id));return pack(po)
