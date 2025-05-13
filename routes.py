from flask import render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid
import logging
import csv
import io
import json
import random
import os

from app import db
from models import (
    User, Role, Store, Product, Category, Inventory,
    Sale, SaleItem, Customer, Payment, Supplier,
    ProductTemplate, LabelTemplate
)
from auth import (
    login_required, admin_required, manager_required, not_cashier_required,
    register_user, authenticate_user, load_logged_in_user
)
from mpesa import initiate_stk_push, check_transaction_status

def register_routes(app):
    """Register all application routes."""
    
    # Register authentication middleware
    app.before_request(load_logged_in_user)
    
    # Home route
    @app.route('/')
    def home():
        if session.get('user_id'):
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    
    # Authentication routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = authenticate_user(username, password)
            
            if user:
                session.clear()
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role.name
                session['store_id'] = user.store_id
                
                # Update last login time
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                # If user is a cashier/employee, redirect to POS; otherwise to dashboard
                if user.role.name == Role.EMPLOYEE:
                    return redirect(url_for('pos'))
                else:
                    return redirect(url_for('dashboard'))
            
            flash('Invalid username or password', 'danger')
        
        return render_template('login.html')
    
    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))
    
    @app.route('/register', methods=['GET', 'POST'])
    @admin_required
    def register():
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            phone = request.form.get('phone')
            role_id = request.form.get('role_id')
            store_id = request.form.get('store_id')
            
            error = None
            
            if not username or not email or not password or not role_id or not store_id:
                error = 'All fields are required.'
            elif User.query.filter_by(username=username).first():
                error = f'User {username} is already registered.'
            elif User.query.filter_by(email=email).first():
                error = f'Email {email} is already registered.'
            
            if error is None:
                try:
                    user = register_user(username, email, password, first_name, last_name, phone, role_id, store_id)
                    flash(f'User {username} created successfully!', 'success')
                    return redirect(url_for('users'))
                except Exception as e:
                    error = str(e)
            
            flash(error, 'danger')
        
        roles = Role.query.all()
        stores = Store.query.all()
        return render_template('users/user_form.html', roles=roles, stores=stores)
    
    # Dashboard
    @app.route('/dashboard')
    @login_required
    @not_cashier_required
    def dashboard():
        store_id = session.get('store_id')
        
        # Get today's sales
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        today_sales = Sale.query.filter(
            Sale.store_id == store_id,
            Sale.sale_date >= today,
            Sale.sale_date < tomorrow,
            Sale.status == 'completed'
        ).all()
        
        # Get low stock items
        low_stock_items = (
            db.session.query(Product, Inventory)
            .join(Inventory, Product.id == Inventory.product_id)
            .filter(
                Inventory.store_id == store_id,
                Inventory.quantity <= Inventory.reorder_level
            )
            .all()
        )
        
        # Summary statistics
        today_sales_count = len(today_sales)
        today_sales_amount = sum(sale.total_amount for sale in today_sales)
        low_stock_count = len(low_stock_items)
        
        # Get recent sales
        recent_sales = (
            Sale.query
            .filter(Sale.store_id == store_id, Sale.status == 'completed')
            .order_by(Sale.sale_date.desc())
            .limit(5)
            .all()
        )
        
        return render_template(
            'dashboard.html',
            today_sales_count=today_sales_count,
            today_sales_amount=today_sales_amount,
            low_stock_count=low_stock_count,
            recent_sales=recent_sales,
            low_stock_items=low_stock_items
        )
    
    # POS routes
    @app.route('/pos')
    @login_required
    def pos():
        store_id = session.get('store_id')
        
        # Get all products with inventory for the current store
        products = (
            db.session.query(Product, Inventory)
            .join(Inventory, Product.id == Inventory.product_id)
            .filter(Inventory.store_id == store_id, Product.is_active == True)
            .all()
        )
        
        categories = Category.query.all()
        customers = Customer.query.all()
        
        return render_template(
            'pos/index.html', 
            products=products,
            categories=categories,
            customers=customers
        )
    
    @app.route('/pos/checkout', methods=['POST'])
    @login_required
    def checkout():
        data = request.json
        items = data.get('items', [])
        customer_id = data.get('customer_id')
        payment_method = data.get('payment_method')
        total_amount = data.get('total_amount')
        
        if not items or not total_amount:
            return jsonify({'success': False, 'message': 'No items in cart'}), 400
        
        try:
            # Generate unique reference number
            reference = f"SALE-{uuid.uuid4().hex[:8].upper()}"
            
            # Create new sale
            sale = Sale(
                reference=reference,
                cashier_id=session.get('user_id'),
                customer_id=customer_id,
                store_id=session.get('store_id'),
                subtotal=data.get('subtotal', 0),
                tax_amount=data.get('tax_amount', 0),
                discount_amount=data.get('discount_amount', 0),
                total_amount=total_amount,
                status='completed'
            )
            db.session.add(sale)
            db.session.flush()  # Get the sale ID without committing
            
            # Add sale items
            for item in items:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=item['product_id'],
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                    tax_rate=item.get('tax_rate', 0),
                    discount_amount=item.get('discount_amount', 0),
                    total_price=item['total_price']
                )
                db.session.add(sale_item)
                
                # Update inventory
                inventory = Inventory.query.filter_by(
                    product_id=item['product_id'],
                    store_id=session.get('store_id')
                ).first()
                
                if inventory:
                    inventory.quantity -= item['quantity']
            
            # Handle payment
            payment_success = True
            payment_reference = None
            
            if payment_method == 'mpesa':
                # For M-Pesa, we'll return the sale ID and let the frontend handle the STK push
                payment_success = False  # Will be completed asynchronously
                
            elif payment_method in ['cash', 'card']:
                # Add payment record
                payment = Payment(
                    sale_id=sale.id,
                    amount=total_amount,
                    payment_method=payment_method,
                    status='completed'
                )
                db.session.add(payment)
            
            # Only commit if non-M-Pesa or if M-Pesa is just saved as pending
            db.session.commit()
            
            # Get the cashier's name for the receipt
            cashier = User.query.get(session.get('user_id'))
            cashier_name = cashier.full_name if cashier else "Unknown"
            
            return jsonify({
                'success': True,
                'sale_id': sale.id,
                'reference': sale.reference,
                'payment_success': payment_success,
                'payment_reference': payment_reference,
                'cashier_name': cashier_name
            })
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Checkout error: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/pos/mpesa-payment', methods=['POST'])
    @login_required
    def mpesa_payment():
        data = request.json
        sale_id = data.get('sale_id')
        phone = data.get('phone')
        amount = data.get('amount')
        
        if not sale_id or not phone or not amount:
            return jsonify({'success': False, 'message': 'Missing required parameters'}), 400
        
        try:
            sale = Sale.query.get(sale_id)
            if not sale:
                return jsonify({'success': False, 'message': 'Sale not found'}), 404
            
            # Initiate STK Push
            response = initiate_stk_push(phone, amount, sale.reference)
            
            if response.get('ResponseCode') == '0':
                # STK push initiated successfully
                checkout_request_id = response.get('CheckoutRequestID')
                
                # Create pending payment
                payment = Payment(
                    sale_id=sale_id,
                    amount=amount,
                    payment_method='mpesa',
                    reference=checkout_request_id,
                    status='pending'
                )
                db.session.add(payment)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'M-Pesa payment initiated',
                    'checkout_request_id': checkout_request_id
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f"M-Pesa error: {response.get('ResponseDescription', 'Unknown error')}"
                }), 400
                
        except Exception as e:
            db.session.rollback()
            logging.error(f"M-Pesa payment error: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/pos/mpesa-callback', methods=['POST'])
    def mpesa_callback():
        data = request.json
        
        try:
            result = data.get('Body', {}).get('stkCallback', {})
            result_code = result.get('ResultCode')
            checkout_request_id = result.get('CheckoutRequestID')
            
            if not checkout_request_id:
                return jsonify({'success': False, 'message': 'Invalid callback data'}), 400
            
            # Find the payment
            payment = Payment.query.filter_by(reference=checkout_request_id).first()
            
            if not payment:
                return jsonify({'success': False, 'message': 'Payment not found'}), 404
            
            if result_code == 0:
                # Payment successful
                payment.status = 'completed'
                db.session.commit()
                return jsonify({'success': True})
            else:
                # Payment failed
                payment.status = 'failed'
                db.session.commit()
                return jsonify({'success': False, 'message': result.get('ResultDesc', 'Payment failed')})
                
        except Exception as e:
            logging.error(f"M-Pesa callback error: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/pos/check-payment-status/<checkout_request_id>')
    @login_required
    def check_payment_status(checkout_request_id):
        try:
            # First check our database
            payment = Payment.query.filter_by(reference=checkout_request_id).first()
            
            if not payment:
                return jsonify({'success': False, 'message': 'Payment not found'}), 404
            
            if payment.status in ['completed', 'failed']:
                return jsonify({
                    'success': True,
                    'status': payment.status,
                    'is_complete': True
                })
            
            # If still pending, check with M-Pesa
            response = check_transaction_status(checkout_request_id)
            
            if response.get('ResultCode') == '0':
                # Update payment status
                payment.status = 'completed'
                db.session.commit()
                return jsonify({
                    'success': True,
                    'status': 'completed',
                    'is_complete': True
                })
            else:
                return jsonify({
                    'success': True,
                    'status': 'pending',
                    'is_complete': False
                })
                
        except Exception as e:
            logging.error(f"Check payment status error: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # Inventory routes
    @app.route('/inventory')
    @login_required
    @not_cashier_required
    def inventory():
        store_id = session.get('store_id')
        
        inventory_items = (
            db.session.query(Product, Inventory, Category)
            .join(Inventory, Product.id == Inventory.product_id)
            .outerjoin(Category, Product.category_id == Category.id)
            .filter(Inventory.store_id == store_id)
            .all()
        )
        
        return render_template('inventory/index.html', inventory_items=inventory_items)
    
    @app.route('/inventory/add', methods=['GET', 'POST'])
    @manager_required
    def add_product():
        if request.method == 'POST':
            # Check if this is a bulk upload
            if 'bulk_upload' in request.form:
                if 'bulk_file' not in request.files:
                    flash('No file part', 'danger')
                    return redirect(request.url)
                    
                file = request.files['bulk_file']
                
                if file.filename == '':
                    flash('No selected file', 'danger')
                    return redirect(request.url)
                    
                if file and file.filename.endswith('.csv'):
                    # Process the CSV file
                    try:
                        # Parse CSV
                        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                        csv_reader = csv.reader(stream)
                        
                        # Skip header row if indicated
                        if request.form.get('header_row'):
                            next(csv_reader)
                            
                        # Process each row
                        products_added = 0
                        errors = []
                        skipped = 0
                        
                        # Cache data to minimize database queries
                        categories_cache = {category.name.lower(): category.id for category in Category.query.all()}
                        existing_skus = {product.sku for product in Product.query.with_entities(Product.sku).all() if product.sku}
                        existing_barcodes = {product.barcode for product in Product.query.with_entities(Product.barcode).all() if product.barcode}
                        
                        # Process in batches for better performance
                        batch_size = 100
                        batch = []
                        
                        store_id = session.get('store_id')
                        default_supplier = Supplier.query.first()
                        default_supplier_id = default_supplier.id if default_supplier else None
                        
                        for row_num, row in enumerate(csv_reader, 1):
                            try:
                                # CSV format should be: Name, Description, SKU, Barcode, Selling Price, Cost Price, Tax Rate, Category, Quantity
                                if len(row) < 5:  # At minimum we need name and selling price
                                    errors.append(f"Row {row_num}: Not enough data. Need at least Name and Selling Price.")
                                    continue
                                    
                                name = row[0].strip()
                                description = row[1].strip() if len(row) > 1 and row[1] else f"Description for {name}"
                                sku = row[2].strip() if len(row) > 2 and row[2] else f"SKU-{uuid.uuid4().hex[:8].upper()}"
                                barcode = row[3].strip() if len(row) > 3 and row[3] else None
                                
                                try:
                                    selling_price = float(row[4]) if len(row) > 4 and row[4] else 0
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid selling price '{row[4]}'")
                                    continue
                                
                                try:
                                    cost_price = float(row[5]) if len(row) > 5 and row[5] else selling_price * 0.8  # Default 20% markup
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid cost price '{row[5]}'")
                                    continue
                                
                                try:
                                    tax_rate = float(row[6]) if len(row) > 6 and row[6] else 16.0  # Default VAT rate
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid tax rate '{row[6]}'")
                                    continue
                                
                                category_name = row[7].strip() if len(row) > 7 and row[7] else None
                                
                                try:
                                    quantity = int(row[8]) if len(row) > 8 and row[8] else 0
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid quantity '{row[8]}'")
                                    continue
                                
                                # Skip rows without a product name
                                if not name:
                                    skipped += 1
                                    continue
                                    
                                # Check for duplicates if option is enabled
                                if request.form.get('skip_duplicates', 'on') == 'on':
                                    if sku and sku in existing_skus:
                                        skipped += 1
                                        continue
                                    
                                    if barcode and barcode in existing_barcodes:
                                        skipped += 1
                                        continue
                                
                                # Determine category ID
                                category_id = None
                                if category_name:
                                    category_name_lower = category_name.lower()
                                    if category_name_lower in categories_cache:
                                        category_id = categories_cache[category_name_lower]
                                    else:
                                        # Create new category if it doesn't exist
                                        new_category = Category(name=category_name)
                                        db.session.add(new_category)
                                        db.session.flush()
                                        category_id = new_category.id
                                        categories_cache[category_name_lower] = category_id
                                
                                # Generate barcode if not provided
                                if not barcode:
                                    # Generate a unique EAN-13 barcode
                                    barcode = "590"  # Example prefix for Kenya
                                    for _ in range(9):
                                        barcode += str(random.randint(0, 9))
                                    
                                    # Calculate check digit
                                    total = 0
                                    for i, digit in enumerate(barcode):
                                        total += int(digit) * (1 if i % 2 == 0 else 3)
                                    check_digit = (10 - (total % 10)) % 10
                                    barcode += str(check_digit)
                                
                                # Create product
                                product = Product(
                                    name=name,
                                    description=description,
                                    sku=sku,
                                    barcode=barcode,
                                    selling_price=selling_price,
                                    cost_price=cost_price,
                                    tax_rate=tax_rate,
                                    category_id=category_id,
                                    supplier_id=default_supplier_id,
                                    is_active=True
                                )
                                
                                # Add to batch for bulk insert
                                batch.append(product)
                                
                                # Process in batches to improve performance
                                if len(batch) >= batch_size:
                                    db.session.add_all(batch)
                                    db.session.flush()  # Get IDs without committing
                                    
                                    # Create inventory entries for each product in batch
                                    for prod in batch:
                                        inventory = Inventory(
                                            product_id=prod.id,
                                            store_id=store_id,
                                            quantity=quantity,
                                            reorder_level=5,
                                            last_restock_date=datetime.utcnow() if quantity > 0 else None
                                        )
                                        db.session.add(inventory)
                                        
                                        # Update tracking
                                        existing_skus.add(prod.sku)
                                        existing_barcodes.add(prod.barcode)
                                    
                                    products_added += len(batch)
                                    batch = []
                                
                            except Exception as e:
                                errors.append(f"Row {row_num}: {str(e)}")
                                continue
                        
                        # Process any remaining products in the last batch
                        if batch:
                            db.session.add_all(batch)
                            db.session.flush()
                            
                            # Create inventory entries for remaining products
                            for prod in batch:
                                inventory = Inventory(
                                    product_id=prod.id,
                                    store_id=store_id,
                                    quantity=quantity,
                                    reorder_level=5,
                                    last_restock_date=datetime.utcnow() if quantity > 0 else None
                                )
                                db.session.add(inventory)
                            
                            products_added += len(batch)
                        
                        # Either commit all or roll back
                        if products_added > 0:
                            db.session.commit()
                            
                            # Create detailed success message
                            success_msg = f'Successfully imported {products_added} products'
                            details = []
                            
                            if skipped > 0:
                                details.append(f"{skipped} skipped")
                            if len(errors) > 0:
                                details.append(f"{len(errors)} errors")
                                
                            if details:
                                success_msg += f" ({', '.join(details)})"
                            
                            flash(success_msg, 'success')
                        else:
                            db.session.rollback()
                            flash('No products were imported. Please check your file and try again.', 'warning')
                        
                        # Report errors with row numbers for easier reference
                        if errors:
                            for error in errors[:5]:  # Show first 5 errors
                                flash(error, 'warning')
                            if len(errors) > 5:
                                flash(f'... and {len(errors) - 5} more errors. Check the logs for details.', 'warning')
                                for error in errors:
                                    logging.error(error)
                                    
                        return redirect(url_for('inventory'))
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error importing products: {str(e)}', 'danger')
                        logging.error(f"Error importing products: {str(e)}")
                        return redirect(request.url)
                else:
                    flash('File type not supported. Please upload a CSV file.', 'danger')
                    return redirect(request.url)
            else:
                # Regular single product addition
                name = request.form.get('name')
                description = request.form.get('description', '')
                sku = request.form.get('sku')
                barcode = request.form.get('barcode')
                selling_price = request.form.get('selling_price')
                cost_price = request.form.get('cost_price')
                tax_rate = request.form.get('tax_rate', 0)
                category_id = request.form.get('category_id')
                supplier_id = request.form.get('supplier_id')
                quantity = request.form.get('quantity', 0)
                reorder_level = request.form.get('reorder_level', 5)
                
                try:
                    # Create product
                    product = Product(
                        name=name,
                        description=description,
                        sku=sku,
                        barcode=barcode,
                        selling_price=float(selling_price),
                        cost_price=float(cost_price),
                        tax_rate=float(tax_rate),
                        category_id=category_id if category_id else None,
                        supplier_id=supplier_id if supplier_id else None
                    )
                    db.session.add(product)
                    db.session.flush()  # Get product ID without committing
                    
                    # Create inventory entry for current store
                    inventory = Inventory(
                        product_id=product.id,
                        store_id=session.get('store_id'),
                        quantity=int(quantity),
                        reorder_level=int(reorder_level),
                        last_restock_date=datetime.utcnow() if int(quantity) > 0 else None
                    )
                    db.session.add(inventory)
                    db.session.commit()
                    
                    flash(f'Product {name} added successfully!', 'success')
                    return redirect(url_for('inventory'))
                    
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error adding product: {str(e)}', 'danger')
        
        categories = Category.query.all()
        suppliers = Supplier.query.all()
        return render_template(
            'inventory/product_form.html',
            categories=categories,
            suppliers=suppliers
        )
    
    @app.route('/inventory/edit/<int:product_id>', methods=['GET', 'POST'])
    @manager_required
    def edit_product(product_id):
        product = Product.query.get_or_404(product_id)
        inventory = Inventory.query.filter_by(
            product_id=product_id,
            store_id=session.get('store_id')
        ).first_or_404()
        
        if request.method == 'POST':
            try:
                # Update product
                product.name = request.form.get('name')
                product.description = request.form.get('description', '')
                product.sku = request.form.get('sku')
                product.barcode = request.form.get('barcode')
                product.selling_price = float(request.form.get('selling_price'))
                product.cost_price = float(request.form.get('cost_price'))
                product.tax_rate = float(request.form.get('tax_rate', 0))
                product.category_id = request.form.get('category_id') or None
                product.supplier_id = request.form.get('supplier_id') or None
                
                # Update inventory
                old_quantity = inventory.quantity
                new_quantity = int(request.form.get('quantity', 0))
                inventory.quantity = new_quantity
                inventory.reorder_level = int(request.form.get('reorder_level', 5))
                
                # If stock increased, update restock date
                if new_quantity > old_quantity:
                    inventory.last_restock_date = datetime.utcnow()
                
                db.session.commit()
                flash(f'Product {product.name} updated successfully!', 'success')
                return redirect(url_for('inventory'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating product: {str(e)}', 'danger')
        
        categories = Category.query.all()
        suppliers = Supplier.query.all()
        return render_template(
            'inventory/product_form.html',
            product=product,
            inventory=inventory,
            categories=categories,
            suppliers=suppliers,
            edit_mode=True
        )
    
    # Customer routes
    @app.route('/customers')
    @login_required
    @not_cashier_required
    def customers():
        customers = Customer.query.all()
        return render_template('customers/index.html', customers=customers)
    
    @app.route('/customers/add', methods=['GET', 'POST'])
    @login_required
    @not_cashier_required
    def add_customer():
        if request.method == 'POST':
            name = request.form.get('name')
            phone = request.form.get('phone')
            email = request.form.get('email')
            address = request.form.get('address')
            
            try:
                customer = Customer(
                    name=name,
                    phone=phone,
                    email=email,
                    address=address
                )
                db.session.add(customer)
                db.session.commit()
                
                flash(f'Customer {name} added successfully!', 'success')
                return redirect(url_for('customers'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding customer: {str(e)}', 'danger')
        
        return render_template('customers/customer_form.html')
    
    @app.route('/customers/edit/<int:customer_id>', methods=['GET', 'POST'])
    @login_required
    @not_cashier_required
    def edit_customer(customer_id):
        customer = Customer.query.get_or_404(customer_id)
        
        if request.method == 'POST':
            try:
                customer.name = request.form.get('name')
                customer.phone = request.form.get('phone')
                customer.email = request.form.get('email')
                customer.address = request.form.get('address')
                
                db.session.commit()
                flash(f'Customer {customer.name} updated successfully!', 'success')
                return redirect(url_for('customers'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating customer: {str(e)}', 'danger')
        
        return render_template('customers/customer_form.html', customer=customer, edit_mode=True)
    
    # Report routes
    @app.route('/reports/sales')
    @login_required
    @not_cashier_required
    def sales_report():
        store_id = session.get('store_id')
        
        # Get query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Default to today if no dates provided
        today = datetime.now().date()
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else today
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today
        
        # Adjust end_date to include the entire day
        end_date_adjusted = datetime.combine(end_date, datetime.max.time())
        
        # Query sales for the specified period
        sales = (
            Sale.query
            .filter(
                Sale.store_id == store_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date_adjusted,
                Sale.status == 'completed'
            )
            .order_by(Sale.sale_date.desc())
            .all()
        )
        
        # Calculate summary statistics
        total_sales = len(sales)
        total_amount = sum(sale.total_amount for sale in sales)
        
        payment_methods = {}
        for sale in sales:
            for payment in sale.payments:
                payment_methods[payment.payment_method] = payment_methods.get(payment.payment_method, 0) + payment.amount
        
        return render_template(
            'reports/sales.html',
            sales=sales,
            start_date=start_date,
            end_date=end_date,
            total_sales=total_sales,
            total_amount=total_amount,
            payment_methods=payment_methods
        )
    
    @app.route('/reports/inventory')
    @login_required
    @not_cashier_required
    def inventory_report():
        store_id = session.get('store_id')
        
        inventory_items = (
            db.session.query(Product, Inventory, Category)
            .join(Inventory, Product.id == Inventory.product_id)
            .outerjoin(Category, Product.category_id == Category.id)
            .filter(Inventory.store_id == store_id)
            .all()
        )
        
        # Calculate inventory value
        total_value = sum(item[0].cost_price * item[1].quantity for item in inventory_items)
        
        # Group by category
        categories = {}
        for product, inventory, category in inventory_items:
            category_name = category.name if category else "Uncategorized"
            if category_name not in categories:
                categories[category_name] = {
                    'count': 0,
                    'quantity': 0,
                    'value': 0
                }
            categories[category_name]['count'] += 1
            categories[category_name]['quantity'] += inventory.quantity
            categories[category_name]['value'] += product.cost_price * inventory.quantity
        
        return render_template(
            'reports/inventory.html',
            inventory_items=inventory_items,
            total_value=total_value,
            categories=categories
        )
    
    # User management
    @app.route('/users')
    @admin_required
    def users():
        users = (
            db.session.query(User, Role, Store)
            .join(Role, User.role_id == Role.id)
            .join(Store, User.store_id == Store.id)
            .all()
        )
        return render_template('users/index.html', users=users)
    
    @app.route('/users/add', methods=['GET', 'POST'])
    @admin_required
    def add_user():
        # Check if employee role is specified in query parameters
        employee_role = request.args.get('role') == 'employee'
        
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            phone = request.form.get('phone')
            role_id = request.form.get('role_id')
            store_id = request.form.get('store_id')
            
            error = None
            
            if not username or not email or not password or not role_id or not store_id:
                error = 'All fields are required.'
            elif User.query.filter_by(username=username).first():
                error = f'User {username} is already registered.'
            elif User.query.filter_by(email=email).first():
                error = f'Email {email} is already registered.'
            
            if error is None:
                try:
                    user = register_user(username, email, password, first_name, last_name, phone, role_id, store_id)
                    flash(f'User {username} created successfully!', 'success')
                    return redirect(url_for('users'))
                except Exception as e:
                    error = str(e)
            
            flash(error, 'danger')
        
        roles = Role.query.all()
        stores = Store.query.all()
        
        # If creating an employee, preselect the employee role
        selected_role_id = None
        if employee_role:
            # Find employee role ID
            employee_role_obj = Role.query.filter_by(name=Role.EMPLOYEE).first()
            if employee_role_obj:
                selected_role_id = employee_role_obj.id
        
        return render_template(
            'users/user_form.html', 
            roles=roles, 
            stores=stores, 
            employee_mode=employee_role,
            selected_role_id=selected_role_id,
            title="Add Employee" if employee_role else "Add New User"
        )
    
    @app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
    @admin_required
    def edit_user(user_id):
        user = User.query.get_or_404(user_id)
        
        if request.method == 'POST':
            try:
                user.username = request.form.get('username')
                user.email = request.form.get('email')
                user.first_name = request.form.get('first_name')
                user.last_name = request.form.get('last_name')
                user.phone = request.form.get('phone')
                user.role_id = request.form.get('role_id')
                user.store_id = request.form.get('store_id')
                user.is_active = bool(request.form.get('is_active'))
                
                # Only update password if provided
                new_password = request.form.get('password')
                if new_password:
                    user.set_password(new_password)
                
                db.session.commit()
                flash(f'User {user.username} updated successfully!', 'success')
                return redirect(url_for('users'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating user: {str(e)}', 'danger')
        
        roles = Role.query.all()
        stores = Store.query.all()
        return render_template(
            'users/user_form.html',
            user=user,
            roles=roles,
            stores=stores,
            edit_mode=True
        )
    
    # Settings and store management
    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    @not_cashier_required
    @manager_required
    def settings():
        store_id = session.get('store_id')
        store = Store.query.get(store_id)
        
        if request.method == 'POST':
            try:
                store.name = request.form.get('name')
                store.location = request.form.get('location')
                store.phone = request.form.get('phone')
                store.email = request.form.get('email')
                
                db.session.commit()
                flash('Store settings updated successfully!', 'success')
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating settings: {str(e)}', 'danger')
        
        return render_template('settings.html', store=store)
    
    # API routes for AJAX calls
    @app.route('/api/products', methods=['GET'])
    @login_required
    def api_products():
        store_id = session.get('store_id')
        query = request.args.get('q', '')
        
        products = (
            db.session.query(Product, Inventory)
            .join(Inventory, Product.id == Inventory.product_id)
            .filter(
                Inventory.store_id == store_id,
                Product.is_active == True,
                Product.name.ilike(f'%{query}%') | Product.barcode.ilike(f'%{query}%')
            )
            .all()
        )
        
        result = []
        for product, inventory in products:
            result.append({
                'id': product.id,
                'name': product.name,
                'barcode': product.barcode,
                'price': product.selling_price,
                'price_with_tax': product.price_with_tax,
                'tax_rate': product.tax_rate,
                'quantity_available': inventory.quantity
            })
        
        return jsonify(result)
    
    @app.route('/api/customers', methods=['GET'])
    @login_required
    def api_customers():
        query = request.args.get('q', '')
        
        customers = Customer.query.filter(
            Customer.name.ilike(f'%{query}%') | Customer.phone.ilike(f'%{query}%')
        ).all()
        
        result = []
        for customer in customers:
            result.append({
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'loyalty_points': customer.loyalty_points
            })
        
        return jsonify(result)
    
    # Initialize database with default data if empty
    @app.route('/initialize-data', methods=['GET'])
    def initialize_data():
        # Check if any users exist
        if User.query.count() > 0:
            return jsonify({'status': 'Database already initialized'})
        
        try:
            # Create default roles
            admin_role = Role(name=Role.ADMIN, description='System Administrator')
            manager_role = Role(name=Role.MANAGER, description='Store Manager')
            cashier_role = Role(name=Role.CASHIER, description='Sales Cashier')
            employee_role = Role(name=Role.EMPLOYEE, description='Store Employee')
            
            db.session.add_all([admin_role, manager_role, cashier_role, employee_role])
            db.session.flush()
            
            # Create default store
            store = Store(
                name='Main Store',
                location='Nairobi, Kenya',
                phone='+254700000000',
                email='store@example.com'
            )
            db.session.add(store)
            db.session.flush()
            
            # Create default admin user
            admin = User(
                username='admin',
                email='admin@example.com',
                first_name='Admin',
                last_name='User',
                role_id=admin_role.id,
                store_id=store.id,
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Create default product categories
            categories = [
                Category(name='Groceries'),
                Category(name='Electronics'),
                Category(name='Household'),
                Category(name='Beverages'),
                Category(name='Personal Care')
            ]
            db.session.add_all(categories)
            
            db.session.commit()
            return jsonify({'status': 'Database initialized successfully'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'Error', 'message': str(e)}), 500
    
    # Inventory enhancement routes for bulk imports, templates and barcodes
    @app.route('/inventory/import', methods=['GET', 'POST'])
    @manager_required
    def import_products():
        """Bulk import products page."""
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file part', 'danger')
                return redirect(request.url)
                
            file = request.files['file']
            
            if file.filename == '':
                flash('No selected file', 'danger')
                return redirect(request.url)
                
            if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
                # Process the file
                try:
                    # For simplicity, we'll only handle CSV files for now
                    if file.filename.endswith('.csv'):
                        # Get column mappings from form
                        column_name = request.form.get('column_name')
                        column_description = request.form.get('column_description')
                        column_sku = request.form.get('column_sku')
                        column_barcode = request.form.get('column_barcode')
                        column_selling_price = request.form.get('column_selling_price')
                        column_cost_price = request.form.get('column_cost_price')
                        column_tax_rate = request.form.get('column_tax_rate')
                        column_category = request.form.get('column_category')
                        column_quantity = request.form.get('column_quantity')
                        
                        # Get default values
                        default_category_id = request.form.get('default_category_id')
                        default_tax_rate = request.form.get('default_tax_rate', 16.0)
                        default_supplier_id = request.form.get('default_supplier_id')
                        default_quantity = request.form.get('default_quantity', 0)
                        default_reorder_level = request.form.get('default_reorder_level', 5)
                        
                        # Parse CSV
                        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                        csv_reader = csv.reader(stream)
                        
                        # Skip header row if indicated
                        if request.form.get('header_row'):
                            next(csv_reader)
                            
                        # Process each row
                        products_added = 0
                        errors = []
                        skipped = 0
                        duplicate_skus = 0
                        duplicate_barcodes = 0
                        
                        # Cache data to minimize database queries
                        categories_cache = {category.name.lower(): category.id for category in Category.query.all()}
                        existing_skus = {product.sku for product in Product.query.with_entities(Product.sku).all() if product.sku}
                        existing_barcodes = {product.barcode for product in Product.query.with_entities(Product.barcode).all() if product.barcode}
                        
                        # Process in batches for better performance with large files
                        batch_size = 100
                        batch = []
                        
                        for row_num, row in enumerate(csv_reader, 1):
                            try:
                                # Extract data based on column mappings
                                name = row[int(column_name)] if column_name else None
                                description = row[int(column_description)] if column_description and int(column_description) < len(row) else None
                                sku = row[int(column_sku)] if column_sku and int(column_sku) < len(row) else f"SKU-{uuid.uuid4().hex[:8].upper()}"
                                barcode = row[int(column_barcode)] if column_barcode and int(column_barcode) < len(row) else None
                                
                                selling_price = row[int(column_selling_price)] if column_selling_price and int(column_selling_price) < len(row) else 0
                                cost_price = row[int(column_cost_price)] if column_cost_price and int(column_cost_price) < len(row) else 0
                                tax_rate = row[int(column_tax_rate)] if column_tax_rate and int(column_tax_rate) < len(row) else default_tax_rate
                                
                                category_name = row[int(column_category)] if column_category and int(column_category) < len(row) else None
                                quantity = row[int(column_quantity)] if column_quantity and int(column_quantity) < len(row) else default_quantity
                                
                                # Skip rows without a product name
                                if not name:
                                    continue
                                    
                                # Determine category ID
                                category_id = default_category_id
                                if category_name:
                                    category_name_lower = category_name.lower()
                                    if category_name_lower in categories_cache:
                                        category_id = categories_cache[category_name_lower]
                                    else:
                                        # Create new category if it doesn't exist
                                        new_category = Category(name=category_name)
                                        db.session.add(new_category)
                                        db.session.flush()
                                        category_id = new_category.id
                                        categories_cache[category_name_lower] = category_id
                                
                                # Generate barcode if not provided
                                if not barcode:
                                    # Generate a unique EAN-13 barcode
                                    barcode = "590"  # Example prefix
                                    for _ in range(9):
                                        barcode += str(random.randint(0, 9))
                                    
                                    # Calculate check digit
                                    total = 0
                                    for i, digit in enumerate(barcode):
                                        total += int(digit) * (1 if i % 2 == 0 else 3)
                                    check_digit = (10 - (total % 10)) % 10
                                    barcode += str(check_digit)
                                
                                # Check for duplicates
                                if sku and sku in existing_skus:
                                    duplicate_skus += 1
                                    if request.form.get('skip_duplicates', 'on') == 'on':
                                        skipped += 1
                                        continue
                                
                                if barcode and barcode in existing_barcodes:
                                    duplicate_barcodes += 1
                                    if request.form.get('skip_duplicates', 'on') == 'on':
                                        skipped += 1
                                        continue
                                
                                # Create product object
                                product = Product(
                                    name=name,
                                    description=description or f"Description for {name}",
                                    sku=sku,
                                    barcode=barcode,
                                    selling_price=float(selling_price),
                                    cost_price=float(cost_price),
                                    tax_rate=float(tax_rate),
                                    category_id=category_id,
                                    supplier_id=default_supplier_id,
                                    is_active=True
                                )
                                
                                # Add to batch for bulk insert
                                batch.append(product)
                                
                                # Process in batches to improve performance
                                if len(batch) >= batch_size:
                                    db.session.add_all(batch)
                                    db.session.flush()  # Get IDs without committing
                                    
                                    # Create inventory entries for each product in batch
                                    for prod in batch:
                                        inventory = Inventory(
                                            product_id=prod.id,
                                            store_id=session.get('store_id'),
                                            quantity=int(quantity),
                                            reorder_level=int(default_reorder_level),
                                            last_restock_date=datetime.utcnow() if int(quantity) > 0 else None
                                        )
                                        db.session.add(inventory)
                                        
                                        # Update tracking
                                        if sku and sku not in existing_skus:
                                            existing_skus.add(sku)
                                        if barcode and barcode not in existing_barcodes:
                                            existing_barcodes.add(barcode)
                                    
                                    products_added += len(batch)
                                    batch = []
                                
                            except Exception as e:
                                errors.append(f"Error processing row: {str(e)}")
                                continue
                        
                        # Process any remaining products in the last batch
                        if batch:
                            db.session.add_all(batch)
                            db.session.flush()
                            
                            # Create inventory entries for remaining products
                            for prod in batch:
                                inventory = Inventory(
                                    product_id=prod.id,
                                    store_id=session.get('store_id'),
                                    quantity=int(quantity),
                                    reorder_level=int(default_reorder_level),
                                    last_restock_date=datetime.utcnow() if int(quantity) > 0 else None
                                )
                                db.session.add(inventory)
                            
                            products_added += len(batch)
                        
                        # Either commit all or roll back
                        if products_added > 0:
                            db.session.commit()
                            
                            # Create detailed success message
                            success_msg = f'Successfully imported {products_added} products'
                            details = []
                            
                            if skipped > 0:
                                details.append(f"{skipped} duplicates skipped")
                            if duplicate_skus > 0:
                                details.append(f"{duplicate_skus} duplicate SKUs")
                            if duplicate_barcodes > 0:
                                details.append(f"{duplicate_barcodes} duplicate barcodes")
                            if len(errors) > 0:
                                details.append(f"{len(errors)} errors")
                                
                            if details:
                                success_msg += f" ({', '.join(details)})"
                            
                            flash(success_msg, 'success')
                        else:
                            db.session.rollback()
                            flash('No products were imported. Please check your file and mapping.', 'warning')
                        
                        # Report errors with row numbers for easier reference
                        if errors:
                            for error in errors[:5]:  # Show first 5 errors
                                flash(error, 'warning')
                            if len(errors) > 5:
                                flash(f'... and {len(errors) - 5} more errors. Check the log for details.', 'warning')
                                for error in errors:
                                    logging.error(error)
                                    
                            # Generate downloadable error log if there are many errors
                            if len(errors) > 10:
                                session['import_errors'] = errors
                                flash(f'<a href="{url_for("download_import_errors")}" class="alert-link">Download complete error log</a>', 'info')
                    
                    return redirect(url_for('inventory'))
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error importing products: {str(e)}', 'danger')
                    logging.error(f"Error importing products: {str(e)}")
                    return redirect(request.url)
            else:
                flash('File type not supported. Please upload a CSV or Excel file.', 'danger')
                return redirect(request.url)
                
        # GET request - render the form
        categories = Category.query.all()
        suppliers = Supplier.query.all()
        
        return render_template(
            'inventory/import.html',
            categories=categories,
            suppliers=suppliers
        )
        
    @app.route('/inventory/templates', methods=['GET'])
    @manager_required
    def product_templates():
        """Product templates page."""
        templates = ProductTemplate.query.all()
        categories = Category.query.all()
        suppliers = Supplier.query.all()
        
        return render_template(
            'inventory/templates.html',
            templates=templates,
            categories=categories,
            suppliers=suppliers
        )
        
    @app.route('/inventory/create-product-template', methods=['POST'])
    @manager_required
    def create_product_template():
        """Create a new product template."""
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            category_id = request.form.get('category_id') or None
            supplier_id = request.form.get('supplier_id') or None
            tax_rate = request.form.get('tax_rate', 16.0)
            reorder_level = request.form.get('reorder_level', 5)
            sku_prefix = request.form.get('sku_prefix', '')
            description_template = request.form.get('description_template', '')
            
            template = ProductTemplate(
                name=name,
                description=description,
                category_id=category_id,
                supplier_id=supplier_id,
                tax_rate=float(tax_rate),
                reorder_level=int(reorder_level),
                sku_prefix=sku_prefix,
                description_template=description_template
            )
            
            db.session.add(template)
            db.session.commit()
            
            flash(f'Template "{name}" created successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating template: {str(e)}', 'danger')
            logging.error(f"Error creating product template: {str(e)}")
        
        return redirect(url_for('product_templates'))
        
    @app.route('/inventory/update-product-template', methods=['POST'])
    @manager_required
    def update_product_template():
        """Update an existing product template."""
        try:
            template_id = request.form.get('template_id')
            
            template = ProductTemplate.query.get_or_404(template_id)
            
            template.name = request.form.get('name')
            template.description = request.form.get('description')
            template.category_id = request.form.get('category_id') or None
            template.supplier_id = request.form.get('supplier_id') or None
            template.tax_rate = float(request.form.get('tax_rate', 16.0))
            template.reorder_level = int(request.form.get('reorder_level', 5))
            template.sku_prefix = request.form.get('sku_prefix', '')
            template.description_template = request.form.get('description_template', '')
            
            db.session.commit()
            
            flash(f'Template "{template.name}" updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating template: {str(e)}', 'danger')
            logging.error(f"Error updating product template: {str(e)}")
        
        return redirect(url_for('product_templates'))
        
    @app.route('/inventory/delete-product-template', methods=['POST'])
    @manager_required
    def delete_product_template():
        """Delete a product template."""
        try:
            template_id = request.form.get('template_id')
            
            template = ProductTemplate.query.get_or_404(template_id)
            
            # Comment out for now as template_id doesn't exist in Product yet
            # if Product.query.filter_by(template_id=template_id).count() > 0:
            #     flash(f'Cannot delete template "{template.name}" because it is being used by products.', 'danger')
            #     return redirect(url_for('product_templates'))
                
            db.session.delete(template)
            db.session.commit()
            
            flash(f'Template "{template.name}" deleted successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting template: {str(e)}', 'danger')
            logging.error(f"Error deleting product template: {str(e)}")
        
        return redirect(url_for('product_templates'))
        
    @app.route('/api/product-templates/<int:template_id>', methods=['GET'])
    @login_required
    def get_product_template(template_id):
        """Get product template data for AJAX requests."""
        try:
            template = ProductTemplate.query.get_or_404(template_id)
            
            # Get all categories and suppliers for the form
            categories = Category.query.all()
            suppliers = Supplier.query.all()
            
            return jsonify({
                'id': template.id,
                'name': template.name,
                'description': template.description or '',
                'category_id': template.category_id,
                'supplier_id': template.supplier_id,
                'tax_rate': template.tax_rate,
                'reorder_level': template.reorder_level,
                'sku_prefix': template.sku_prefix or '',
                'description_template': template.description_template or '',
                'categories': [{'id': c.id, 'name': c.name} for c in categories],
                'suppliers': [{'id': s.id, 'name': s.name} for s in suppliers]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    @app.route('/inventory/barcodes', methods=['GET'])
    @login_required
    def barcodes():
        """Barcode generation and printing page."""
        products = db.session.query(Product, Inventory)\
            .join(Inventory, Product.id == Inventory.product_id)\
            .filter(Inventory.store_id == session.get('store_id'))\
            .all()
            
        return render_template('inventory/barcodes.html', products=products)
        
    @app.route('/inventory/download-import-errors', methods=['GET'])
    @login_required
    @not_cashier_required
    def download_import_errors():
        """Download error log from product import."""
        if 'import_errors' not in session or not session['import_errors']:
            flash('No import errors found', 'warning')
            return redirect(url_for('import_products'))
            
        errors = session['import_errors']
        
        # Create CSV with error data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Error Number', 'Error Message'])
        
        # Write error data
        for i, error in enumerate(errors, 1):
            writer.writerow([i, error])
        
        # Go to the beginning of the stream
        output.seek(0)
        
        # Create a response with the CSV
        response = send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'product_import_errors_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
        # Clear the errors from session after download
        session.pop('import_errors', None)
        
        return response
    
    @app.route('/inventory/download-product-template', methods=['GET'])
    @login_required
    @not_cashier_required
    def download_product_template():
        """Download sample CSV template for product import."""
        # Create a CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Name', 'Description', 'SKU', 'Barcode', 'Selling Price', 'Cost Price', 'Tax Rate', 'Category', 'Quantity'])
        
        # Write sample data
        writer.writerow(['Jogoo Maize Flour 2kg', 'Popular maize flour', 'SKU001', '5901234123457', '175.00', '145.00', '16', 'Groceries', '50'])
        writer.writerow(['Mumias Sugar 1kg', 'Fine granulated sugar', 'SKU002', '5901234123458', '130.00', '110.00', '16', 'Groceries', '40'])
        writer.writerow(['Dettol Soap 175g', 'Antibacterial soap', 'SKU003', '5901234123459', '90.00', '70.00', '16', 'Personal Care', '30'])
        
        # Go to the beginning of the stream
        output.seek(0)
        
        # Create a response with the CSV
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='product_import_template.csv'
        )
        
    @app.route('/inventory/save-label-template', methods=['POST'])
    @login_required
    def save_label_template():
        """Save a label template."""
        try:
            template_name = request.form.get('template_name')
            template_description = request.form.get('template_description', '')
            template_config = request.form.get('template_config', '{}')
            
            # Validate JSON
            json.loads(template_config)
            
            template = LabelTemplate(
                name=template_name,
                description=template_description,
                config=template_config,
                user_id=session.get('user_id')
            )
            
            db.session.add(template)
            db.session.commit()
            
            flash(f'Label template "{template_name}" saved successfully.', 'success')
        except json.JSONDecodeError:
            flash('Invalid template configuration.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving label template: {str(e)}', 'danger')
            logging.error(f"Error saving label template: {str(e)}")
        
        return redirect(url_for('barcodes'))
    
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_template('error/500.html'), 500
