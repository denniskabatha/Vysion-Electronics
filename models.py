# /home/mwangidennis/CloudSalesPOS/models.py
from datetime import datetime
import json
from extensions import db # CHANGED: Import db from extensions.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.ext.hybrid import hybrid_property

# User roles table for role-based access control
class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))

    # Define standard roles
    ADMIN = "admin"
    MANAGER = "manager"
    CASHIER = "cashier"
    EMPLOYEE = "employee"

    def __repr__(self):
        return f"<Role {self.name}>"

# Store model (for multi-branch support)
class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    users = db.relationship('User', backref='store', lazy=True)
    inventory = db.relationship('Inventory', backref='store', lazy=True)
    sales = db.relationship('Sale', backref='store', lazy=True)
    # Added missing relationship from HardwareConfiguration backref
    hardware_configurations = db.relationship('HardwareConfiguration', backref='store', lazy=True)


    def __repr__(self):
        return f"<Store {self.name}>"

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Foreign keys
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=True) # Made nullable as per common practice, adjust if strictly required

    # Relationships
    role = db.relationship('Role', backref='users')
    sales = db.relationship('Sale', backref='cashier', lazy=True)
    # Added missing relationship from LabelTemplate backref
    label_templates = db.relationship('LabelTemplate', backref='user', lazy=True)


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def has_role(self, role_name):
        return self.role.name == role_name

    def __repr__(self):
        return f"<User {self.username}>"

# Product categories
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # Added unique=True for category names
    description = db.Column(db.String(255))

    # Relationships
    products = db.relationship('Product', backref='category', lazy=True)
    product_templates = db.relationship('ProductTemplate', backref='category', lazy=True) # Added relationship


    def __repr__(self):
        return f"<Category {self.name}>"

# Supplier model
class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # Added unique=True
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    products = db.relationship('Product', backref='supplier', lazy=True)
    product_templates = db.relationship('ProductTemplate', backref='supplier', lazy=True)

    def __repr__(self):
        return f"<Supplier {self.name}>"

# Product template model
class ProductTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    tax_rate = db.Column(db.Float, default=16.0)  # Default to standard KRA VAT rate
    reorder_level = db.Column(db.Integer, default=5)
    sku_prefix = db.Column(db.String(20))
    # description_template = db.Column(db.String(255)) # This was commented out in original, keeping it so
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign keys
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))

    # Relationship to Product (Many-to-One from Product to ProductTemplate)
    # This implies a Product has one Template. If one Template can have many Products:
    products = db.relationship('Product', backref='template', lazy=True)


    @property
    def products_count(self):
        return len(self.products) # Now correctly counts associated products

    def __repr__(self):
        return f"<ProductTemplate {self.name}>"

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(50), unique=True, nullable=True) # Allow SKU to be nullable initially
    barcode = db.Column(db.String(50), unique=True, nullable=True) # Allow barcode to be nullable initially
    selling_price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, nullable=True) # Allow cost price to be nullable
    tax_rate = db.Column(db.Float, default=0.0)  # VAT rate in percentage
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign keys
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    template_id = db.Column(db.Integer, db.ForeignKey('product_template.id'), nullable=True) # Added template_id

    # Relationships
    inventory = db.relationship('Inventory', backref='product', lazy=True, uselist=False) # One-to-one for a specific store in Inventory table
    sale_items = db.relationship('SaleItem', backref='product', lazy=True)

    @hybrid_property
    def price_with_tax(self):
        return self.selling_price * (1 + self.tax_rate / 100)

    def generate_barcode(self):
        """Generate a unique barcode for this product."""
        import random

        # Use 616 as prefix (GS1 Kenya)
        prefix = "616" # Corrected GS1 prefix for Kenya
        # Add random digits to make a 12-digit number (for EAN-13)
        # Needs 9 more digits for the item reference part
        for _ in range(9):
            prefix += str(random.randint(0, 9))

        # Calculate check digit
        total = 0
        for i, digit_char in enumerate(prefix):
            digit = int(digit_char)
            if (i + 1) % 2 != 0: # Odd position (1st, 3rd, ...)
                total += digit
            else: # Even position (2nd, 4th, ...)
                total += digit * 3
        check_digit = (10 - (total % 10)) % 10

        return prefix + str(check_digit)

    def __repr__(self):
        return f"<Product {self.name}>"

# Inventory model - tracks stock across stores
class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, default=0, nullable=False)
    reorder_level = db.Column(db.Integer, default=5)
    last_restock_date = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign keys
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)

    # Unique constraint for product-store combination
    __table_args__ = (db.UniqueConstraint('product_id', 'store_id', name='_product_store_uc'),)

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    def __repr__(self):
        return f"<Inventory ProductID:{self.product_id} StoreID:{self.store_id} Qty:{self.quantity}>"


# Customer model
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True) # Added unique=True, made nullable
    email = db.Column(db.String(100), unique=True, nullable=True) # Added unique=True, made nullable
    address = db.Column(db.String(255))
    loyalty_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sales = db.relationship('Sale', backref='customer', lazy=True)

    def __repr__(self):
        return f"<Customer {self.name}>"


# Sale model
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float, default=0.0, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0, nullable=False)
    discount_amount = db.Column(db.Float, default=0.0, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='completed', nullable=False)  # completed, voided, returned
    notes = db.Column(db.Text)

    # Foreign keys
    cashier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True) # Allow anonymous sales
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)

    # Relationships
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade="all, delete-orphan")
    payments = db.relationship('Payment', backref='sale', lazy=True, cascade="all, delete-orphan")

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items)

    @property
    def payment_status(self):
        paid_amount = sum(payment.amount for payment in self.payments if payment.status == 'completed')
        if paid_amount >= self.total_amount:
            return "Paid"
        elif paid_amount > 0:
            return "Partial"
        else:
            return "Unpaid"

    def __repr__(self):
        return f"<Sale {self.reference}>"

# Sale Items - individual items in a sale
class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False) # Price at the time of sale, before tax/discount per item
    tax_rate_applied = db.Column(db.Float, default=0.0, nullable=False) # Tax rate applied to this item
    discount_amount_applied = db.Column(db.Float, default=0.0, nullable=False) # Discount specifically for this item line
    # total_price should be (quantity * unit_price * (1 + tax_rate_applied/100)) - discount_amount_applied
    # Or, more simply, store the final line total after all calculations
    line_total = db.Column(db.Float, nullable=False) # (Quantity * (UnitPrice + UnitTax)) - UnitDiscount

    # Foreign keys
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

    # Removed 'total_price' in favor of 'line_total' for clarity
    # Removed 'tax_rate', renamed to 'tax_rate_applied'
    # Renamed 'discount_amount' to 'discount_amount_applied'


    def __repr__(self):
        return f"<SaleItem ProductID:{self.product_id} x {self.quantity}>"


# Payment model
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, mpesa, card
    reference = db.Column(db.String(100))  # e.g., M-Pesa transaction ID
    status = db.Column(db.String(20), default='completed', nullable=False)  # completed, pending, failed

    # Foreign keys
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)

    def __repr__(self):
        return f"<Payment {self.payment_method}: {self.amount} ({self.status})>"


# Label template model
class LabelTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # Added unique=True
    description = db.Column(db.String(255))
    config = db.Column(db.Text)  # JSON configuration for the label
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Allow system templates

    @property
    def config_dict(self):
        """Return the config as a dictionary."""
        if self.config:
            try:
                return json.loads(self.config)
            except json.JSONDecodeError:
                return {} # Or log an error
        return {}

    def __repr__(self):
        return f"<LabelTemplate {self.name}>"


class HardwareConfiguration(db.Model):
    """
    Model for storing hardware configurations for POS peripherals.
    This model allows storing configuration for barcode scanners, receipt printers,
    cash drawers, card readers, and other hardware compatible with the POS system.
    """
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False, unique=True) # One config per store

    # Hardware types
    barcode_scanner_type = db.Column(db.String(50), default='usb_hid')
    receipt_printer_type = db.Column(db.String(50), default='browser') # e.g., browser, epson_serial, star_lan
    cash_drawer_type = db.Column(db.String(50), default='manual') # e.g., manual, printer_kick
    card_reader_type = db.Column(db.String(50), default='manual') # e.g., manual, stripe_terminal

    # Communication settings
    scanner_port = db.Column(db.String(100)) # Increased length
    printer_port = db.Column(db.String(100)) # Increased length
    drawer_port = db.Column(db.String(100))  # Increased length, e.g. COM1, /dev/ttyUSB0, IP Address

    # JSON configuration for hardware-specific parameters
    scanner_config = db.Column(db.Text, default='{}')  # JSON configuration for scanner
    printer_config = db.Column(db.Text, default='{}')  # JSON configuration for printer
    drawer_config = db.Column(db.Text, default='{}')   # JSON configuration for cash drawer
    card_reader_config = db.Column(db.Text, default='{}')   # JSON configuration for card reader

    # Test and calibration status
    is_scanner_active = db.Column(db.Boolean, default=False) # Default to False until configured/tested
    is_printer_active = db.Column(db.Boolean, default=False)
    is_drawer_active = db.Column(db.Boolean, default=False)
    is_card_reader_active = db.Column(db.Boolean, default=False)

    # Last test and calibration times
    scanner_last_test = db.Column(db.DateTime)
    printer_last_test = db.Column(db.DateTime)
    drawer_last_test = db.Column(db.DateTime)
    card_reader_last_test = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship (backref already defined in Store)
    # store = db.relationship('Store', backref='hardware_configuration', uselist=False)


    @property
    def scanner_config_dict(self):
        """Return the scanner config as a dictionary."""
        if self.scanner_config:
            try:
                return json.loads(self.scanner_config)
            except json.JSONDecodeError: return {}
        return {}

    @property
    def printer_config_dict(self):
        """Return the printer config as a dictionary."""
        if self.printer_config:
            try:
                return json.loads(self.printer_config)
            except json.JSONDecodeError: return {}
        return {}

    @property
    def drawer_config_dict(self):
        """Return the cash drawer config as a dictionary."""
        if self.drawer_config:
            try:
                return json.loads(self.drawer_config)
            except json.JSONDecodeError: return {}
        return {}

    @property
    def card_reader_config_dict(self):
        """Return the card reader config as a dictionary."""
        if self.card_reader_config:
            try:
                return json.loads(self.card_reader_config)
            except json.JSONDecodeError: return {}
        return {}

    def set_scanner_config(self, config_dict):
        """Set scanner configuration from a dict."""
        self.scanner_config = json.dumps(config_dict)

    def set_printer_config(self, config_dict):
        """Set printer configuration from a dict."""
        self.printer_config = json.dumps(config_dict)

    def set_drawer_config(self, config_dict):
        """Set cash drawer configuration from a dict."""
        self.drawer_config = json.dumps(config_dict)

    def set_card_reader_config(self, config_dict):
        """Set card reader configuration from a dict."""
        self.card_reader_config = json.dumps(config_dict)

    def __repr__(self):
        return f"<HardwareConfiguration {self.id} for Store {self.store_id}>"