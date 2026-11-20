from typing import Literal
from pydantic import BaseModel,Field,model_validator
class Login(BaseModel):email:str;password:str
class EditionInput(BaseModel):code:str=Field(min_length=3,max_length=40);title:str=Field(min_length=2,max_length=100);subject:str=Field(min_length=2,max_length=40);version:str=Field(min_length=1,max_length=30);deposit_cents:int=Field(ge=100,le=100000)
class CompatibilityInput(BaseModel):target_id:int;allowed_id:int;reason:str=Field(min_length=6,max_length=250)
class ClassroomInput(BaseModel):code:str=Field(min_length=3,max_length=40);name:str=Field(min_length=2,max_length=100);size:int=Field(ge=1,le=100)
class StudentInput(BaseModel):code:str=Field(min_length=3,max_length=40);name:str=Field(min_length=2,max_length=60);classroom_id:int
class CopyInput(BaseModel):barcode:str=Field(min_length=3,max_length=60);edition_id:int;source:str=Field(min_length=2,max_length=120)
class InspectionInput(BaseModel):condition:Literal['usable','repair'];note:str=Field(min_length=4,max_length=250)
class LineInput(BaseModel):edition_id:int;quantity:int=Field(ge=1,le=100)
class PackInput(BaseModel):
    code:str=Field(min_length=3,max_length=60);classroom_id:int;term:str=Field(min_length=3,max_length=30);lines:list[LineInput]=Field(min_length=1,max_length=6)
    @model_validator(mode='after')
    def unique(self):
        if len({x.edition_id for x in self.lines})!=len(self.lines):raise ValueError('课程版次不能重复')
        return self
class ReceiveInput(BaseModel):quantity:int=Field(ge=1,le=100);barcode_prefix:str=Field(min_length=3,max_length=45)
class IssueInput(BaseModel):student_id:int
class AccountInput(BaseModel):student_id:int;term:str=Field(min_length=3,max_length=30)
class DepositInput(BaseModel):amount_cents:int=Field(ge=100,le=1000000);receipt:str=Field(min_length=4,max_length=80)
class ReturnInput(BaseModel):condition:Literal['usable','repair'];damage_cents:int=Field(default=0,ge=0,le=100000);note:str=Field(min_length=4,max_length=250);receipt:str=Field(min_length=4,max_length=80)
class LossInput(BaseModel):damage_cents:int=Field(ge=1,le=100000);note:str=Field(min_length=6,max_length=250);receipt:str=Field(min_length=4,max_length=80)
class SettlementInput(BaseModel):receipt:str=Field(min_length=4,max_length=80)
