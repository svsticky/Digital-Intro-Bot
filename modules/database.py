import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

database = "sqlite:///data/database.sqlite"

SQLAlchemyBase = declarative_base()
engine = sa.create_engine(database, echo=False)
Session = sessionmaker(bind=engine)

#TODO: build database management functions to be called from elsewhere

def getFirst(table, column, value):
    session = Session()
    return_value = session.query(table).filter_by(**{column: value}).first()
    session.close()
    return return_value

def getAll(table, column, value):
    session = Session()
    return_value = session.query(table).filter_by(**{column: value}).all()
    session.close()
    return return_value

def dbInsert(db_object):
    """Inserts object"""
    if(db_object):
        session = Session()
        session.add(db_object)
        session.commit()
        session.close()

def dbMerge(db_object):
    """Updates object"""
    if(db_object):
        session = Session()
        session.merge(db_object)
        session.commit()
        session.close()

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
    name = sa.Column(sa.String(50))
    info = sa.Column(sa.String(50))
    members = relationship("CommitteeUser")
    occupied = sa.Column(sa.Boolean, default=False)


class MentorGroup(SQLAlchemyBase):
    __tablename__ = 'mentor_group'
    mg_id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50))
    parents = relationship("MentorUser")
    occupied = sa.Column(sa.Boolean, default=False)


class Visit(SQLAlchemyBase):
    __tablename__ = 'mentorgroup'
    visit_id = sa.Column(sa.Integer, primary_key=True)
    mg_id = sa.Column(sa.String(50), index=True)
    committee_id = sa.Column(sa.String(50))
    visited = sa.Column(sa.Boolean, default=False)


@event.listens_for(User, 'mapper_configured')
def receive_mapper_configured(mapper, class_):
    # to prevent 'incompatible polymorphic identity' warning, not mandatory
    mapper._validate_polymorphic_identity = None

SQLAlchemyBase.metadata.create_all(engine)
