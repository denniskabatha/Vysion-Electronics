# /home/mwangidennis/CloudSalesPOS/app.py
import os
import json
import logging
import time
from datetime import timedelta
from flask import Flask, request, abort
# Remove: from flask_sqlalchemy import SQLAlchemy  # SQLAlchemy itself is now initialized in extensions
# Remove: from sqlalchemy.orm import DeclarativeBase # Base class is now in extensions
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from werkzeug.middleware.proxy_fix import ProxyFix
import functools

# Import db instance from extensions.py
from extensions import db # ADD THIS LINE

# Configure logging
logging.basicConfig(level=logging.INFO)

# Simple in-memory rate limiter
class RateLimiter:
    def __init__(self, max_requests=100, window_seconds=60):
        self.max_requests = max_requests  # Max requests per window
        self.window_seconds = window_seconds  # Window size in seconds
        self.requests = {}  # {ip: [(timestamp, count), ...]}

    def is_rate_limited(self, ip):
        now = time.time()

        # Remove expired entries
        if ip in self.requests:
            self.requests[ip] = [r for r in self.requests[ip]
                                 if now - r[0] < self.window_seconds]
        else:
            self.requests[ip] = []

        # Count recent requests
        total = sum(r[1] for r in self.requests[ip])

        if total >= self.max_requests:
            return True

        # Record this request
        self.requests[ip].append((now, 1))
        return False

# REMOVE THIS BLOCK - It's now in extensions.py
# # Define base class for SQLAlchemy models
# class Base(DeclarativeBase):
#     pass
#
# # Initialize SQLAlchemy
# db = SQLAlchemy(model_class=Base)

# Create Flask application
app = Flask(__name__)

# Set secret key from environment variable
app.secret_key = os.environ.get("SESSION_SECRET", "kenya_pos_default_secret_key")

# Configure proxy fix middleware for proper URL generation
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Security settings
app.config['SESSION_COOKIE_SECURE'] = True  # Only send cookies over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Restrict cookie sending to same site
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)  # Session timeout

# Create rate limiter for sensitive routes
login_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10 login attempts per minute
api_limiter = RateLimiter(max_requests=200, window_seconds=60)  # 200 API requests per minute

# Configure database connection - using SQLite for simplicity
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///kenyan_pos.db"

# Set SQLAlchemy options
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True  # Verify connections before use
}

# SQLite-specific connection arguments
# This correctly merges with the previous SQLALCHEMY_ENGINE_OPTIONS
app.config["SQLALCHEMY_ENGINE_OPTIONS"].update({
    "connect_args": {"check_same_thread": False}  # Allow access from multiple threads for SQLite
})


# Load KRA eTIMS settings if configuration file exists
etims_config_file = os.path.join('instance', 'config.json')
if os.path.exists(etims_config_file):
    try:
        with open(etims_config_file, 'r') as f:
            etims_config = json.load(f)

        # Apply eTIMS configuration to app
        app.config.update({
            'ENABLE_TIMS': etims_config.get('ENABLE_TIMS', False),
            'TAX_PIN': etims_config.get('TAX_PIN', ''),
            'TIMS_DEVICE_ID': etims_config.get('TIMS_DEVICE_ID', ''),
            'TIMS_CERT_SERIAL': etims_config.get('TIMS_CERT_SERIAL', ''),
            'VAT_REGISTRATION_DATE': etims_config.get('VAT_REGISTRATION_DATE', ''),
            'TIMS_URL': etims_config.get('TIMS_URL', 'https://etims.kra.go.ke/api/v1/'),
            'ENABLE_QR_CODE': etims_config.get('ENABLE_QR_CODE', True),
            'DEFAULT_TAX_RATE': etims_config.get('DEFAULT_TAX_RATE', 16.0)
        })

        # Check for certificate file
        cert_path = os.path.join('instance', 'etims_certificate.p12')
        if os.path.exists(cert_path):
            app.config['TIMS_CERTIFICATE_PATH'] = cert_path

        logging.info("KRA eTIMS configuration loaded successfully")
    except Exception as e:
        logging.error(f"Failed to load KRA eTIMS configuration: {str(e)}")
else:
    # Set default eTIMS configuration
    app.config.update({
        'ENABLE_TIMS': False,
        'TAX_PIN': '',
        'TIMS_DEVICE_ID': '',
        'TIMS_CERT_SERIAL': '',
        'VAT_REGISTRATION_DATE': '',
        'TIMS_URL': 'https://etims.kra.go.ke/api/v1/',
        'ENABLE_QR_CODE': True,
        'DEFAULT_TAX_RATE': 16.0
    })
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Note: SQLALCHEMY_ENGINE_OPTIONS was already set and updated.
# The following would overwrite the pool_pre_ping if it wasn't merged correctly above.
# Ensured above that connect_args is added to the existing dictionary.
# app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
#     "connect_args": {"check_same_thread": False},
#     "pool_pre_ping": True, # This was already set
# }

# Initialize JWT for authentication
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", app.secret_key)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=86400) # 24 hours, ensure timedelta for consistency

# Initialize database with app (db is now the imported instance)
db.init_app(app)

# Initialize migrations
migrate = Migrate(app, db)

# Import routes after app is created to avoid circular imports
with app.app_context():
    # Import models so they are registered with SQLAlchemy
    # This will work now because models.py imports 'db' from 'extensions.py'
    from models import User, Role, Store, Product, Category, Inventory, Sale, SaleItem, Customer, Payment, Supplier, ProductTemplate, LabelTemplate, HardwareConfiguration
    # Added missing models to the import list based on models.py

    # Create all tables if they don't exist
    db.create_all()

    # Import routes after DB initialization
    from routes import register_routes
    register_routes(app)

# Configure M-Pesa credentials
app.config["MPESA_CONSUMER_KEY"] = os.environ.get("MPESA_CONSUMER_KEY", "")
app.config["MPESA_CONSUMER_SECRET"] = os.environ.get("MPESA_CONSUMER_SECRET", "")
app.config["MPESA_SHORTCODE"] = os.environ.get("MPESA_SHORTCODE", "")
app.config["MPESA_PASSKEY"] = os.environ.get("MPESA_PASSKEY", "")
app.config["MPESA_CALLBACK_URL"] = os.environ.get("MPESA_CALLBACK_URL", "")
app.config["MPESA_ENVIRONMENT"] = os.environ.get("MPESA_ENVIRONMENT", "sandbox")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)