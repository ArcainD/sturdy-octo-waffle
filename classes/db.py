import sqlalchemy as sa
from sqlalchemy import ForeignKey, PrimaryKeyConstraint, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from classes.vkapi import ApiUser
from classes.vkapi_cons import RATINGS

Base = declarative_base()


class Clients(Base):
    __tablename__ = 'clients'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    vk_id = sa.Column(sa.String(20), unique=True, nullable=False)
    fname = sa.Column(sa.String(300), nullable=False)
    lname = sa.Column(sa.String(300))
    domain = sa.Column(sa.String(50))
    country_id = sa.Column(sa.Integer)
    country_name = sa.Column(sa.String(100))
    city_id = sa.Column(sa.Integer)
    city_name = sa.Column(sa.String(200))
    hometown = sa.Column(sa.String(300))
    birth_date = sa.Column(sa.TIMESTAMP(timezone=True))
    birth_day = sa.Column(sa.Integer)
    birth_month = sa.Column(sa.Integer)
    birth_year = sa.Column(sa.Integer)
    sex_id = sa.Column(sa.Integer)
    updated = sa.Column(sa.TIMESTAMP(timezone=True), default=func.now())
    rated_users = relationship('Users', secondary='clients_users')
    tagged_photos = relationship('Photos', secondary='clients_userphotos')

    def convert_to_apiuser(self, rating_id=RATINGS['new']) -> ApiUser:
        bdate = [str(self.birth_day) if self.birth_day is not None else '',
                 str(self.birth_month) if self.birth_month is not None else '',
                 str(self.birth_year) if self.birth_year is not None else '']
        row = {'id': self.vk_id,
               'first_name': self.fname,
               'last_name': self.lname,
               'sex': self.sex_id,
               'country': {
                   'id': self.country_id,
                   'title': self.country_name
               },
               'last_seen': {
                   'time': None,
               },
               'domain': self.domain,
               'bdate': '.'.join(bdate),
               }
        return ApiUser(row, rating_id=rating_id)


class Users(Base):
    __tablename__ = 'users'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    vk_id = sa.Column(sa.String(20), unique=True, nullable=False)
    fname = sa.Column(sa.String(300), nullable=False)
    lname = sa.Column(sa.String(300))
    domain = sa.Column(sa.String(50))
    country_id = sa.Column(sa.Integer)
    country_name = sa.Column(sa.String(100))
    city_id = sa.Column(sa.Integer)
    city_name = sa.Column(sa.String(200))
    hometown = sa.Column(sa.String(300))
    birth_date = sa.Column(sa.TIMESTAMP(timezone=True))
    birth_day = sa.Column(sa.Integer)
    birth_month = sa.Column(sa.Integer)
    birth_year = sa.Column(sa.Integer)
    sex_id = sa.Column(sa.Integer)
    updated = sa.Column(sa.TIMESTAMP(timezone=True), default=func.now())
    raters = relationship('Clients', secondary='clients_users')
    searches = relationship('Searches', secondary='searches_users')

    def convert_to_apiuser(self, rating_id=RATINGS['new']) -> ApiUser:
        bdate = [str(self.birth_day) if self.birth_day is not None else '',
                 str(self.birth_month) if self.birth_month is not None else '',
                 str(self.birth_year) if self.birth_year is not None else '']
        row = {'id': self.vk_id,
               'first_name': self.fname,
               'last_name': self.lname,
               'sex': self.sex_id,
               'country': {
                   'id': self.country_id,
                   'title': self.country_name
               },
               'last_seen': {
                   'time': None,
               },
               'domain': self.domain,
               'bdate': '.'.join(bdate),
               }
        return ApiUser(row, rating_id=rating_id)


class ClientsUsers(Base):
    __tablename__ = 'clients_users'
    __table_args__ = (PrimaryKeyConstraint('client_id', 'user_id'),)
    client_id = sa.Column(sa.Integer, ForeignKey('clients.id',
                                                 ondelete='CASCADE'))
    user_id = sa.Column(sa.Integer, ForeignKey('users.id', ondelete='CASCADE'))
    rating_id = sa.Column(sa.Integer)
    updated = sa.Column(sa.TIMESTAMP(timezone=True), default=func.now())

    def __init__(self, client_id=None, user_id=None, rating_id=None,
                 updated=func.now()):
        self.client_id = client_id
        self.user_id = user_id
        self.rating_id = rating_id
        self.updated = updated


class Photos(Base):
    __tablename__ = 'photos'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    url = sa.Column(sa.String(2048))
    likes_count = sa.Column(sa.Integer)
    comments_count = sa.Column(sa.Integer)
    reposts_count = sa.Column(sa.Integer)
    photo_id = sa.Column(sa.String(20), nullable=False)
    owner_id = sa.Column(sa.Integer, ForeignKey('users.id'), nullable=False)
    updated = sa.Column(sa.TIMESTAMP(timezone=True), default=func.now())
    tagged_clients = relationship('Clients', secondary='clients_userphotos')

    def __init__(self, url=None, likes_count=None, comments_count=None,
                 photo_id=None, owner_db_id=None, reposts_count=None,
                 updated=func.now()):
        self.url = url
        self.likes_count = likes_count
        self.comments_count = comments_count
        self.reposts_count = reposts_count
        self.photo_id = photo_id
        self.owner_id = owner_db_id
        self.updated = updated


class ClientsUserPhotos(Base):
    __tablename__ = 'clients_userphotos'
    __table_args__ = (PrimaryKeyConstraint('client_id', 'photo_id'),)
    client_id = sa.Column(sa.Integer, ForeignKey('clients.id',
                                                 ondelete='CASCADE'))
    photo_id = sa.Column(sa.Integer, ForeignKey('photos.id',
                                                ondelete='CASCADE'))


class Searches(Base):
    __tablename__ = 'searches'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    client_id = sa.Column(sa.Integer, ForeignKey('clients.id'), nullable=False)
    min_age = sa.Column(sa.Integer)
    max_age = sa.Column(sa.Integer)
    sex_id = sa.Column(sa.Integer)
    status_id = sa.Column(sa.Integer)
    city_id = sa.Column(sa.Integer)
    city_name = sa.Column(sa.String(100))
    updated = sa.Column(sa.TIMESTAMP(timezone=True), default=func.now())
    found_users = relationship('Users', secondary='searches_users')


class SearchesUsers(Base):
    __tablename__ = 'searches_users'
    __table_args__ = (PrimaryKeyConstraint('search_id', 'user_id'),)
    search_id = sa.Column(sa.Integer, ForeignKey(
        'searches.id', ondelete='CASCADE'), nullable=False)
    user_id = sa.Column(sa.Integer, ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False)
