from flask import Flask
from flask_restful import Resource, Api, reqparse
from config import Config
from models import User as DB_User,Appointment as DB_Appointment,Calendar as DB_Calendar, Association, db
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
        name,start,duration=args["app_name"],datetime.datetime.fromtimestamp(args["app_start"]),args["app_dur"]

        if name == None or start == None or duration == None:
            return "Error! Make sure to provide the arguments 'app_name', 'app_start', and 'app_dur'"
       
        calendar_id=db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().id
        new_appointment=DB_Appointment(name=name,date=start,duration=duration,calendar_id=calendar_id)
        db.session.add(new_appointment)
        db.session.commit()
        return new_appointment.to_dict()

        

api.add_resource(Users,'/users')
api.add_resource(User,'/user/<user_name>')
api.add_resource(Appointment,'/appointments/<user_name>/<calendar_name>')

parser = reqparse.RequestParser()
parser.add_argument('user',type=str)
parser.add_argument('calendar',type=str)
parser.add_argument('app_name',type=str)
parser.add_argument('app_start',type=int)
parser.add_argument('app_dur',type=int)

if __name__=='__main__':
    app.run(debug=True)