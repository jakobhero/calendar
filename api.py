from flask import Flask
from flask_restful import Resource, Api, reqparse
from config import Config
from models import User as DB_User,Appointment as DB_Appointment,Calendar as DB_Calendar, Association as DB_Association, db
import secrets, datetime

app = Flask(__name__)
app.config.from_object(Config)
api=Api(app)
db.init_app(app)

class Users(Resource):
    def get(self):
        users=[]
        for user in db.session.query(DB_User).all():
            users.append(user.to_dict())
        return {"users":users},200
    
    def post(self):
        args=parser.parse_args()
        user_name=args["user"]
        if user_name == None:
            return "Error! No argument 'user' provided.",400
        
        if db.session.query(DB_User).filter(DB_User.name==user_name).scalar() is not None:
            return "Error! User '"+user_name+"' already exists.",404

        new_user=DB_User(name=user_name,secret=secrets.token_hex(nbytes=4))
        db.session.add(new_user)
        db.session.commit()

        return {
            'user':new_user.to_dict(),
            'secret':new_user.secret
        },200

class User(Resource):
    def get(self,user_name):
        if db.session.query(DB_User).filter(DB_User.name==user_name).scalar() is None:
            return "User '"+user_name+"' is not in the system",404
        return db.session.query(DB_User).filter(DB_User.name==user_name).first().to_dict(),200

    def post(self,user_name):
        if db.session.query(DB_User).filter(DB_User.name==user_name).scalar() is None:
            return "User '"+user_name+"' is not in the system",404

        args=parser.parse_args()
        calendar_name=args["calendar"]
        if calendar_name == None:
            return "Error! No argument 'calendar' provided",400

        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is not None:
            return "Error! User '"+user_name+"' already has a calendar named '"+calendar_name+"'. Please choose a unique calendar name.",400
        
        new_calendar=DB_Calendar(name=calendar_name,owned_by=user_name)
        db.session.add(new_calendar)
        db.session.commit()

        #retrieve the system identifier from the previously created calendar
        calendar_id=db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().id
        
        #if user has now default calendar yet, the new calendar will be the default.
        status="own"
        if db.session.query(DB_Association).filter(DB_Association.user_name==user_name,DB_Association.status=="default").scalar() is None:
            status="default"

        new_association=DB_Association(user_name=user_name,calendar_id=new_calendar.id,status=status)
        db.session.add(new_association)
        db.session.commit()

        return {
            'calendar':new_calendar.to_dict()
        },200

class Appointment(Resource):
    def get(self,user_name,calendar_name):
        if db.session.query(DB_User).filter(DB_User.name==user_name).scalar() is None:
            return "User '"+user_name+"' is not in the system",404
        
        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is None:
            return "Error! User '"+user_name+"' does not own a calendar named '"+calendar_name+"'.",400
        
        return db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().to_dict()["appointments"],200
    
    def post(self,user_name,calendar_name):
        if db.session.query(DB_User).filter(DB_User.name==user_name).scalar() is None:
            return "User '"+user_name+"' is not in the system",404
        
        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is None:
            return "Error! User '"+user_name+"' does not own a calendar named '"+calendar_name+"'.",400
        
        args=parser.parse_args()
        name,start,duration=args["name"],args["start"],args["dur"]

        if name == None or start == None or duration == None:
            return "Error! Make sure to provide the arguments 'name', 'start', and 'dur'"

        start=datetime.datetime.fromtimestamp(start)
        calendar_id=db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().id

        #check against existing records in DB, in which case the write operation is an update.
        start_comp=start.replace(hour=0, minute=0, second=0, microsecond=0)
        end_comp=start_comp+datetime.timedelta(hours=24)
        existing_appointment=db.session.query(DB_Appointment).filter(DB_Appointment.name==name,DB_Appointment.date>=start_comp,DB_Appointment.date<end_comp,DB_Appointment.calendar_id==calendar_id).first()
        if existing_appointment!=None:
            existing_appointment.date=start
            existing_appointment.duration=duration
            db.session.commit()
            return {
                "type":"update",
                "appointment":existing_appointment.to_dict()
                }
                      
        #print(f"Start comparison date: {start_comp}\nEnd comparison date: {end_comp}\nActual date: {start}")
        new_appointment=DB_Appointment(name=name,date=start,duration=duration,calendar_id=calendar_id)
        db.session.add(new_appointment)
        db.session.commit()
        
        return {
            "type":"insertion",
            "appointment":new_appointment.to_dict()
        }

    def delete(self,user_name,calendar_name):
        if db.session.query(DB_User).filter(DB_User.name==user_name).scalar() is None:
            return "User '"+user_name+"' is not in the system",404
        
        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is None:
            return "Error! User '"+user_name+"' does not own a calendar named '"+calendar_name+"'.",400
        
        args=parser.parse_args()
        name,start=args["name"],args["start"]

        if name == None or start == None:
            return "Error! Make sure to provide the identifying arguments 'name' and 'start'"

        start=datetime.datetime.utcfromtimestamp(start)
        calendar_id=db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().id 

        existing_appointment=db.session.query(DB_Appointment).filter(DB_Appointment.name==name,DB_Appointment.date==start,DB_Appointment.calendar_id==calendar_id).first()
        if existing_appointment==None:
            return f"Error! The requested appointment with 'name' == {name} and 'date' == {start} does not exist in this calendar."

        db.session.delete(existing_appointment)
        db.session.commit()
        return {
            "type":"deletion",
            "appointment":existing_appointment.to_dict()
        }            

api.add_resource(Users,'/users')
api.add_resource(User,'/user/<user_name>')
api.add_resource(Appointment,'/appointments/<user_name>/<calendar_name>')

parser = reqparse.RequestParser()
parser.add_argument('user',type=str)
parser.add_argument('calendar',type=str)
parser.add_argument('name',type=str)
parser.add_argument('start',type=int)
parser.add_argument('dur',type=int)

if __name__=='__main__':
    app.run(debug=True)