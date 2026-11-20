import os,logging
from contextlib import asynccontextmanager
import redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI,Depends,HTTPException
from fastapi.responses import JSONResponse
from .db import session
from .models import *
from .schemas import *
from .common import lock,inventory_lock,pack,add,audit
from .auth import current,writer,supervisor,verify,token
from .middleware import Trace,Burst
from . import pack_service as packs,circulation_service as circulation
q=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
@asynccontextmanager
async def lifespan(app):
    if os.getenv('SEED_DEMO','true').lower()=='true':
        try:
            from .seed_service import seed
            seed()
        except Exception:logging.exception('seed failed')
    yield
app=FastAPI(title='循书校园·循环用书簿',lifespan=lifespan);app.add_middleware(Trace);app.add_middleware(Burst)
@app.exception_handler(IntegrityError)
async def duplicate(r,e):return JSONResponse({'detail':'条码、编号、课程映射或回单重复，不能重复入账'},409)
@app.get('/health')
def health(s=Depends(session)):s.execute(select(1));q.ping();return {'status':'ok'}
@app.post('/auth/login')
def login(d:Login,s=Depends(session)):
    u=s.scalar(select(User).where(User.email==d.email))
    if not u or not verify(d.password,u.password_hash):raise HTTPException(401,'邮箱或口令错误')
    return {'token':token(u),'user':{'email':u.email,'role':u.role}}
@app.get('/me')
def me(u=Depends(current)):return {'email':u.email,'role':u.role}
@app.get('/archive')
def archive(s=Depends(session),u=Depends(current)):
    return {m.__tablename__:[pack(x)for x in s.scalars(select(m).order_by(m.id))]for m in (Edition,Compatibility,Classroom,Student,Copy,Inspection,Pack,PackLine,Assignment,Purchase,Account,DepositEntry)}
@app.get('/audits')
def audits(s=Depends(session),u=Depends(current)):return [pack(x)for x in s.scalars(select(Audit).order_by(Audit.id.desc()).limit(50))]
@app.post('/editions')
def edition(d:EditionInput,s=Depends(session),u=Depends(writer)):
    x=add(s,Edition(**d.model_dump()));audit(s,u,'登记教材版次 '+d.code);s.commit();return x
@app.post('/compatibilities')
def compatibility(d:CompatibilityInput,s=Depends(session),u=Depends(writer)):
    inventory_lock(s);a=s.get(Edition,d.target_id);b=s.get(Edition,d.allowed_id)
    if not a or not b:raise HTTPException(404,'版次不存在')
    if a.id==b.id or a.subject!=b.subject:raise HTTPException(409,'兼容核验须同课程的不同版次')
    x=add(s,Compatibility(**d.model_dump()));audit(s,u,'提交教师版次兼容核验');s.commit();return x
@app.post('/compatibilities/{id}/approve')
def approve_compatibility(id:int,s=Depends(session),u=Depends(supervisor)):
    inventory_lock(s);x=lock(s,Compatibility,id)
    if x.state!='pending':raise HTTPException(409,'版次映射已经核定')
    x.state='approved';audit(s,u,'主管批准版次兼容');s.commit();return pack(x)
@app.post('/classrooms')
def classroom(d:ClassroomInput,s=Depends(session),u=Depends(writer)):
    x=add(s,Classroom(**d.model_dump()));audit(s,u,'登记班级 '+d.code);s.commit();return x
@app.post('/students')
def student(d:StudentInput,s=Depends(session),u=Depends(writer)):
    if not s.get(Classroom,d.classroom_id):raise HTTPException(404,'班级不存在')
    x=add(s,Student(**d.model_dump()));audit(s,u,'登记学生 '+d.code);s.commit();return x
@app.post('/copies')
def copy(d:CopyInput,s=Depends(session),u=Depends(writer)):
    inventory_lock(s)
    if not s.get(Edition,d.edition_id):raise HTTPException(404,'版次不存在')
    x=add(s,Copy(**d.model_dump()));audit(s,u,'回收单本待检 '+d.barcode);s.commit();return x
@app.post('/copies/{id}/inspect')
def inspect(id:int,d:InspectionInput,s=Depends(session),u=Depends(writer)):
    inventory_lock(s);x=lock(s,Copy,id)
    if x.state not in ('uninspected','available','repair'):raise HTTPException(409,'预留/在借/遗失书不能覆盖书况')
    x.condition=d.condition;x.state='available'if d.condition=='usable'else'repair';entry=add(s,Inspection(copy_id=id,**d.model_dump()));audit(s,u,'检查或修复书况 '+x.barcode);s.commit();return {'copy':pack(x),'inspection':entry}
@app.post('/packs')
def pack_new(d:PackInput,s=Depends(session),u=Depends(writer)):
    x=packs.create(s,d,u);s.commit();return x
@app.post('/packs/{id}/recommend')
def recommend(id:int,s=Depends(session),u=Depends(writer)):
    p=lock(s,Pack,id)
    if p.ml_state not in ('recorded','failed'):raise HTTPException(409,'只可估计新配套或失败重试')
    p.ml_state='queued';p.error=None;s.commit()
    try:q.rpush('book-baskets',id)
    except Exception:p.ml_state='failed';p.error='队列不可用，恢复后可重新排队';s.commit();raise HTTPException(503,p.error)
    return pack(p)
@app.post('/packs/{id}/reserve')
def reserve(id:int,s=Depends(session),u=Depends(supervisor)):
    x=packs.reserve(s,id,u);s.commit();return x
@app.post('/purchases/{id}/receive')
def receive(id:int,d:ReceiveInput,s=Depends(session),u=Depends(supervisor)):
    x=packs.receive(s,id,d,u);s.commit();return x
@app.post('/accounts')
def account(d:AccountInput,s=Depends(session),u=Depends(writer)):
    lock(s,Student,d.student_id);x=add(s,Account(**d.model_dump()));audit(s,u,'建立学期押金账户');s.commit();return x
@app.post('/accounts/{id}/deposit')
def deposit(id:int,d:DepositInput,s=Depends(session),u=Depends(supervisor)):
    x=lock(s,Account,id)
    if x.state!='open':raise HTTPException(409,'已清算账户不可重开收款')
    x.balance_cents+=d.amount_cents;entry=add(s,DepositEntry(account_id=id,kind='deposit',amount_cents=d.amount_cents,receipt=d.receipt,note='学生学期押金实收'));audit(s,u,'收取学生押金');s.commit();return {'account':pack(x),'entry':entry}
@app.post('/assignments/{id}/issue')
def issue(id:int,d:IssueInput,s=Depends(session),u=Depends(writer)):
    x=circulation.issue(s,id,d,u);s.commit();return x
@app.post('/assignments/{id}/return')
def return_book(id:int,d:ReturnInput,s=Depends(session),u=Depends(writer)):
    x=circulation.return_book(s,id,d,u);s.commit();return x
@app.post('/assignments/{id}/exchange')
def exchange(id:int,d:ReturnInput,s=Depends(session),u=Depends(writer)):
    x=circulation.return_book(s,id,d,u,True);s.commit();return x
@app.post('/assignments/{id}/loss')
def loss(id:int,d:LossInput,s=Depends(session),u=Depends(supervisor)):
    x=circulation.lose(s,id,d,u);s.commit();return x
@app.post('/accounts/{id}/settle')
def settle(id:int,d:SettlementInput,s=Depends(session),u=Depends(supervisor)):
    x=circulation.settle(s,id,d,u);s.commit();return x
