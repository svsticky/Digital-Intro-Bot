import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

database = "sqlite:///data/database.sqlite"

SQLAlchemyBase = declarative_base()
engine = sa.create_engine(database, echo=False)
Session = sessionmaker(bind=engine)

#TODO: build database management functions to be called from elsewhere

#TODO: build database tables

class User(SQLAlchemyBase):
    __tablename__ = 'user'
    user_id = sa.Column(sa.Integer, primary_key=True)
    user_teams_id = sa.Column(sa.String, index=True)
    name = sa.Column(sa.String)

    __mapper_args__ = {
        'polymorphic_identity':'user',
        'polymorphic_on':type
    }


class CommitteeUser(SQLAlchemyBase):
    __tablename__ = 'committee_user'
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.user_id'), primary_key=True)
    committee_id = sa.Column(sa.Integer, sa.ForeignKey('committee.committee_id'))


class MentorUser(SQLAlchemyBase):
    __tablename__ = 'mentor_user'
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.user_id'), primary_key=True)
    mg_id = sa.Column(sa.Integer, sa.ForeignKey('mentor_group.mg_id'))


class IntroUser(SQLAlchemyBase):
    __tablename__ = 'intro_user'
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.user_id'), primary_key=True)


class Committee(SQLAlchemyBase):
    __tablename__ = 'committee'
    committee_id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)
    info = sa.Column(sa.String)
    channel_id = sa.Column(sa.String)
    members = relationship("CommitteeUser")
    occupied = sa.Column(sa.Boolean, default=False)


class MentorGroup(SQLAlchemyBase):
    __tablename__ = 'mentor_group'
    mg_id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)
    channel_id = sa.Column(sa.String)
    parents = relationship("MentorUser")
    occupied = sa.Column(sa.Boolean, default=False)


class Visit(SQLAlchemyBase):
    __tablename__ = 'mentorgroup'
    mg_id = sa.Column(sa.String, index=True)
    committee_id = sa.Column(sa.String)
    visited = sa.Column(sa.Boolean, default=False)


SQLAlchemyBase.metadata.create.all(engine)
