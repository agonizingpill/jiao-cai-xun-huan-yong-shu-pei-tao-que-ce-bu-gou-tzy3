from datetime import date
from sqlalchemy import select,func,text
import numpy as np
from .db import Base,engine,Session
from .models import *
from .auth import hashed

def seed():
    Base.metadata.create_all(engine)
    if engine.dialect.name=='mysql':
        with engine.begin()as c:
            cols={r[1]for r in c.execute(text('SHOW COLUMNS FROM purchases'))}
            for name,ddl in{'promised_date':'DATE','original_promised_date':'DATE','risk_level':'VARCHAR(10)','risk_score':'INT','risk_samples':'INT','risk_received':'INT','risk_ordered':'INT','risk_promised':'DATE'}.items():
                if name not in cols:c.execute(text('ALTER TABLE purchases ADD COLUMN '+name+' '+ddl))
    with Session()as s:
        for role in ('operator','supervisor','viewer'):
            if not s.scalar(select(User.id).where(User.email==role+'@xunshu.demo')):s.add(User(email=role+'@xunshu.demo',password_hash=hashed('Books2026!'),role=role))
        editions={}
        for code,title,subject,version in [('PHY-V2','高中物理·必修一','physics','V2-2026'),('PHY-V1','高中物理·必修一','physics','V1-2024'),('LAB-V2','物理实验册','lab','V2-2026'),('LAB-V1','物理实验册','lab','V1-2022'),('MATH-V2','数学·必修一','math','V2-2026')]:
            e=s.scalar(select(Edition).where(Edition.code==code))
            if not e:e=Edition(code=code,title=title,subject=subject,version=version,deposit_cents=2000);s.add(e);s.flush()
            editions[code]=e
        for target,allowed,state,reason in [('PHY-V2','PHY-V1','approved','教师逐页核验，章节页码与练习相同'),('LAB-V2','LAB-V1','pending','旧版缺少传感器实验，须教师复核')]:
            if not s.scalar(select(Compatibility.id).where(Compatibility.target_id==editions[target].id,Compatibility.allowed_id==editions[allowed].id)):s.add(Compatibility(target_id=editions[target].id,allowed_id=editions[allowed].id,state=state,reason=reason))
        rooms={}
        for i in range(1,13):
            code='G1-'+str(i);room=s.scalar(select(Classroom).where(Classroom.code==code))
            if not room:room=Classroom(code=code,name='高一'+str(i)+'班',size=12);s.add(room);s.flush()
            rooms[code]=room
        for i in range(1,7):
            code='S'+str(30+i);student=s.scalar(select(Student).where(Student.code==code))
            if not student:student=Student(code=code,name='同学'+str(i),classroom_id=rooms['G1-3'].id);s.add(student);s.flush()
            if not s.scalar(select(Account.id).where(Account.student_id==student.id,Account.term=='2026秋')):s.add(Account(student_id=student.id,term='2026秋',balance_cents=0))
        for code,num in [('PHY-V2',8),('PHY-V1',10),('LAB-V2',6),('LAB-V1',4)]:
            for i in range(1,num+1):
                barcode=code+'-'+str(i).zfill(3)
                if not s.scalar(select(Copy.id).where(Copy.barcode==barcode)):s.add(Copy(barcode=barcode,edition_id=editions[code].id,condition='usable',state='available',source='2026秋回收验收'))
        for i in range(1,5):
            barcode='PHY-REPAIR-'+str(i)
            if not s.scalar(select(Copy.id).where(Copy.barcode==barcode)):s.add(Copy(barcode=barcode,edition_id=editions['PHY-V1'].id,condition='repair',state='repair',source='封面破损待修复'))
        rng=np.random.default_rng(38);patterns=[['math','physics','lab'],['language','history'],['math','computing'],['art','music']]
        for i in range(96):
            code='HIST-'+str(i+1).zfill(3);subjects=patterns[int(rng.choice(4,p=[.4,.3,.2,.1]))]
            if not s.scalar(select(HistoricalBasket.id).where(HistoricalBasket.code==code)):s.add(HistoricalBasket(code=code,subjects=subjects))
        for code,ecode,ordered,promised,original,batches in[
            ('HIST-PO-1','MATH-V2',6,date(2026,3,20),date(2026,3,20),[(date(2026,3,15),4),(date(2026,3,19),2)]),
            ('HIST-PO-2','PHY-V2',8,date(2026,3,25),date(2026,3,25),[(date(2026,3,20),2),(date(2026,3,28),6)]),
            ('HIST-PO-3','LAB-V2',5,date(2026,4,10),date(2026,4,5),[(date(2026,4,6),3),(date(2026,4,9),2)]),
            ('HIST-PO-4','MATH-V2',10,date(2026,4,20),date(2026,4,20),[(date(2026,4,10),5),(date(2026,4,18),5)]),
            ('HIST-PO-5','PHY-V1',4,date(2026,5,10),date(2026,5,10),[(date(2026,5,8),2),(date(2026,5,10),2)]),
            ('HIST-PO-6','LAB-V2',6,date(2026,5,20),date(2026,5,15),[(date(2026,5,14),6)]),
            ('HIST-PO-7','PHY-V2',5,date(2026,6,1),date(2026,6,1),[(date(2026,5,28),2),(date(2026,5,31),3)]),
            ('HIST-PO-8','MATH-V2',8,date(2026,6,10),date(2026,6,10),[(date(2026,6,1),6),(date(2026,6,8),2)]),
            ('HIST-PO-9','MATH-V2',6,date(2026,6,20),date(2026,6,20),[(date(2026,6,12),3),(date(2026,6,18),3)]),
            ('HIST-PO-10','PHY-V2',4,date(2026,6,25),date(2026,6,25),[(date(2026,6,20),4)]),
            ('HIST-PO-11','LAB-V2',8,date(2026,7,1),date(2026,7,1),[(date(2026,6,25),4),(date(2026,6,30),4)]),
            ('HIST-PO-12','MATH-V2',5,date(2026,7,5),date(2026,7,5),[(date(2026,6,30),2),(date(2026,7,3),3)])]:
            if s.scalar(select(Pack.id).where(Pack.code==code)):continue
            p=Pack(code=code,classroom_id=rooms['G1-1'].id,term='2026春',state='allocated');s.add(p);s.flush()
            line=PackLine(pack_id=p.id,edition_id=editions[ecode].id,quantity=ordered);s.add(line);s.flush()
            po=Purchase(line_id=line.id,ordered=ordered,received=ordered,state='received',promised_date=promised,original_promised_date=original);s.add(po);s.flush()
            for j,(on,qty)in enumerate(batches):s.add(ReceiveBatch(purchase_id=po.id,batch_key='SEED-'+code+'-'+str(j),quantity=qty,barcode_prefix=code+'-B'+str(j),received_on=on))
        if not s.scalar(select(Pack.id).where(Pack.code=='PACK-2026-G15')):
            p=Pack(code='PACK-2026-G15',classroom_id=rooms['G1-5'].id,term='2026秋',state='partial');s.add(p);s.flush()
            line=PackLine(pack_id=p.id,edition_id=editions['MATH-V2'].id,quantity=12);s.add(line);s.flush()
            po=Purchase(line_id=line.id,ordered=5,received=2,state='open');s.add(po);s.flush()
            s.add(ReceiveBatch(purchase_id=po.id,batch_key='SEED-G15-0',quantity=2,barcode_prefix='PO-G15-OLD',received_on=date(2026,11,12)))
        s.commit();return {m.__tablename__:s.scalar(select(func.count()).select_from(m))for m in (User,Edition,Compatibility,Classroom,Student,Copy,Inspection,Pack,PackLine,Assignment,Purchase,ReceiveBatch,Account,DepositEntry,HistoricalBasket)}
