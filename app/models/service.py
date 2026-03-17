# app/models/service.py
from app import db
from datetime import datetime

class Service(db.Model):
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False, default=0)
    gst_rate = db.Column(db.Float, default=0)
    category = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)  # Just store user ID without foreign key
    
    # Relationships
    bill_items = db.relationship('ServiceBillItem', backref='service', lazy=True)
    
    def to_dict(self):
        """Convert service to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'gst_rate': self.gst_rate,
            'category': self.category,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Service {self.name}>'


class ServiceBillItem(db.Model):
    __tablename__ = 'service_bill_items'
    
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id', ondelete='SET NULL'), nullable=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id', ondelete='CASCADE'), nullable=False)
    
    # Snapshot of service details at time of billing
    service_name = db.Column(db.String(100), nullable=False)
    service_description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    gst_rate = db.Column(db.Float, default=0)
    gst_amount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def calculate_totals(self):
        """Calculate GST and total"""
        self.gst_amount = (self.price * self.gst_rate / 100) * self.quantity
        self.total = (self.price * self.quantity) + self.gst_amount
        return self
    
    def to_dict(self):
        """Convert service bill item to dictionary"""
        return {
            'id': self.id,
            'serviceId': self.service_id,
            'billId': self.bill_id,
            'serviceName': self.service_name,
            'serviceDescription': self.service_description,
            'price': self.price,
            'quantity': self.quantity,
            'gstRate': self.gst_rate,
            'gstAmount': self.gst_amount,
            'total': self.total,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<ServiceBillItem {self.service_name} x{self.quantity}>'