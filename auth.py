from functools import wraps
from flask import session, redirect, url_for, flash, g, request
import logging

from app import db
from models import User, Role

def login_required(view):
    """Decorator to ensure user is logged in."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    """Decorator to ensure user has admin role."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        
        # Check if user is admin
        if session.get('role') != Role.ADMIN:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('dashboard'))
            
        return view(**kwargs)
    return wrapped_view

def manager_required(view):
    """Decorator to ensure user has manager or admin role."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        
        # Check if user is manager or admin
        if session.get('role') not in [Role.ADMIN, Role.MANAGER]:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('pos'))
            
        return view(**kwargs)
    return wrapped_view


def not_cashier_required(view):
    """Decorator to ensure user is not a cashier (employee)."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        
        # Check if user is anything but cashier/employee
        if session.get('role') == Role.EMPLOYEE:
            flash('Employees do not have access to this area.', 'danger')
            return redirect(url_for('pos'))
            
        return view(**kwargs)
    return wrapped_view

def register_user(username, email, password, first_name, last_name, phone, role_id, store_id):
    """Register a new user."""
    try:
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role_id=role_id,
            store_id=store_id,
            is_active=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        return user
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error registering user: {str(e)}")
        raise

def authenticate_user(username, password):
    """Authenticate a user by username and password."""
    try:
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and user.check_password(password):
            return user
        
        return None
    except Exception as e:
        logging.error(f"Error authenticating user: {str(e)}")
        return None

def load_logged_in_user():
    """Load user details into flask g object if logged in."""
    user_id = session.get('user_id')
    
    if user_id is None:
        g.user = None
    else:
        try:
            g.user = User.query.get(user_id)
        except Exception:
            g.user = None
