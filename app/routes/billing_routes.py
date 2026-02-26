# app/routes/billing_routes.py
from flask import Blueprint, request, jsonify, make_response
from app.models.billing import Bill, BillItem, Payment
from app.models.product import Product
from app import db
from flask_cors import CORS
from sqlalchemy import or_, and_, func
from datetime import datetime, timedelta
import traceback
import random
import string

billing_bp = Blueprint("billing_bp", __name__)

# Configure CORS for this blueprint with credentials support
CORS(billing_bp, 
     supports_credentials=True,
     origins=["http://localhost:3000", "http://127.0.0.1:3000"])

# Add after_request handler to ensure CORS headers are set properly
@billing_bp.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Generic OPTIONS handler for all routes in this blueprint
@billing_bp.route('/<path:path>', methods=['OPTIONS'])
def handle_all_options(path):
    """Handle OPTIONS requests for any route in this blueprint"""
    response = make_response()
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

def generate_unique_bill_number():
    """Generate a unique random bill number"""
    while True:
        # Format: BT-YYMMDD-XXXXXXXX (BT = Brain Tech)
        now = datetime.now()
        year = str(now.year)[-2:]
        month = str(now.month).zfill(2)
        day = str(now.day).zfill(2)
        
        # Generate 8 random alphanumeric characters
        random_chars = ''.join(random.choices(
            string.ascii_uppercase + string.digits, 
            k=8
        ))
        
        bill_number = f"BT-{year}{month}{day}-{random_chars}"
        
        # Check if this number already exists
        existing = Bill.query.filter_by(bill_number=bill_number).first()
        if not existing:
            return bill_number


# ------------------ SEARCH PRODUCTS FOR BILLING ------------------
@billing_bp.route("/billing/search-products", methods=["GET"])
def search_products_for_billing():
    """Search products by name, model, or type for billing"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify([]), 200
            
        # Search in name, model, and type, only show products with stock > 0
        products = Product.query.filter(
            or_(
                Product.name.ilike(f'%{query}%'),
                Product.model.ilike(f'%{query}%'),
                Product.type.ilike(f'%{query}%')
            )
        ).filter(Product.quantity > 0).limit(10).all()
        
        result = [{
            'id': p.id,
            'name': p.name,
            'model': p.model or '',
            'type': p.type or '',
            'sellPrice': p.sell_price,
            'quantity': p.quantity,
            'inStock': p.quantity > 0
        } for p in products]
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Search error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to search products"}), 400


# ------------------ GET PRODUCT BY BARCODE ------------------
@billing_bp.route("/billing/product/barcode/<string:barcode>", methods=["GET"])
def get_product_by_barcode(barcode):
    """Get product by barcode for quick billing"""
    try:
        if not barcode:
            return jsonify({"error": "Barcode is required"}), 400
            
        product = Product.query.filter_by(barcode=barcode).first()
        
        if not product:
            return jsonify({"error": "Product not found"}), 404
            
        if product.quantity <= 0:
            return jsonify({"error": "Product out of stock"}), 400
            
        return jsonify({
            'id': product.id,
            'name': product.name,
            'model': product.model or '',
            'type': product.type or '',
            'sellPrice': product.sell_price,
            'quantity': product.quantity
        }), 200
        
    except Exception as e:
        print(f"Barcode error: {str(e)}")
        return jsonify({"error": "Failed to fetch product"}), 400


# ------------------ CREATE NEW BILL ------------------
@billing_bp.route("/billing/bills", methods=["POST"])
def create_bill():
    """Create a new bill with items and payment"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('items'):
            return jsonify({"error": "No items in bill"}), 400
            
        if len(data['items']) == 0:
            return jsonify({"error": "Bill must have at least one item"}), 400
        
        # Create new bill instance with unique number
        bill = Bill()
        bill.bill_number = generate_unique_bill_number()
        bill.customer_name = data.get('customerName', 'Walk-in Customer')
        bill.customer_phone = data.get('customerPhone', '')
        bill.customer_email = data.get('customerEmail', '')
        bill.customer_gst = data.get('customerGST', '')
        bill.customer_address = data.get('customerAddress', '')
        
        # Discount and tax settings
        bill.discount = float(data.get('discount', 0))
        bill.discount_type = data.get('discountType', 'amount')
        bill.tax = float(data.get('tax', 0))
        bill.tax_type = data.get('taxType', 'percentage')
        
        # Payment information
        bill.paid_amount = float(data.get('paidAmount', 0))
        bill.payment_method = data.get('paymentMethod', 'cash')
        
        # Add items and update stock
        items_added = []
        for item_data in data.get('items', []):
            product = Product.query.get(item_data['productId'])
            
            if not product:
                db.session.rollback()
                return jsonify({"error": f"Product with ID {item_data['productId']} not found"}), 404
            
            quantity = int(item_data['quantity'])
            if quantity <= 0:
                db.session.rollback()
                return jsonify({"error": f"Invalid quantity for {product.name}"}), 400
                
            if product.quantity < quantity:
                db.session.rollback()
                return jsonify({"error": f"Insufficient stock for {product.name}. Available: {product.quantity}"}), 400
            
            # Calculate item total
            item_total = product.sell_price * quantity
            
            # Create bill item with status (defaults to 'pending' from model)
            bill_item = BillItem(
                product_id=product.id,
                product_name=product.name,
                product_model=product.model or '',
                product_type=product.type or '',
                sell_price=product.sell_price,
                quantity=quantity,
                total=item_total
                # item_status will default to 'pending' as defined in the model
            )
            
            # Update product quantity
            product.quantity -= quantity
            
            bill.items.append(bill_item)
            items_added.append({
                'name': product.name,
                'quantity': quantity,
                'total': item_total,
                'status': 'pending'  # Include status in response
            })
        
        # Calculate all totals
        bill.calculate_totals()
        
        # Save to database
        db.session.add(bill)
        db.session.commit()
        
        # Create payment record if amount paid
        if bill.paid_amount > 0:
            payment = Payment(
                bill_id=bill.id,
                payment_id=f"PAY-{bill.bill_number}",
                amount=bill.paid_amount,
                method=bill.payment_method,
                status='completed' if bill.paid_amount >= bill.total else 'partial'
            )
            db.session.add(payment)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bill created successfully',
            'billNumber': bill.bill_number,
            'billId': bill.id,
            'total': round(bill.total, 2),
            'changeAmount': round(bill.change_amount, 2),
            'items': items_added
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Create bill error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400


# ------------------ GET BILLS WITH PENDING ITEMS ------------------
@billing_bp.route("/billing/bills/pending-items", methods=["GET"])
def get_bills_with_pending_items():
    """Get all bills that have pending items"""
    try:
        # Find all bills that have at least one pending item
        bills = Bill.query.join(BillItem).filter(
            BillItem.item_status == 'pending'
        ).distinct(Bill.id).order_by(Bill.created_at.desc()).all()
        
        result = []
        for bill in bills:
            # Count pending items for this bill
            pending_count = BillItem.query.filter_by(
                bill_id=bill.id, 
                item_status='pending'
            ).count()
            
            result.append({
                'id': bill.id,
                'billNumber': bill.bill_number,
                'customerName': bill.customer_name,
                'customerPhone': bill.customer_phone,
                'total': round(bill.total, 2),
                'paidAmount': round(bill.paid_amount, 2),
                'pendingItems': pending_count,
                'createdAt': bill.created_at.isoformat() if bill.created_at else None
            })
        
        return jsonify({
            'success': True,
            'bills': result
        }), 200
        
    except Exception as e:
        print(f"Get pending bills error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch pending bills"}), 400


# ------------------ GET PENDING ITEMS FOR A BILL ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/items/pending", methods=["GET"])
def get_pending_bill_items(bill_id):
    """Get all pending items for a specific bill"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        pending_items = BillItem.query.filter_by(
            bill_id=bill_id,
            item_status='pending'
        ).all()
        
        items = [{
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'product_model': item.product_model,
            'product_type': item.product_type,
            'sell_price': item.sell_price,
            'quantity': item.quantity,
            'total': item.total,
            'item_status': item.item_status
        } for item in pending_items]
        
        return jsonify({
            'success': True,
            'bill_id': bill_id,
            'bill_number': bill.bill_number,
            'items': items
        }), 200
        
    except Exception as e:
        print(f"Get pending items error: {str(e)}")
        return jsonify({"error": "Failed to fetch pending items"}), 400


# ------------------ COMPLETE A BILL ITEM ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/items/<int:item_id>/complete", methods=["POST"])
def complete_bill_item(bill_id, item_id):
    """Mark a bill item as completed (inventory already updated during bill creation)"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        item = BillItem.query.get_or_404(item_id)
        
        if item.bill_id != bill.id:
            return jsonify({"error": "Item does not belong to this bill"}), 400
        
        if item.item_status != 'pending':
            return jsonify({"error": "Item is already completed"}), 400
        
        # Update item status to completed
        item.item_status = 'completed'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item marked as completed successfully',
            'item': {
                'id': item.id,
                'status': item.item_status
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Complete item error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ COMPLETE ALL ITEMS IN A BILL ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/complete-all", methods=["POST"])
def complete_all_bill_items(bill_id):
    """Mark all pending items in a bill as completed"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        # Get all pending items
        pending_items = BillItem.query.filter_by(
            bill_id=bill_id,
            item_status='pending'
        ).all()
        
        if not pending_items:
            return jsonify({"error": "No pending items found in this bill"}), 400
        
        completed_count = 0
        for item in pending_items:
            item.item_status = 'completed'
            completed_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully completed {completed_count} items',
            'completedCount': completed_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Complete all items error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ GET ALL BILLS (with pagination) ------------------
@billing_bp.route("/billing/bills", methods=["GET"])
def get_all_bills():
    """Get all bills with pagination and filters"""
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        customer = request.args.get('customer')
        payment_method = request.args.get('payment_method')
        payment_status = request.args.get('payment_status')
        
        # Build query
        query = Bill.query
        
        if start_date:
            query = query.filter(Bill.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(Bill.created_at <= datetime.fromisoformat(end_date))
        if customer:
            query = query.filter(Bill.customer_name.ilike(f'%{customer}%'))
        if payment_method:
            query = query.filter(Bill.payment_method == payment_method)
        if payment_status:
            query = query.filter(Bill.payment_status == payment_status)
        
        # Order by most recent first
        query = query.order_by(Bill.created_at.desc())
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format response
        bills = []
        for bill in pagination.items:
            # Count pending items
            pending_count = BillItem.query.filter_by(
                bill_id=bill.id, 
                item_status='pending'
            ).count()
            
            bills.append({
                'id': bill.id,
                'billNumber': bill.bill_number,
                'customerName': bill.customer_name,
                'customerPhone': bill.customer_phone,
                'subtotal': round(bill.subtotal, 2),
                'discount': round(bill.discount, 2),
                'tax': round(bill.tax, 2),
                'total': round(bill.total, 2),
                'paidAmount': round(bill.paid_amount, 2),
                'paymentMethod': bill.payment_method,
                'paymentStatus': bill.payment_status,
                'itemCount': len(bill.items),
                'pendingItems': pending_count,
                'createdAt': bill.created_at.isoformat() if bill.created_at else None
            })
        
        return jsonify({
            'bills': bills,
            'total': pagination.total,
            'pages': pagination.pages,
            'currentPage': page,
            'perPage': per_page
        }), 200
        
    except Exception as e:
        print(f"Get bills error: {str(e)}")
        return jsonify({"error": "Failed to fetch bills"}), 400


# ------------------ GET SINGLE BILL BY ID ------------------
@billing_bp.route("/billing/bills/<int:bill_id>", methods=["GET"])
def get_bill_by_id(bill_id):
    """Get detailed bill information by ID"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        # Get payment history
        payments = Payment.query.filter_by(bill_id=bill.id).all()
        
        # Get all items with their status
        items = [{
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'product_model': item.product_model,
            'product_type': item.product_type,
            'sell_price': item.sell_price,
            'quantity': item.quantity,
            'total': item.total,
            'item_status': item.item_status
        } for item in bill.items]
        
        bill_dict = bill.to_dict()
        bill_dict['items'] = items
        bill_dict['payments'] = [p.to_dict() for p in payments]
        
        return jsonify(bill_dict), 200
        
    except Exception as e:
        print(f"Get bill error: {str(e)}")
        return jsonify({"error": "Bill not found"}), 404


# ------------------ GET BILL BY NUMBER ------------------
@billing_bp.route("/billing/bills/number/<string:bill_number>", methods=["GET"])
def get_bill_by_number(bill_number):
    """Get bill by bill number"""
    try:
        bill = Bill.query.filter_by(bill_number=bill_number).first_or_404()
        
        # Get all items with their status
        items = [{
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'product_model': item.product_model,
            'product_type': item.product_type,
            'sell_price': item.sell_price,
            'quantity': item.quantity,
            'total': item.total,
            'item_status': item.item_status
        } for item in bill.items]
        
        bill_dict = bill.to_dict()
        bill_dict['items'] = items
        
        return jsonify(bill_dict), 200
        
    except Exception as e:
        print(f"Get bill by number error: {str(e)}")
        return jsonify({"error": "Bill not found"}), 404


# ------------------ UPDATE BILL PAYMENT ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/payment", methods=["PUT"])
def update_bill_payment(bill_id):
    """Update payment information for a bill"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        data = request.get_json()
        
        # Update payment details
        bill.paid_amount = float(data.get('paidAmount', bill.paid_amount))
        bill.payment_method = data.get('paymentMethod', bill.payment_method)
        
        # Recalculate
        bill.calculate_totals()
        
        # Add payment record
        payment = Payment(
            bill_id=bill.id,
            payment_id=f"PAY-{bill.bill_number}-{datetime.now().strftime('%H%M%S')}",
            amount=data.get('additionalAmount', bill.paid_amount),
            method=bill.payment_method,
            status='completed',
            reference=data.get('reference', ''),
            notes=data.get('notes', '')
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment updated successfully',
            'bill': bill.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Update payment error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ CANCEL/REFUND BILL ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/cancel", methods=["POST"])
def cancel_bill(bill_id):
    """Cancel a bill and restore stock"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        # Restore product quantities for items that are not completed
        for item in bill.items:
            if item.item_status != 'completed':
                product = Product.query.get(item.product_id)
                if product:
                    product.quantity += item.quantity
        
        # Update payment status
        for payment in bill.payments:
            payment.status = 'refunded'
        
        # Delete bill (or mark as cancelled)
        db.session.delete(bill)  # Or add a 'cancelled' field to Bill model
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bill cancelled successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Cancel bill error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ GET BILLING STATISTICS ------------------
@billing_bp.route("/billing/statistics", methods=["GET"])
def get_billing_statistics():
    """Get billing statistics for dashboard"""
    try:
        # Date range
        today = datetime.now().date()
        start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0)
        end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59)
        
        start_of_week = today - timedelta(days=today.weekday())
        start_of_week = datetime(start_of_week.year, start_of_week.month, start_of_week.day, 0, 0, 0)
        
        start_of_month = datetime(today.year, today.month, 1, 0, 0, 0)
        
        # Today's stats
        today_stats = db.session.query(
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total).label('total_sales'),
            func.avg(Bill.total).label('avg_bill_value')
        ).filter(Bill.created_at.between(start_of_day, end_of_day)).first()
        
        # Week's stats
        week_stats = db.session.query(
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total).label('total_sales')
        ).filter(Bill.created_at >= start_of_week).first()
        
        # Month's stats
        month_stats = db.session.query(
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total).label('total_sales')
        ).filter(Bill.created_at >= start_of_month).first()
        
        # Pending items count
        pending_items_count = BillItem.query.filter_by(item_status='pending').count()
        
        # Payment method distribution
        payment_methods = db.session.query(
            Bill.payment_method,
            func.count(Bill.id).label('count'),
            func.sum(Bill.total).label('total')
        ).group_by(Bill.payment_method).all()
        
        # Recent bills
        recent_bills = Bill.query.order_by(Bill.created_at.desc()).limit(5).all()
        
        return jsonify({
            'today': {
                'bills': today_stats.bill_count or 0,
                'sales': round(today_stats.total_sales or 0, 2),
                'average': round(today_stats.avg_bill_value or 0, 2)
            },
            'thisWeek': {
                'bills': week_stats.bill_count or 0,
                'sales': round(week_stats.total_sales or 0, 2)
            },
            'thisMonth': {
                'bills': month_stats.bill_count or 0,
                'sales': round(month_stats.total_sales or 0, 2)
            },
            'pendingItems': pending_items_count,
            'paymentMethods': [{
                'method': pm[0] or 'other',
                'count': pm[1],
                'total': round(pm[2] or 0, 2)
            } for pm in payment_methods],
            'recentBills': [{
                'id': b.id,
                'billNumber': b.bill_number,
                'customerName': b.customer_name,
                'total': round(b.total, 2),
                'createdAt': b.created_at.isoformat()
            } for b in recent_bills]
        }), 200
        
    except Exception as e:
        print(f"Statistics error: {str(e)}")
        return jsonify({"error": "Failed to fetch statistics"}), 400


# ------------------ VOID BILL ITEM ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/items/<int:item_id>/void", methods=["POST"])
def void_bill_item(bill_id, item_id):
    """Void a specific item from bill and adjust stock"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        item = BillItem.query.get_or_404(item_id)
        
        if item.bill_id != bill.id:
            return jsonify({"error": "Item does not belong to this bill"}), 400
        
        # Only restore stock if item is not completed
        if item.item_status != 'completed':
            product = Product.query.get(item.product_id)
            if product:
                product.quantity += item.quantity
        
        # Remove item
        db.session.delete(item)
        
        # Recalculate bill totals
        bill.calculate_totals()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item voided successfully',
            'bill': bill.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Void item error: {str(e)}")
        return jsonify({"error": str(e)}), 400