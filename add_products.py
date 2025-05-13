#!/usr/bin/env python
import os
import sys
import random
from datetime import datetime, timedelta

# Add the current directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Product, Category, Supplier, Inventory, Store

# Kenyan-specific product data
products_data = [
    # Groceries
    {"name": "Unga Ngano (Wheat Flour) 2kg", "category": "Groceries", "price": 250.00, "cost": 200.00, "barcode": "5901234123457"},
    {"name": "Jogoo Maize Flour 2kg", "category": "Groceries", "price": 175.00, "cost": 145.00, "barcode": "5901234123458"},
    {"name": "Mumias Sugar 1kg", "category": "Groceries", "price": 130.00, "cost": 110.00, "barcode": "5901234123459"},
    {"name": "Kabras Sugar 2kg", "category": "Groceries", "price": 260.00, "cost": 220.00, "barcode": "5901234123460"},
    {"name": "Golden Fry Cooking Oil 2L", "category": "Groceries", "price": 550.00, "cost": 450.00, "barcode": "5901234123461"},
    {"name": "Royco Mchuzi Mix Beef 200g", "category": "Groceries", "price": 95.00, "cost": 75.00, "barcode": "5901234123462"},
    
    # Beverages
    {"name": "Tusker Lager 500ml", "category": "Beverages", "price": 180.00, "cost": 145.00, "barcode": "5901234123463"},
    {"name": "Ketepa Tea Leaves 250g", "category": "Beverages", "price": 210.00, "cost": 170.00, "barcode": "5901234123464"},
    {"name": "Java House Coffee 200g", "category": "Beverages", "price": 350.00, "cost": 280.00, "barcode": "5901234123465"},
    {"name": "Coca Cola 2L", "category": "Beverages", "price": 160.00, "cost": 130.00, "barcode": "5901234123466"},
    {"name": "Minute Maid Orange Juice 1L", "category": "Beverages", "price": 220.00, "cost": 180.00, "barcode": "5901234123467"},
    
    # Personal Care
    {"name": "Dettol Soap 175g", "category": "Personal Care", "price": 90.00, "cost": 70.00, "barcode": "5901234123468"},
    {"name": "Colgate Toothpaste 150g", "category": "Personal Care", "price": 180.00, "cost": 140.00, "barcode": "5901234123469"},
    {"name": "Nice & Lovely Lotion 400ml", "category": "Personal Care", "price": 250.00, "cost": 195.00, "barcode": "5901234123470"},
    {"name": "Omo Washing Powder 1kg", "category": "Personal Care", "price": 350.00, "cost": 280.00, "barcode": "5901234123471"},
    
    # Electronics
    {"name": "Safaricom Airtime Scratch Card KES 1000", "category": "Electronics", "price": 1000.00, "cost": 950.00, "barcode": "5901234123472"},
    {"name": "Kenyan Mpesa Sim Card", "category": "Electronics", "price": 50.00, "cost": 30.00, "barcode": "5901234123473"},
    {"name": "Generic USB Cable", "category": "Electronics", "price": 350.00, "cost": 200.00, "barcode": "5901234123474"},
    {"name": "Nokia Feature Phone", "category": "Electronics", "price": 2500.00, "cost": 2000.00, "barcode": "5901234123475"},
    
    # Household
    {"name": "Kiwi Shoe Polish Black", "category": "Household", "price": 120.00, "cost": 95.00, "barcode": "5901234123476"},
    {"name": "Neko Toilet Paper 10 Pack", "category": "Household", "price": 450.00, "cost": 380.00, "barcode": "5901234123477"},
    {"name": "Mortein Doom Insect Spray 400ml", "category": "Household", "price": 320.00, "cost": 260.00, "barcode": "5901234123478"}
]

def add_products():
    with app.app_context():
        # Get all categories (they should already exist from initialization)
        categories = {category.name: category for category in Category.query.all()}
        
        # If no categories exist, create them
        if not categories:
            for category_name in ["Groceries", "Beverages", "Personal Care", "Electronics", "Household"]:
                category = Category(name=category_name)
                db.session.add(category)
            db.session.commit()
            # Refresh categories
            categories = {category.name: category for category in Category.query.all()}
        
        # Get default supplier (or create one)
        supplier = Supplier.query.first()
        if not supplier:
            supplier = Supplier(
                name="Kenya Suppliers Ltd",
                contact_person="John Kamau",
                phone="+254712345678",
                email="info@kenyasuppliers.co.ke",
                address="Nairobi Business District"
            )
            db.session.add(supplier)
            db.session.commit()
        
        # Get default store
        store = Store.query.first()
        if not store:
            print("Error: No store found in database. Please initialize database first.")
            return
        
        # Add products
        products_added = 0
        for product_data in products_data:
            # Check if product with this barcode already exists
            existing_product = Product.query.filter_by(barcode=product_data["barcode"]).first()
            if not existing_product:
                # Create the product
                product = Product(
                    name=product_data["name"],
                    description=f"Description for {product_data['name']}",
                    sku=f"SKU-{random.randint(10000, 99999)}",
                    barcode=product_data["barcode"],
                    selling_price=product_data["price"],
                    cost_price=product_data["cost"],
                    tax_rate=16.0,  # Standard Kenyan VAT rate
                    is_active=True,
                    category_id=categories[product_data["category"]].id,
                    supplier_id=supplier.id
                )
                db.session.add(product)
                db.session.flush()  # Flush to get the product ID
                
                # Create inventory entry for this product
                inventory = Inventory(
                    product_id=product.id,
                    store_id=store.id,
                    quantity=random.randint(10, 100),
                    reorder_level=5,
                    last_restock_date=datetime.utcnow() - timedelta(days=random.randint(1, 30))
                )
                db.session.add(inventory)
                products_added += 1
        
        if products_added > 0:
            db.session.commit()
            print(f"Successfully added {products_added} products to the database.")
        else:
            print("All products already exist in the database.")

if __name__ == "__main__":
    add_products()