from flask import Flask
from flask_restful import Resource, Api, reqparse
from config import Config
from models import User as DB_User,Appointment as DB_Appointment,Calendar as DB_Calendar, UC_Association as DB_UCA, CA_Association as DB_CAA, db
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
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404
        return db.session.query(DB_User).filter(DB_User.name==user_name).first().to_dict(),200

    def post(self,user_name):
        if not user_exists(user_name):
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
        if db.session.query(DB_UCA).filter(DB_UCA.user_name==user_name,DB_UCA.status=="default").scalar() is None:
            status="default"

        new_association=DB_UCA(user_name=user_name,calendar_id=new_calendar.id,status=status)
        db.session.add(new_association)
        db.session.commit()

        return {
            'calendar':new_calendar.to_dict()
        },200

class Appointment(Resource):
    def get(self,user_name,calendar_name):
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404
        
        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is None:
            return "Error! User '"+user_name+"' does not own a calendar named '"+calendar_name+"'.",400
        
        return db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().to_dict()["appointments"],200
    
    def post(self,user_name,calendar_name):
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404
        
        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is None:
            return "Error! User '"+user_name+"' does not own a calendar named '"+calendar_name+"'.",400
        
        args=parser.parse_args()
        name,start,duration=args["name"],args["start"],args["dur"]

        if name == None or start == None or duration == None:
            return "Error! Make sure to provide the arguments 'name', 'start', and 'dur'",400

        start=datetime.datetime.fromtimestamp(start)
        calendar_id=db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().id

        #check against existing records in DB, in which case the write operation is an update.
        existing_appointment=check_appointment(name,start,calendar_id)
        if existing_appointment!=None:
            existing_appointment.date=start
            existing_appointment.duration=duration
            db.session.commit()
            return {
                "type":"update",
                "appointment":existing_appointment.to_dict()
                },200
                      
        #print(f"Start comparison date: {start_comp}\nEnd comparison date: {end_comp}\nActual date: {start}")
        new_appointment=DB_Appointment(name=name,date=start,duration=duration,origin_id=calendar_id)
        db.session.add(new_appointment)
        db.session.commit()

        appointment_id=check_appointment(name,start,calendar_id).id
        new_association=DB_CAA(calendar_id=calendar_id,appointment_id=appointment_id,status="host")
        db.session.add(new_association)
        db.session.commit()
        
        return {
            "type":"insertion",
            "appointment":new_appointment.to_dict()
        },200

    def delete(self,user_name,calendar_name):
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404
        
        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is None:
            return "Error! User '"+user_name+"' does not own a calendar named '"+calendar_name+"'.",400
        
        args=parser.parse_args()
        name,start=args["name"],args["start"]

        if name == None or start == None:
            return "Error! Make sure to provide the identifying arguments 'name' and 'start'",400

        start=datetime.datetime.utcfromtimestamp(start)
        calendar_id=db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().id 

        existing_appointment=check_appointment(name,start,calendar_id)
        if existing_appointment==None:
            return f"Error! The requested appointment with 'name' == {name} and 'date' == {start} does not exist in this calendar or you do not have the permission to delete it.",400

        db.session.delete(existing_appointment)
        db.session.commit()
        return {
            "type":"deletion",
            "appointment":existing_appointment.to_dict()
        },200

class Search(Resource):
    def get(self,user_name):
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404
        return {"appointments":find_appointments(user_name)}       

    def post(self,user_name):
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404

        args=parser.parse_args()
        appointment_name=args["name"]
        
        return {"appointments":find_appointments(user_name,appointment_name)},200

class Availability(Resource):
    def post(self,user_name):
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404
        
        args=parser.parse_args()
        booked_user=args["user"]
        days_ahead=args["days_ahead"]

        if days_ahead==None:
            days_ahead=7

        if booked_user==None:
            return "Error! You must specify a user that you want to book an appointment with by passing the argument 'user'",400

        if not user_exists(booked_user):
            return f"Error! The user '{booked_user}' you want to book an appointment with does not exist in the system",404

        if user_name==booked_user:
            return f"Error! You cannot book an appointment with yourself",400

        #the allowed time for bookings is anywhere from now to the days ahead provided in the request (by default 7)
        start_time=datetime.datetime.now()
        end_time=start_time+datetime.timedelta(days=days_ahead)

        #retrieve the appointments of the booking and the booked user within the corresponding timeframe
        booking=find_appointments(user_name,None,start_time,end_time)
        booked=find_appointments(booked_user,None,start_time,end_time)

        booking_user=db.session.query(DB_User).filter(DB_User.name==user_name).first()
        booked_user=db.session.query(DB_User).filter(DB_User.name==booked_user).first()

        starting_point=datetime.datetime.min
        earliest_td=max(booking_user.avail_start,booked_user.avail_start)-starting_point
        latest_td=min(booking_user.avail_end,booked_user.avail_end)-starting_point

        time_slots={}   
        i,j=0,0
        while(start_time<end_time):
            available=[]
            weekday=start_time.weekday()
            midnight=start_time.replace(hour=0,minute=0,second=0,microsecond=0)
            earliest=midnight+earliest_td
            latest=midnight+latest_td
            if weekday>4:
                start_time+=datetime.timedelta(days=1)
                continue
            if booking_user.avail_days[weekday]=="n" or booked_user.avail_days[weekday]=="n":
                time_slots[start_time.strftime("%Y/%m/%d")]=available
                start_time+=datetime.timedelta(days=1)
                continue
            unix_earliest=earliest.timestamp()
            unix_latest=latest.timestamp()

            # while len(booking)>i and booking[i]["datestamp"]<unix_earliest:
            #     curr=booking[i]["datestamp"]+booking[i]["duration"]*60+booking_user.buffer*60
            #     if curr>unix_earliest:
            #         unix_earliest=datetime.datetime.fromtimestamp(curr)
            #     i+=1
            # while len(booked)>j and booked[j]["datestamp"]<unix_earliest:
            #     curr=booked[j]["datestamp"]+booking[j]["duration"]*60+booked_user.buffer*60
            #     if curr>unix_earliest:
            #         unix_earliest=datetime.datetime.fromtimestamp(curr)
            #     j+=1

            if i == len(booking) and j == len(booked):
                if unix_earliest<unix_latest:
                    available.append([unix_to_time(unix_earliest),unix_to_time(unix_latest)])
                time_slots[start_time.strftime("%Y/%m/%d")]=available
                start_time+=datetime.timedelta(days=1)
                continue

            next_booking,next_booked=unix_latest,unix_latest
            while i != len(booking) or j != len(booked):
                print(f"i = {i}, j = {j}, lengths of lists: {len(booking),len(booked)}")
                if i<len(booking):
                    next_booking=min(booking[i]["datestamp"]-booking_user.buffer*60,unix_latest)
                else:
                    next_booking=unix_latest
                if j<len(booking):
                    next_booked=min(booked[j]["datestamp"]-booked_user.buffer*60,unix_latest)
                else:
                    next_booked=unix_latest
                print(f"next booking: {unix_to_time(next_booking)}, next booked: {unix_to_time(next_booked)}.")
                if min(next_booking,next_booked)>unix_earliest:
                    available.append([unix_to_time(unix_earliest),unix_to_time(min(next_booking,next_booked))])
                if next_booking >= unix_latest and next_booked >= unix_latest:
                    break
                if next_booking<next_booked:
                    unix_earliest=next_booking+(booking[i]["duration"]+2*booking_user.buffer)*60
                    i+=1
                else:
                    unix_earliest=next_booked+(booked[j]["duration"]+2*booked_user.buffer)*60
                    j+=1
            
            # if unix_earliest<unix_latest:
            #     available.append([unix_to_time(unix_earliest),unix_to_time(unix_latest)])

            time_slots[start_time.strftime("%Y/%m/%d")]=available
            start_time+=datetime.timedelta(days=1)
    
        return time_slots,200

class Booking(Resource):
    def post(self,user_name,calendar_name):
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404
        
        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is None:
            return "Error! User '"+user_name+"' does not own a calendar named '"+calendar_name+"'.",400
        
        args=parser.parse_args()
        booked_user=args["user"]
        name,start,duration=args["name"],args["start"],args["dur"]

        if booked_user==None:
            return "Error! You must specify a user that you want to book an appointment with by passing the argument 'user'",400
        
        if name == None or start == None or duration == None:
            return "Error! Make sure to provide the arguments 'name', 'start', and 'dur'",400

        unix_start=start
        unix_end=start+duration*60

        search_start=datetime.datetime.fromtimestamp(unix_start).replace(hour=0,minute=0,second=0,microsecond=0)
        search_end=search_start+datetime.timedelta(days=1)

        booking=db.session.query(DB_User).filter(DB_User.name==user_name).first()
        booked=db.session.query(DB_User).filter(DB_User.name==booked_user).first()
        if booked==None:
            return f"Error! The user '{booked_user}' you are trying to set up an appointment with does not exist in the system.'"

        appointments_booking=find_appointments(user_name,None,search_start,search_end)
        appointments_booked=find_appointments(booked_user,None,search_start,search_end)

        if not slot_available(booking,appointments_booking,unix_start,unix_end):
            return f"Error! User '{user_name}' is not free at the requested slot",400

        if not slot_available(booked,appointments_booked,unix_start,unix_end):
            return f"Error! User '{booked_user}' is not free at the requested slot",400


        #retrieve the system identifier from the previously created calendar
        calendar_id=db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().id
        start_dt=datetime.datetime.fromtimestamp(start)

        new_appointment=DB_Appointment(name=name,date=start_dt,duration=duration,origin_id=calendar_id)
        db.session.add(new_appointment)
        db.session.commit()

        #find guest default calendar
        guest_calendar_id=db.session.query(DB_UCA).filter(DB_UCA.user_name==booked_user,DB_UCA.status=="default").first().calendar_id

        appointment_id=check_appointment(name,start_dt,calendar_id).id
        new_association_host=DB_CAA(calendar_id=calendar_id,appointment_id=appointment_id,status="host")
        new_association_guest=DB_CAA(calendar_id=guest_calendar_id,appointment_id=appointment_id,status="pending")
        db.session.add(new_association_host)
        db.session.add(new_association_guest)
        db.session.commit()
        return{
            "type":"invitation",
            "appointment":new_association_guest.to_dict()
        },200

class Sharing(Resource):
    def post(self,user_name,calendar_name):
        if not user_exists(user_name):
            return "User '"+user_name+"' is not in the system",404
        
        if db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).scalar() is None:
            return "Error! User '"+user_name+"' does not own a calendar named '"+calendar_name+"'.",400
        
        args=parser.parse_args()
        shared_name=args["user"]
        if shared_name==None:
            return f"Error! You must provide a user you want to share the calendar with by setting the argument 'user'",400
        
        shared_user=db.session.query(DB_User).filter(DB_User.name==shared_name).first()
        if shared_user==None:
            return f"Error! The user '{shared_user}' you are trying to share a calendar with does not exist in the system.'"
        
        calendar_id=db.session.query(DB_Calendar).filter(DB_Calendar.owned_by==user_name,DB_Calendar.name==calendar_name).first().id
        shared_association=DB_UCA(user_name=shared_name,calendar_id=calendar_id,status="pending")
        db.session.add(shared_association)
        db.session.commit()
        return{
            "type":"calendar invite",
            "calendar":shared_association.to_dict()
        },200

def user_exists(name):
    """Function checks whether user with name exists in system"""
    if db.session.query(DB_User).filter(DB_User.name==name).scalar() is None:
        return False
    return True

def check_appointment(name,start,calendar_id):
    """Function returns the result for a query on appointments with given name, start time on the same day as the time provided and calendar_id.
    The combination of these three attributes function as identifying tuple for the appointment relation."""
    start_comp=start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_comp=start_comp+datetime.timedelta(hours=24)
    return db.session.query(DB_Appointment).filter(DB_Appointment.name==name,DB_Appointment.date>=start_comp,DB_Appointment.date<end_comp,DB_Appointment.origin_id==calendar_id).first()

def find_appointments(user_name,substring=None,min_start=datetime.datetime.min,max_start=datetime.datetime.max):
    """Function returns all appointments associated with the calendars associated with the provided user.
    If argument substring is passed, only those appointments that contain substring in its name will be returned."""
    name_search=True
    if substring == None:
        name_search=False

    appointments=[]
    calendars=db.session.query(DB_User).filter(DB_User.name==user_name).first().calendars
    for calendar in calendars:
        for appointment in calendar.calendar.appointments:
            if appointment not in appointments:
                curr=appointment.appointment
                if curr.date>=min_start and curr.date<=max_start and (not name_search or substring.lower() in curr.name.lower()):
                    appointments.append(appointment.to_dict())
    
    #sort the appointments in order of their start date
    appointments.sort(key=lambda x:x["datestamp"])
    return appointments

def unix_to_time(timestamp):
    """converts a unix timestamp to a time in the format HH:MM."""
    return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M")

def slot_available(user,appointments,unix_start,unix_end):
    start,end=datetime.datetime.fromtimestamp(unix_start),datetime.datetime.fromtimestamp(unix_end)
    weekday=start.weekday()
    midnight=start.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()

    #appointment is at unavailable day or the weekend
    if weekday > 4 or user.avail_days[weekday]=="n":
        return False
    
    #appointment starts before the user's daily availability begins
    if unix_start-midnight < user.avail_start.replace(tzinfo=datetime.timezone.utc).timestamp():
        print("problem here")
        return False

    #appointment ends after the user's daily availability has ended
    if unix_end-midnight > user.avail_end.replace(year=1970,tzinfo=datetime.timezone.utc).timestamp():
        print("problem there")
        print(unix_end-midnight,user.avail_end.replace(year=1970,tzinfo=datetime.timezone.utc).timestamp())
        return False

    for appointment in appointments:
        ds=appointment["datestamp"]
        dur=appointment["duration"]
        #the planned appointment starts when another one is ongoing
        if unix_start-user.buffer*60>ds and unix_start-user.buffer*60<ds+dur*60:
            return False

        #the planned appointment ends when another one is ongoing
        if unix_end+user.buffer*60>ds and unix_end+user.buffer*60<ds+dur*60:
            return False

        #the planned appointment encapsulates an existing appointment
        if ds >= unix_start-user.buffer*60  and ds <=unix_end+user.buffer*60:
            return False
    
    return True
    



api.add_resource(Users,'/users')
api.add_resource(User,'/user/<user_name>')
api.add_resource(Appointment,'/appointments/<user_name>/<calendar_name>')
api.add_resource(Search,'/search/<user_name>')
api.add_resource(Availability,'/availability/<user_name>')
api.add_resource(Booking,'/book/<user_name>/<calendar_name>')
api.add_resource(Sharing,'/share/<user_name>/<calendar_name>')

parser = reqparse.RequestParser()
parser.add_argument('user',type=str)
parser.add_argument('calendar',type=str)
parser.add_argument('name',type=str)
parser.add_argument('start',type=int)
parser.add_argument('dur',type=int)
parser.add_argument('days_ahead',type=int)

if __name__=='__main__':
    app.run(debug=True)