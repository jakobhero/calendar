from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import DeclarativeMeta
import datetime

db=SQLAlchemy()

class User(db.Model):
    __tablename__='user'
    name=db.Column(db.String(20),nullable=False,primary_key=True)
    secret=db.Column(db.String(8),nullable=False)
    avail_days=db.Column(db.String(5),default="yyyyy")
    avail_start=db.Column(db.DateTime(),default=datetime.datetime(year=datetime.MINYEAR,month=1,day=1,hour=9,minute=0))
    avail_end=db.Column(db.DateTime(),default=datetime.datetime(year=datetime.MINYEAR,month=1,day=1,hour=18,minute=0))
    buffer=db.Column(db.SmallInteger,default=15)
    appointments=db.relationship('Appointment',backref='owner', cascade="all, delete", lazy=True)

    def __repr__(self):
        return 'Name: '+self.name+', Secret: '+self.secret

    def to_dict(self):
        appointments=[]
        for appointment in self.appointments:
            appointments.append(appointment.to_dict())
        return {
            'name':self.name,
            'availability':{
                'days':self.avail_days,
                'start':self.avail_start.strftime("%H:%M"),
                'end':self.avail_end.strftime("%H:%M")
            },
            'appointments':appointments
        }

class Appointment(db.Model):
    _tablename__='appointment'
    name=db.Column(db.String(100),nullable=False,primary_key=True)
    date=db.Column(db.DateTime(),nullable=False)
    duration=db.Column(db.SmallInteger,nullable=False)
    owner_id=db.Column(db.String(8),db.ForeignKey('user.secret'),nullable=False)
    
    def __repr__(self):
        return 'Name '+self.name+'\ntakes place on '+self.date+' for '+str(self.duration)+' mins.\nCreated by '+self.owner_id+'.'

    def to_dict(self):
        return {
            'name':self.name,
            'date':self.date.strftime("%Y/%m/%d %H:%M"),
            'duration':self.duration
        }