from flask import Flask
from flask_restful import Resource, Api, reqparse
from config import Config
from models import User as DB_User,Appointment,db
import secrets

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
            return "Error! You need to provide argument 'user'",400
        
        if db.session.query(DB_User).filter(DB_User.name==user_name).scalar() is not None:
            return "Error! User '"+user_name+"' already exists",404

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

api.add_resource(Users,'/users')
api.add_resource(User,'/user/<user_name>')

parser = reqparse.RequestParser()
parser.add_argument('user',type=str)

if __name__=='__main__':
    app.run(debug=True)