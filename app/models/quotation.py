# app/models/quotation.py
from app import db
from datetime import datetime

class Quotation(db.Model):
    __tablename__ = 'quotations'
    
    id = db.Column(db.Integer, primary_key=True)
    quotation_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Customer details
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(100))
    customer_address = db.Column(db.Text)
    customer_gstin = db.Column(db.String(20))
    
    # Quotation details
    quotation_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    valid_until = db.Column(db.Date, nullable=False)
    
    # Financial details
    subtotal = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    discount_type = db.Column(db.String(20), default='fixed')
    discount_rate = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    
    # Additional
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # created_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Comment this out if no users table
    
    # Relationships
    items = db.relationship('QuotationItem', backref='quotation', lazy=True, cascade='all, delete-orphan')
    
    def calculate_totals(self):
        """Calculate subtotal and total"""
        self.subtotal = sum(item.total for item in self.items)
        
        if self.discount_type == 'percentage':
            self.discount = (self.subtotal * self.discount_rate) / 100
        else:
            self.discount = min(self.discount_rate, self.subtotal)
        
        self.total = self.subtotal - self.discount
        
    def to_dict(self):
        """Convert quotation to dictionary"""
        return {
            'id': self.id,
            'quotationNumber': self.quotation_number,
            'customerName': self.customer_name,
            'customerPhone': self.customer_phone,
            'customerEmail': self.customer_email,
            'customerAddress': self.customer_address,
            'customerGstin': self.customer_gstin,
            'quotationDate': self.quotation_date.isoformat() if self.quotation_date else None,
            'validUntil': self.valid_until.isoformat() if self.valid_until else None,
            'subtotal': self.subtotal,
            'discount': self.discount,
            'discountType': self.discount_type,
            'discountRate': self.discount_rate,
            'total': self.total,
            'notes': self.notes,
            'status': self.status,
            'items': [item.to_dict() for item in self.items],
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class QuotationItem(db.Model):
    __tablename__ = 'quotation_items'
    
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Snapshot of product details at time of quotation
    product_name = db.Column(db.String(100), nullable=False)
    product_model = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    gst = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)
    
    # Relationship
    product = db.relationship('Product')
    
    def calculate_total(self):
        """Calculate item total"""
        self.total = self.price * self.quantity
    
    def to_dict(self):
        """Convert quotation item to dictionary"""
        return {
            'id': self.id,
            'productId': self.product_id,
            'productName': self.product_name,
            'productModel': self.product_model,
            'price': self.price,
            'quantity': self.quantity,
            'gst': self.gst,
            'total': self.total
        }