from datetime import datetime
import json
from app import db
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
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    
    # Relationships
    role = db.relationship('Role', backref='users')
    sales = db.relationship('Sale', backref='cashier', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def has_role(self, role_name):
        return self.role.name == role_name
    
    def __repr__(self):
        return f"<User {self.username}>"

# Product categories
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    
    # Relationships
    products = db.relationship('Product', backref='category', lazy=True)
    
    def __repr__(self):
        return f"<Category {self.name}>"

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(50), unique=True)
    barcode = db.Column(db.String(50), unique=True)
    selling_price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float, default=0.0)  # VAT rate in percentage
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    template_id = db.Column(db.Integer, db.ForeignKey('product_template.id'))
    
    # Relationships
    inventory = db.relationship('Inventory', backref='product', lazy=True)
    sale_items = db.relationship('SaleItem', backref='product', lazy=True)
    
    @hybrid_property
    def price_with_tax(self):
        return self.selling_price * (1 + self.tax_rate / 100)
    
    def generate_barcode(self):
        """Generate a unique barcode for this product."""
        import random
        
        # Use 590 as prefix (Kenya's country code would be different, this is just for example)
        prefix = "590"
        # Add random digits to make a 12-digit number (for EAN-13)
        for _ in range(9):
            prefix += str(random.randint(0, 9))
            
        # Calculate check digit
        total = 0
        for i, digit in enumerate(prefix):
            if i % 2 == 0:
                total += int(digit)
            else:
                total += int(digit) * 3
        check_digit = (10 - (total % 10)) % 10
        
        return prefix + str(check_digit)
    
    def __repr__(self):
        return f"<Product {self.name}>"

# Inventory model - tracks stock across stores
class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, default=0)
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
        return f"<Inventory {self.product_id} at {self.store_id}: {self.quantity}>"

# Sale model
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='completed')  # completed, voided, returned
    notes = db.Column(db.Text)
    
    # Foreign keys
    cashier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    
    # Relationships
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade="all, delete-orphan")
    payments = db.relationship('Payment', backref='sale', lazy=True, cascade="all, delete-orphan")
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items)
    
    @property
    def payment_status(self):
        paid_amount = sum(payment.amount for payment in self.payments)
        return "Paid" if paid_amount >= self.total_amount else "Partial" if paid_amount > 0 else "Unpaid"
    
    def __repr__(self):
        return f"<Sale {self.reference}>"

# Sale Items - individual items in a sale
class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, nullable=False)
    
    # Foreign keys
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    
    def __repr__(self):
        return f"<SaleItem {self.product_id} x {self.quantity}>"

# Customer model
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(255))
    loyalty_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    sales = db.relationship('Sale', backref='customer', lazy=True)
    
    def __repr__(self):
        return f"<Customer {self.name}>"

# Payment model
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, mpesa, card
    reference = db.Column(db.String(100))  # e.g., M-Pesa transaction ID
    status = db.Column(db.String(20), default='completed')  # completed, pending, failed
    
    # Foreign keys
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    
    def __repr__(self):
        return f"<Payment {self.payment_method}: {self.amount}>"

# Supplier model
class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
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
    description_template = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    
    # Relationships
    products = db.relationship('Product', backref='template', lazy=True)
    
    @property
    def products_count(self):
        return Product.query.filter_by(template_id=self.id).count()
    
    def __repr__(self):
        return f"<ProductTemplate {self.name}>"

# Label template model
class LabelTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    config = db.Column(db.Text)  # JSON configuration for the label
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    user = db.relationship('User', backref='label_templates')
    
    @property
    def config_dict(self):
        """Return the config as a dictionary."""
        if self.config:
            return json.loads(self.config)
        return {}
    
    def __repr__(self):
        return f"<LabelTemplate {self.name}>"
