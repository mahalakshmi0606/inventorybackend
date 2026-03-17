# app/routes/service_routes.py
from flask import Blueprint, request, jsonify, session
from app import db
from app.models.service import Service, ServiceBillItem
from app.models.billing import Bill
from datetime import datetime
import logging
import traceback
import random
import string

service_bp = Blueprint('service', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

# ==================== Service Management Routes ====================

@service_bp.route('/services', methods=['GET'])
def get_services():
    """Get all services"""
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        query = Service.query
        if not include_inactive:
            query = query.filter_by(is_active=True)
        
        services = query.order_by(Service.name).all()
        return jsonify([service.to_dict() for service in services]), 200
        
    except Exception as e:
        logger.error(f"Error fetching services: {str(e)}")
        return jsonify({'error': 'Failed to fetch services'}), 500


@service_bp.route('/services/search', methods=['GET'])
def search_services():
    """Search services by name, description, or category"""
    try:
        query = request.args.get('q', '')
        if len(query) < 2:
            return jsonify([]), 200
        
        search_term = f"%{query}%"
        services = Service.query.filter(
            Service.is_active == True,
            db.or_(
                Service.name.ilike(search_term),
                Service.description.ilike(search_term),
                Service.category.ilike(search_term)
            )
        ).order_by(Service.name).limit(20).all()
        
        return jsonify([service.to_dict() for service in services]), 200
        
    except Exception as e:
        logger.error(f"Error searching services: {str(e)}")
        return jsonify({'error': 'Failed to search services'}), 500


@service_bp.route('/services/<int:service_id>', methods=['GET'])
def get_service(service_id):
    """Get service by ID"""
    try:
        service = Service.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        return jsonify(service.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error fetching service: {str(e)}")
        return jsonify({'error': 'Failed to fetch service'}), 500


@service_bp.route('/services', methods=['POST'])
def create_service():
    """Create a new service"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Service name is required'}), 400
        
        if not data.get('price') and data.get('price') != 0:
            return jsonify({'error': 'Service price is required'}), 400
        
        # Create new service
        service = Service(
            name=data['name'],
            description=data.get('description', ''),
            price=float(data['price']),
            gst_rate=float(data.get('gst_rate', 0)),
            category=data.get('category', 'General')
        )
        
        db.session.add(service)
        db.session.commit()
        
        return jsonify({
            'message': 'Service created successfully',
            'service': service.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': 'Invalid price value'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating service: {str(e)}")
        return jsonify({'error': 'Failed to create service'}), 500


@service_bp.route('/services/<int:service_id>', methods=['PUT'])
def update_service(service_id):
    """Update an existing service"""
    try:
        service = Service.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            service.name = data['name']
        if 'description' in data:
            service.description = data['description']
        if 'price' in data:
            service.price = float(data['price'])
        if 'gst_rate' in data:
            service.gst_rate = float(data['gst_rate'])
        if 'category' in data:
            service.category = data['category']
        
        service.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Service updated successfully',
            'service': service.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({'error': 'Invalid price value'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating service: {str(e)}")
        return jsonify({'error': 'Failed to update service'}), 500


@service_bp.route('/services/<int:service_id>/toggle', methods=['PATCH'])
def toggle_service_status(service_id):
    """Activate or deactivate a service"""
    try:
        service = Service.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        data = request.get_json()
        service.is_active = data.get('is_active', not service.is_active)
        service.updated_at = datetime.utcnow()
        db.session.commit()
        
        status = 'activated' if service.is_active else 'deactivated'
        return jsonify({
            'message': f'Service {status} successfully',
            'is_active': service.is_active
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling service status: {str(e)}")
        return jsonify({'error': 'Failed to update service status'}), 500


@service_bp.route('/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    """Delete a service (soft delete by setting is_active=False)"""
    try:
        service = Service.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        # Soft delete by deactivating
        service.is_active = False
        service.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Service deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting service: {str(e)}")
        return jsonify({'error': 'Failed to delete service'}), 500


# ==================== Service Bill Items Routes ====================

@service_bp.route('/bills/<int:bill_id>/service-items', methods=['GET'])
def get_bill_service_items(bill_id):
    """Get all service items for a bill"""
    try:
        items = ServiceBillItem.query.filter_by(bill_id=bill_id).all()
        return jsonify([item.to_dict() for item in items]), 200
        
    except Exception as e:
        logger.error(f"Error fetching service items: {str(e)}")
        return jsonify({'error': 'Failed to fetch service items'}), 500


@service_bp.route('/bills/<int:bill_id>/service-items', methods=['POST'])
def add_service_item(bill_id):
    """Add a service item to a bill"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('serviceName'):
            return jsonify({'error': 'Service Name is required'}), 400
        
        if not data.get('quantity') or int(data['quantity']) <= 0:
            return jsonify({'error': 'Valid quantity is required'}), 400
        
        if not data.get('price') and data.get('price') != 0:
            return jsonify({'error': 'Price is required'}), 400
        
        # Get service details
        service_name = data.get('serviceName')
        service_description = data.get('serviceDescription', '')
        price = float(data['price'])
        gst_rate = float(data.get('gstRate', data.get('gst_rate', 0)))  # Handle both field names
        
        # Calculate totals
        quantity = int(data['quantity'])
        gst_amount = (price * gst_rate / 100) * quantity
        total = (price * quantity) + gst_amount
        
        # Create service bill item
        item = ServiceBillItem(
            service_id=data.get('serviceId', data.get('service_id')),  # Handle both field names
            bill_id=bill_id,
            service_name=service_name,
            service_description=service_description,
            price=price,
            quantity=quantity,
            gst_rate=gst_rate,
            gst_amount=gst_amount,
            total=total
        )
        
        db.session.add(item)
        
        # Update bill totals
        bill = Bill.query.get(bill_id)
        if bill:
            bill.total = (bill.total or 0) + total
        
        db.session.commit()
        
        return jsonify({
            'message': 'Service item added successfully',
            'item': item.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': 'Invalid numeric value'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding service item: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to add service item'}), 500


@service_bp.route('/service-items/<int:item_id>', methods=['PUT'])
def update_service_item(item_id):
    """Update a service item"""
    try:
        item = ServiceBillItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Service item not found'}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'quantity' in data:
            item.quantity = int(data['quantity'])
        if 'price' in data:
            item.price = float(data['price'])
        if 'gst_rate' in data:
            item.gst_rate = float(data['gst_rate'])
        
        # Recalculate totals
        item.gst_amount = (item.price * item.gst_rate / 100) * item.quantity
        old_total = item.total
        item.total = (item.price * item.quantity) + item.gst_amount
        
        # Update bill totals
        bill = Bill.query.get(item.bill_id)
        if bill:
            bill.total = (bill.total or 0) - old_total + item.total
        
        db.session.commit()
        
        return jsonify({
            'message': 'Service item updated successfully',
            'item': item.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({'error': 'Invalid numeric value'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating service item: {str(e)}")
        return jsonify({'error': 'Failed to update service item'}), 500


@service_bp.route('/service-items/<int:item_id>', methods=['DELETE'])
def delete_service_item(item_id):
    """Delete a service item"""
    try:
        item = ServiceBillItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Service item not found'}), 404
        
        bill_id = item.bill_id
        item_total = item.total
        
        db.session.delete(item)
        
        # Update bill totals
        bill = Bill.query.get(bill_id)
        if bill:
            bill.total = max(0, (bill.total or 0) - item_total)
        
        db.session.commit()
        
        return jsonify({'message': 'Service item deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting service item: {str(e)}")
        return jsonify({'error': 'Failed to delete service item'}), 500


# ==================== Service Analytics Routes ====================

@service_bp.route('/analytics/popular-services', methods=['GET'])
def get_popular_services():
    """Get most used services"""
    try:
        from sqlalchemy import func
        
        results = db.session.query(
            Service.id,
            Service.name,
            Service.category,
            func.count(ServiceBillItem.id).label('usage_count'),
            func.sum(ServiceBillItem.quantity).label('total_quantity'),
            func.sum(ServiceBillItem.total).label('total_revenue')
        ).outerjoin(
            ServiceBillItem, Service.id == ServiceBillItem.service_id
        ).filter(
            Service.is_active == True
        ).group_by(
            Service.id, Service.name, Service.category
        ).order_by(
            func.count(ServiceBillItem.id).desc()
        ).limit(10).all()
        
        return jsonify([{
            'id': r[0],
            'name': r[1],
            'category': r[2],
            'usage_count': r[3],
            'total_quantity': float(r[4]) if r[4] else 0,
            'total_revenue': float(r[5]) if r[5] else 0
        } for r in results]), 200
        
    except Exception as e:
        logger.error(f"Error fetching popular services: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics'}), 500


@service_bp.route('/analytics/service-revenue', methods=['GET'])
def get_service_revenue():
    """Get revenue by service category"""
    try:
        from sqlalchemy import func
        
        period = request.args.get('period', 'month')  # day, week, month, year
        
        # Define date truncation based on period
        if period == 'day':
            date_trunc = func.date(ServiceBillItem.created_at)
        elif period == 'week':
            date_trunc = func.date_format(ServiceBillItem.created_at, '%Y-%u')
        elif period == 'month':
            date_trunc = func.date_format(ServiceBillItem.created_at, '%Y-%m')
        elif period == 'year':
            date_trunc = func.year(ServiceBillItem.created_at)
        else:
            date_trunc = func.date_format(ServiceBillItem.created_at, '%Y-%m')
        
        results = db.session.query(
            date_trunc.label('period'),
            Service.category,
            func.count(db.distinct(ServiceBillItem.bill_id)).label('bill_count'),
            func.sum(ServiceBillItem.quantity).label('total_quantity'),
            func.sum(ServiceBillItem.total).label('total_revenue')
        ).join(
            Service, Service.id == ServiceBillItem.service_id
        ).group_by(
            'period', Service.category
        ).order_by(
            func.max(ServiceBillItem.created_at).desc()
        ).limit(30).all()
        
        return jsonify([{
            'period': r[0],
            'category': r[1],
            'bill_count': r[2],
            'total_quantity': float(r[3]) if r[3] else 0,
            'total_revenue': float(r[4]) if r[4] else 0
        } for r in results]), 200
        
    except Exception as e:
        logger.error(f"Error fetching service revenue: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics'}), 500


# ==================== Direct Service Bill Creation ====================

@service_bp.route('/service-bills', methods=['POST'])
def create_service_bill():
    """Create a service bill directly without going through billing_routes"""
    try:
        data = request.get_json()
        
        # Log received data for debugging
        logger.info(f"Received service bill data: {data}")
        
        # Validate required fields
        if not data.get('customerName'):
            return jsonify({'error': 'Customer name is required'}), 400
        
        if not data.get('items') or len(data['items']) == 0:
            return jsonify({'error': 'At least one service item is required'}), 400
        
        # Generate bill number
        now = datetime.now()
        year = now.strftime('%y')
        month = now.strftime('%m')
        day = now.strftime('%d')
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        bill_number = f"HPS-SV-{year}{month}{day}-{random_part}"
        
        # Calculate totals
        subtotal = 0
        total_gst = 0
        
        for item in data['items']:
            quantity = int(item.get('quantity', 1))
            price = float(item.get('price', 0))
            gst_rate = float(item.get('gstRate', item.get('gst_rate', 0)))  # Handle both field names
            
            subtotal += price * quantity
            total_gst += (price * gst_rate / 100) * quantity
        
        # Apply discount
        discount = float(data.get('discount', 0))
        discount_type = data.get('discountType', 'percentage')
        
        discount_amount = 0
        if discount > 0:
            if discount_type == 'percentage':
                discount_amount = (subtotal * discount) / 100
            else:
                discount_amount = min(discount, subtotal)
        
        total = subtotal + total_gst - discount_amount
        
        # Create new bill
        bill = Bill(
            bill_number=bill_number,
            customer_name=data['customerName'],
            customer_phone=data.get('customerPhone', ''),
            customer_email=data.get('customerEmail', ''),
            customer_gst=data.get('customerGST', ''),
            customer_address=data.get('customerAddress', ''),
            customer_type=data.get('customerType', 'regular'),
            discount=discount,
            discount_type=discount_type,
            paid_amount=float(data.get('paidAmount', 0)),
            payment_method=data.get('paymentMethod', 'cash'),
            total=total,
            subtotal=subtotal,
            tax=total_gst
        )
        
        db.session.add(bill)
        db.session.flush()  # Get bill ID without committing
        
        # Process service items
        items_data = data.get('items', [])
        
        for item_data in items_data:
            # Validate service item fields
            if not item_data.get('serviceName'):
                return jsonify({'error': 'Service name is required for service items'}), 400
            
            quantity = int(item_data.get('quantity', 1))
            price = float(item_data.get('price', 0))
            gst_rate = float(item_data.get('gstRate', item_data.get('gst_rate', 0)))
            
            # Calculate GST and total
            gst_amount = (price * gst_rate / 100) * quantity
            item_total = (price * quantity) + gst_amount
            
            # Create service bill item
            service_item = ServiceBillItem(
                bill_id=bill.id,
                service_name=item_data['serviceName'],
                service_description=item_data.get('serviceDescription', item_data.get('description', '')),
                price=price,
                quantity=quantity,
                gst_rate=gst_rate,
                gst_amount=gst_amount,
                total=item_total
            )
            
            # If service_id is provided, link it
            if item_data.get('serviceId') or item_data.get('service_id'):
                service_item.service_id = item_data.get('serviceId', item_data.get('service_id'))
            
            db.session.add(service_item)
        
        db.session.commit()
        
        logger.info(f"Service bill created successfully: {bill_number}")
        
        return jsonify({
            'success': True,
            'message': 'Service bill created successfully',
            'billId': bill.id,
            'billNumber': bill.bill_number
        }), 201
        
    except ValueError as e:
        db.session.rollback()
        logger.error(f"Value error in create_service_bill: {str(e)}")
        return jsonify({'error': f'Invalid numeric value: {str(e)}'}), 400
    except KeyError as e:
        db.session.rollback()
        logger.error(f"Key error in create_service_bill: {str(e)}")
        return jsonify({'error': f'Missing required field: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating service bill: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== Service Bill Retrieval Routes ====================

@service_bp.route('/service-bills/<int:bill_id>', methods=['GET'])
def get_service_bill(bill_id):
    """Get a specific service bill by ID"""
    try:
        bill = Bill.query.get(bill_id)
        if not bill:
            return jsonify({'error': 'Bill not found'}), 404
        
        # Get service items for this bill
        items = ServiceBillItem.query.filter_by(bill_id=bill_id).all()
        
        return jsonify({
            'bill': {
                'id': bill.id,
                'billNumber': bill.bill_number,
                'customerName': bill.customer_name,
                'customerPhone': bill.customer_phone,
                'customerEmail': bill.customer_email,
                'customerGST': bill.customer_gst,
                'customerAddress': bill.customer_address,
                'customerType': bill.customer_type,
                'subtotal': bill.subtotal,
                'discount': bill.discount,
                'discountType': bill.discount_type,
                'tax': bill.tax,
                'total': bill.total,
                'paidAmount': bill.paid_amount,
                'paymentMethod': bill.payment_method,
                'paymentStatus': bill.payment_status,
                'createdAt': bill.created_at.isoformat() if bill.created_at else None
            },
            'items': [item.to_dict() for item in items]
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching service bill: {str(e)}")
        return jsonify({'error': 'Failed to fetch service bill'}), 500


@service_bp.route('/service-bills', methods=['GET'])
def get_all_service_bills():
    """Get all service bills with optional filtering"""
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filter parameters
        customer_name = request.args.get('customer_name', '')
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')
        
        query = Bill.query
        
        # Apply filters
        if customer_name:
            query = query.filter(Bill.customer_name.ilike(f'%{customer_name}%'))
        
        if from_date:
            from_datetime = datetime.strptime(from_date, '%Y-%m-%d')
            query = query.filter(Bill.created_at >= from_datetime)
        
        if to_date:
            to_datetime = datetime.strptime(to_date, '%Y-%m-%d')
            # Add one day to include the entire end date
            to_datetime = to_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(Bill.created_at <= to_datetime)
        
        # Order by most recent first
        query = query.order_by(Bill.created_at.desc())
        
        # Paginate
        paginated_bills = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'bills': [{
                'id': bill.id,
                'billNumber': bill.bill_number,
                'customerName': bill.customer_name,
                'customerPhone': bill.customer_phone,
                'total': bill.total,
                'paidAmount': bill.paid_amount,
                'paymentStatus': bill.payment_status,
                'createdAt': bill.created_at.isoformat() if bill.created_at else None
            } for bill in paginated_bills.items],
            'total': paginated_bills.total,
            'pages': paginated_bills.pages,
            'current_page': paginated_bills.page
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching service bills: {str(e)}")
        return jsonify({'error': 'Failed to fetch service bills'}), 500


@service_bp.route('/service-bills/number/<string:bill_number>', methods=['GET'])
def get_service_bill_by_number(bill_number):
    """Get a service bill by its bill number"""
    try:
        bill = Bill.query.filter_by(bill_number=bill_number).first()
        if not bill:
            return jsonify({'error': 'Bill not found'}), 404
        
        # Get service items for this bill
        items = ServiceBillItem.query.filter_by(bill_id=bill.id).all()
        
        return jsonify({
            'bill': {
                'id': bill.id,
                'billNumber': bill.bill_number,
                'customerName': bill.customer_name,
                'customerPhone': bill.customer_phone,
                'customerEmail': bill.customer_email,
                'customerGST': bill.customer_gst,
                'customerAddress': bill.customer_address,
                'customerType': bill.customer_type,
                'subtotal': bill.subtotal,
                'discount': bill.discount,
                'discountType': bill.discount_type,
                'tax': bill.tax,
                'total': bill.total,
                'paidAmount': bill.paid_amount,
                'paymentMethod': bill.payment_method,
                'paymentStatus': bill.payment_status,
                'createdAt': bill.created_at.isoformat() if bill.created_at else None
            },
            'items': [item.to_dict() for item in items]
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching service bill by number: {str(e)}")
        return jsonify({'error': 'Failed to fetch service bill'}), 500