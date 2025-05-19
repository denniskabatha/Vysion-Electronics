# /home/mwangidennis/CloudSalesPOS/extensions.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Define base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy instance.
# Models will import this 'db' object.
# The Flask app will be initialized with it later using db.init_app(app).
db = SQLAlchemy(model_class=Base)