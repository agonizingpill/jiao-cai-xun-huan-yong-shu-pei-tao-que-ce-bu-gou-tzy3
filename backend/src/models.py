from sqlalchemy import Column,Integer,String,ForeignKey,JSON,UniqueConstraint,CheckConstraint
from .db import Base
from .constants import COPY_CONDITIONS,PACK_STATES,ASSIGNMENT_STATES
class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True);email=Column(String(100),unique=True,nullable=False);password_hash=Column(String(220),nullable=False);role=Column(String(30),nullable=False)
class Audit(Base):
    __tablename__='audits'
    id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(300))
class Edition(Base):
    __tablename__='editions'
    id=Column(Integer,primary_key=True);code=Column(String(40),unique=True,nullable=False);title=Column(String(100),nullable=False);subject=Column(String(40),nullable=False);version=Column(String(30),nullable=False);deposit_cents=Column(Integer,nullable=False)
    __table_args__=(CheckConstraint('deposit_cents>0'),)
class Compatibility(Base):
    __tablename__='compatibilities'
    id=Column(Integer,primary_key=True);target_id=Column(Integer,ForeignKey('editions.id'),nullable=False);allowed_id=Column(Integer,ForeignKey('editions.id'),nullable=False);reason=Column(String(250),nullable=False);state=Column(String(20),default='pending')
    __table_args__=(UniqueConstraint('target_id','allowed_id'),)
class Classroom(Base):
    __tablename__='classrooms'
    id=Column(Integer,primary_key=True);code=Column(String(40),unique=True,nullable=False);name=Column(String(100),nullable=False);size=Column(Integer,nullable=False)
class Student(Base):
    __tablename__='students'
    id=Column(Integer,primary_key=True);code=Column(String(40),unique=True,nullable=False);name=Column(String(60),nullable=False);classroom_id=Column(Integer,ForeignKey('classrooms.id'),nullable=False)
class Copy(Base):
    __tablename__='copies'
    id=Column(Integer,primary_key=True);barcode=Column(String(60),unique=True,nullable=False);edition_id=Column(Integer,ForeignKey('editions.id'),nullable=False);condition=Column(String(20),default=COPY_CONDITIONS[0]);state=Column(String(20),default='uninspected');source=Column(String(120),nullable=False)
class Inspection(Base):
    __tablename__='inspections'
    id=Column(Integer,primary_key=True);copy_id=Column(Integer,ForeignKey('copies.id'),nullable=False);condition=Column(String(20),nullable=False);note=Column(String(250),nullable=False)
class Pack(Base):
    __tablename__='packs'
    id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);classroom_id=Column(Integer,ForeignKey('classrooms.id'),nullable=False);term=Column(String(30),nullable=False);state=Column(String(20),default=PACK_STATES[0]);ml_state=Column(String(20),default='recorded');recommendation=Column(JSON);error=Column(String(450))
class PackLine(Base):
    __tablename__='pack_lines'
    id=Column(Integer,primary_key=True);pack_id=Column(Integer,ForeignKey('packs.id'),nullable=False);edition_id=Column(Integer,ForeignKey('editions.id'),nullable=False);quantity=Column(Integer,nullable=False)
    __table_args__=(UniqueConstraint('pack_id','edition_id'),CheckConstraint('quantity>0'))
class Assignment(Base):
    __tablename__='assignments'
    id=Column(Integer,primary_key=True);line_id=Column(Integer,ForeignKey('pack_lines.id'),nullable=False);copy_id=Column(Integer,ForeignKey('copies.id'),nullable=False);student_id=Column(Integer,ForeignKey('students.id'));state=Column(String(20),default=ASSIGNMENT_STATES[0]);deposit_cents=Column(Integer,nullable=False);replacement_for_id=Column(Integer,ForeignKey('assignments.id'));note=Column(String(250),default='')
class Purchase(Base):
    __tablename__='purchases'
    id=Column(Integer,primary_key=True);line_id=Column(Integer,ForeignKey('pack_lines.id'),unique=True,nullable=False);ordered=Column(Integer,nullable=False);received=Column(Integer,default=0);state=Column(String(20),default='open')
class Account(Base):
    __tablename__='accounts'
    id=Column(Integer,primary_key=True);student_id=Column(Integer,ForeignKey('students.id'),nullable=False);term=Column(String(30),nullable=False);balance_cents=Column(Integer,default=0);state=Column(String(20),default='open')
    __table_args__=(UniqueConstraint('student_id','term'),CheckConstraint('balance_cents>=0'))
class DepositEntry(Base):
    __tablename__='deposit_entries'
    id=Column(Integer,primary_key=True);account_id=Column(Integer,ForeignKey('accounts.id'),nullable=False);assignment_id=Column(Integer,ForeignKey('assignments.id'));kind=Column(String(20),nullable=False);amount_cents=Column(Integer,nullable=False);receipt=Column(String(80),unique=True,nullable=False);note=Column(String(250),nullable=False)
class HistoricalBasket(Base):
    __tablename__='historical_baskets'
    id=Column(Integer,primary_key=True);code=Column(String(40),unique=True,nullable=False);subjects=Column(JSON,nullable=False)
