import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, with_polymorphic

database = "sqlite:///data/database.sqlite"

SQLAlchemyBase = declarative_base()
engine = sa.create_engine(database, echo=False)
Session = sessionmaker(bind=engine)

#TODO: build database management functions to be called from elsewhere
# To be able to use these functions, you need to create a new session.
# When done, close the session!

def getFirst(session, table, column, value):
    return_value = session.query(table).filter_by(**{column: value}).first()
    return return_value

def getAll(session, table, column, value):
    return_value = session.query(table).filter_by(**{column: value}).all()
    return return_value

def dbInsert(session, db_object):
    """Inserts object"""
    if(db_object):
        session.add(db_object)
        session.commit()

def dbMerge(session, db_object):
    """Updates object"""
    if(db_object):
        session.merge(db_object)
        session.commit()

def getUserOnType(session, user_type, teams_id):
    return_value = session.query(User).filter((User.user_teams_id == teams_id) & (User.user_type == user_type)).first()

    return return_value

def getAllUsersOnType(session, user_type):
    return_value = session.query(User).filter(User.user_type == user_type).all()
    return return_value

def getEnrollment(session, committee_id, email):
    return session.query(Enrollment).filter((Enrollment.committee_id == committee_id) & (Enrollment.email_address == email)).first()


#TODO: build database tables

class User(SQLAlchemyBase):
    __tablename__ = 'user'
    user_id = sa.Column(sa.Integer, primary_key=True)
    user_teams_id = sa.Column(sa.String(50), index=True)
    user_name = sa.Column(sa.String(50))
    user_type = sa.Column(sa.String(50))

    __mapper_args__ = {
        'polymorphic_identity':'user',
        'polymorphic_on':user_type
    }


class CommitteeUser(User):
    __tablename__ = 'committee_user'
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.user_id'), primary_key=True)
    committee_id = sa.Column(sa.Integer, sa.ForeignKey('committee.committee_id'))

    __mapper_args__ = {
        'polymorphic_identity':'committee_user',
    }


class MentorUser(User):
    __tablename__ = 'mentor_user'
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.user_id'), primary_key=True)
    mg_id = sa.Column(sa.Integer, sa.ForeignKey('mentor_group.mg_id'))

    __mapper_args__ = {
        'polymorphic_identity':'mentor_user',
    }


class IntroUser(User):
    __tablename__ = 'intro_user'
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.user_id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity':'intro_user',
    }


class Committee(SQLAlchemyBase):
    __tablename__ = 'committee'
    committee_id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50), unique=True)
    info = sa.Column(sa.String(50))
    channel_id = sa.Column(sa.String(50), index=True)
    members = relationship("CommitteeUser")
    occupied = sa.Column(sa.Boolean, default=False)


class MentorGroup(SQLAlchemyBase):
    __tablename__ = 'mentor_group'
    mg_id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50), unique=True, index=True)
    channel_id = sa.Column(sa.String(50), index=True)
    parents = relationship("MentorUser")
    occupied = sa.Column(sa.Boolean, default=False)
    timeslot = sa.Column(sa.String(50))


class Visit(SQLAlchemyBase):
    __tablename__ = 'mentorgroup'
    visit_id = sa.Column(sa.Integer, primary_key=True)
    mg_id = sa.Column(sa.String(50), index=True)
    committee_id = sa.Column(sa.String(50))

class Enrollment(SQLAlchemyBase):
    __tablename__ = 'enrollment'
    enroll_id = sa.Column(sa.Integer, primary_key=True)
    committee_id = sa.Column(sa.Integer, sa.ForeignKey('committee.committee_id'))
    first_name = sa.Column(sa.String(50))
    last_name = sa.Column(sa.String(50))
    email_address = sa.Column(sa.String(50))
    __table_args__ = (sa.UniqueConstraint('committee_id', 'email_address', name='_id_email_uc'),)


@event.listens_for(User, 'mapper_configured')
def receive_mapper_configured(mapper, class_):
    # to prevent 'incompatible polymorphic identity' warning, not mandatory
    mapper._validate_polymorphic_identity = None

SQLAlchemyBase.metadata.create_all(engine)
