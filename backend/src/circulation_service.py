from sqlalchemy import select,func
from fastapi import HTTPException
from .models import Edition,Student,Account,DepositEntry,Pack,PackLine,Copy,Assignment
from .common import inventory_lock,compatible,lock,add,pack,audit

def account_for(s,student,term):
    x=s.scalar(select(Account).where(Account.student_id==student,Account.term==term).with_for_update().execution_options(populate_existing=True))
    if not x or x.state!='open':raise HTTPException(409,'先建立本学期开放的学生押金账户')
    return x
def outstanding(s,student,term):
    return list(s.scalars(select(Assignment).join(PackLine,Assignment.line_id==PackLine.id).join(Pack,PackLine.pack_id==Pack.id).where(Assignment.student_id==student,Pack.term==term,Assignment.state=='issued')))
def issue(s,id,d,u):
    inventory_lock(s);a=lock(s,Assignment,id);line=s.get(PackLine,a.line_id);p=s.get(Pack,line.pack_id);student=s.get(Student,d.student_id)
    if not student or student.classroom_id!=p.classroom_id:raise HTTPException(409,'学生须属于本配套班级')
    acc=account_for(s,student.id,p.term)
    if a.state!='reserved' or s.get(Copy,a.copy_id).state!='reserved':raise HTTPException(409,'该本书已领出或不在预留状态')
    active=outstanding(s,student.id,p.term)
    subject=s.get(Edition,line.edition_id).subject
    if any(s.get(Edition,s.get(PackLine,x.line_id).edition_id).subject==subject for x in active):raise HTTPException(409,'该生本学期已领同课程用书，不能通过另一配套或版次重复领')
    if sum(x.deposit_cents for x in active)+a.deposit_cents>acc.balance_cents:raise HTTPException(409,'押金不足，须补足本学期在借用书押金')
    a.student_id=student.id;a.state='issued';s.get(Copy,a.copy_id).state='issued';audit(s,u,'学生领用单本 '+student.code);return pack(a)
def charge(s,account,a,amount,receipt,note):
    if amount>a.deposit_cents or amount>account.balance_cents:raise HTTPException(409,'损耗扣款不可超过该书押金或账户余额')
    if amount:
        account.balance_cents-=amount;s.add(DepositEntry(account_id=account.id,assignment_id=a.id,kind='damage',amount_cents=-amount,receipt=receipt,note=note))
def return_book(s,id,d,u,exchange=False):
    inventory_lock(s);a=lock(s,Assignment,id);line=s.get(PackLine,a.line_id);p=s.get(Pack,line.pack_id)
    if a.state!='issued':raise HTTPException(409,'只有在借书可退换，不可重复退书')
    acc=account_for(s,a.student_id,p.term)
    if d.condition=='usable'and d.damage_cents:raise HTTPException(409,'完好回收不收损耗费')
    charge(s,acc,a,d.damage_cents,d.receipt,d.note);copy=lock(s,Copy,a.copy_id);copy.condition=d.condition;copy.state='available'if d.condition=='usable'else'repair';a.state='returned';a.note=d.note
    if exchange:
        # Exclude the just-returned copy: a real physical exchange requires another book.
        replacement=s.scalar(select(Copy).where(Copy.edition_id.in_(compatible(s,line.edition_id)),Copy.condition=='usable',Copy.state=='available',Copy.id!=copy.id).order_by(Copy.id).with_for_update())
        if not replacement:raise HTTPException(409,'没有兼容且可用的替换书，保留原在借状态')
        if sum(x.deposit_cents for x in outstanding(s,a.student_id,p.term))+a.deposit_cents>acc.balance_cents:raise HTTPException(409,'损耗后押金不足，补足后再换书')
        replacement.state='issued';new=Assignment(line_id=line.id,copy_id=replacement.id,student_id=a.student_id,state='issued',deposit_cents=a.deposit_cents,replacement_for_id=a.id,note=d.note);s.add(new);s.flush();audit(s,u,'退换实物书并保留前后条码');return {'returned':pack(a),'replacement':pack(new)}
    audit(s,u,'学生退书与书况回收');return pack(a)
def lose(s,id,d,u):
    inventory_lock(s);a=lock(s,Assignment,id);line=s.get(PackLine,a.line_id);p=s.get(Pack,line.pack_id)
    if a.state!='issued':raise HTTPException(409,'仅在借书可报损，不可重复扣款')
    acc=account_for(s,a.student_id,p.term);charge(s,acc,a,d.damage_cents,d.receipt,d.note);copy=lock(s,Copy,a.copy_id);copy.state='lost';copy.condition='lost';a.state='lost';a.note=d.note;audit(s,u,'主管报损与押金扣款');return pack(a)
def settle(s,id,d,u):
    inventory_lock(s);acc=lock(s,Account,id)
    if acc.state!='open':raise HTTPException(409,'学期已经清算，不可重复退款')
    missing=outstanding(s,acc.student_id,acc.term)
    if missing:raise HTTPException(409,'仍有未归还书目：'+','.join(str(x.id)for x in missing))
    refund=acc.balance_cents;acc.balance_cents=0;acc.state='settled';entry=DepositEntry(account_id=acc.id,kind='refund',amount_cents=-refund,receipt=d.receipt,note='学期清算退还余额，无未还书目');s.add(entry);s.flush();audit(s,u,'学期押金清算与退款');return {'account':pack(acc),'refund_cents':refund,'entry':pack(entry)}
