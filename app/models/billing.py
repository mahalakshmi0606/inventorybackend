# app/models/billing.py
from app import db
from datetime import datetime

class Bill(db.Model):
    __tablename__ = "bills"

    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Customer Information
    customer_name = db.Column(db.String(100), nullable=False, default='Walk-in Customer')
    customer_phone = db.Column(db.String(20))
    customer_email = db.Column(db.String(100))
    customer_gst = db.Column(db.String(50))
    customer_address = db.Column(db.String(200))
    
    # Bill Summary
    subtotal = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    discount_type = db.Column(db.String(20), default='amount')  # 'amount' or 'percentage'
    tax = db.Column(db.Float, default=0)
    tax_type = db.Column(db.String(20), default='percentage')  # 'amount' or 'percentage'
    total = db.Column(db.Float, default=0)
    
    # Payment Information
    paid_amount = db.Column(db.Float, default=0)
    change_amount = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(50), default='cash')  # cash, card, upi, credit
    payment_status = db.Column(db.String(20), default='pending')  # paid, partial, pending
    
    # Metadata - REMOVED the foreign key
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)  # Just store user ID without foreign key
    
    # Relationships
    items = db.relationship('BillItem', backref='bill', lazy=True, cascade='all, delete-orphan')
    
    def generate_bill_number(self):
        """Generate unique bill number"""
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        
        # Get count of bills created today
        today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
        today_end = datetime(now.year, now.month, now.day, 23, 59, 59)
        
        bill_count = Bill.query.filter(
            Bill.created_at.between(today_start, today_end)
        ).count() + 1
        
        return f"BILL-{date_str}-{str(bill_count).zfill(4)}"
    
    def calculate_totals(self):
        """Calculate all bill totals"""
        self.subtotal = sum(item.total for item in self.items)
        
        # Apply discount
        if self.discount_type == 'percentage':
            discount_amount = (self.subtotal * self.discount) / 100
        else:
            discount_amount = self.discount
        
        # Apply tax
        if self.tax_type == 'percentage':
            tax_amount = ((self.subtotal - discount_amount) * self.tax) / 100
        else:
            tax_amount = self.tax
        
        self.total = self.subtotal - discount_amount + tax_amount
        self.change_amount = max(0, self.paid_amount - self.total)
        
        # Update payment status
        if self.paid_amount >= self.total:
            self.payment_status = 'paid'
        elif self.paid_amount > 0:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'pending'
    
    def to_dict(self):
        return {
            'id': self.id,
            'billNumber': self.bill_number,
            'customer': {
                'name': self.customer_name,
                'phone': self.customer_phone,
                'email': self.customer_email,
                'gst': self.customer_gst,
                'address': self.customer_address
            },
            'summary': {
                'subtotal': round(self.subtotal, 2),
                'discount': round(self.discount, 2),
                'discountType': self.discount_type,
                'tax': round(self.tax, 2),
                'taxType': self.tax_type,
                'total': round(self.total, 2)
            },
            'payment': {
                'paidAmount': round(self.paid_amount, 2),
                'changeAmount': round(self.change_amount, 2),
                'method': self.payment_method,
                'status': self.payment_status
            },
            'items': [item.to_dict() for item in self.items],
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class BillItem(db.Model):
    __tablename__ = "bill_items"
    
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Snapshot of product details at time of billing
    product_name = db.Column(db.String(100), nullable=False)
    product_model = db.Column(db.String(100))
    product_type = db.Column(db.String(100))
    sell_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Float, nullable=False)
    
    # Item Status - Added new field with default 'pending'
    item_status = db.Column(db.String(20), nullable=False, default='pending')  # pending, completed, cancelled
    
    # Relationship
    product = db.relationship('Product')
    
    def to_dict(self):
        return {
            'id': self.id,
            'productId': self.product_id,
            'productName': self.product_name,
            'productModel': self.product_model,
            'productType': self.product_type,
            'sellPrice': round(self.sell_price, 2),
            'quantity': self.quantity,
            'total': round(self.total, 2),
            'itemStatus': self.item_status  # Will always be 'pending' by default
        }


class Payment(db.Model):
    __tablename__ = "payments"
    
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=False)
    payment_id = db.Column(db.String(100), unique=True)  # Transaction ID from payment gateway
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50), nullable=False)  # cash, card, upi, credit
    status = db.Column(db.String(20), default='completed')  # completed, pending, failed, refunded
    reference = db.Column(db.String(100))  # Check number, UPI reference, etc.
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    bill = db.relationship('Bill', backref='payments')
    
    def to_dict(self):
        return {
            'id': self.id,
            'paymentId': self.payment_id,
            'amount': round(self.amount, 2),
            'method': self.method,
            'status': self.status,
            'reference': self.reference,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }