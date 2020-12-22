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
    calendars_all=db.relationship('Association',backref='invited', cascade="all, delete", lazy=True)
    calendars_own=db.relationship('Calendar',backref='owner',cascade="all, delete",lazy=True)

    def __repr__(self):
        return 'Name: '+self.name+', Secret: '+self.secret

    def to_dict(self):
        calendars_own,calendars_invited=[],[]
        for calendar in self.calendars_own:
            calendars_own.append(calendar.to_dict())
        for association in self.calendars_all:
            calendars_invited.append({
                "calendar":association.calendar.to_dict(),
                "status":association.status
            })
        return {
            'name':self.name,
            'availability':{
                'days':self.avail_days,
                'start':self.avail_start.strftime("%H:%M"),
                'end':self.avail_end.strftime("%H:%M")
            },
            'calendars_own':calendars_own,
            'calendars_invited':calendars_invited
        }

class Association(db.Model):
    __tablename__='association'
    user_name=db.Column(db.String(20),db.ForeignKey("user.name"),primary_key=True)
    calendar_id=db.Column(db.Integer,db.ForeignKey("calendar.id"),primary_key=True)
    status=db.Column(db.String(20),default="Pending")

class Calendar(db.Model):
    __tablename__='calendar'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(50),nullable=False)
    owned_by=db.Column(db.String(8),db.ForeignKey('user.name'),nullable=False)
    invited=db.relationship('Association',backref='calendar', cascade="all, delete", lazy=True)
    appointments=db.relationship('Appointment',backref='calendar', cascade="all, delete", lazy=True)

    def to_dict(self):
        appointments=[]
        for appointment in self.appointments:
            appointments.append(appointment.to_dict())
        return {
            "name":self.name,
            "owner":self.owned_by,
            "appointments":appointments
        }

class Appointment(db.Model):
    _tablename__='appointment'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(100),nullable=False)
    date=db.Column(db.DateTime(),nullable=False)
    duration=db.Column(db.SmallInteger,nullable=False)
    calendar_id=db.Column(db.String(8),db.ForeignKey('calendar.id'),nullable=False)
    
    def __repr__(self):
        return 'Name '+self.name+'\ntakes place on '+self.date+' for '+str(self.duration)+' mins.\nCreated by '+self.owner_id+'.'

    def to_dict(self):
        return {
            'name':self.name,
            'date':self.date.strftime("%Y/%m/%d %H:%M"),
            'duration':self.duration
        }