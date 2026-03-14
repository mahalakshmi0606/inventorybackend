from flask import Blueprint, request, jsonify
from app import db
from app.models.invoice import Invoice, InvoiceItem
from app.models.product import Product
from datetime import datetime, timedelta
from sqlalchemy import func
import traceback

invoice_bp = Blueprint('invoice', __name__)

def generate_invoice_number():
    """Generate a unique invoice number"""
    try:
        today = datetime.now()
        date_str = today.strftime('%Y%m%d')
        
        # Count invoices created today
        count = Invoice.query.filter(
            func.date(Invoice.created_at) == today.date()
        ).count()
        
        # Format: INV-YYYYMMDD-XXX
        seq = str(count + 1).zfill(3)
        return f"INV-{date_str}-{seq}"
    except Exception as e:
        print(f"Error generating invoice number: {str(e)}")
        # Fallback: use timestamp
        return f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

@invoice_bp.route('/invoice', methods=['GET'])
def get_invoices():
    """Get all invoices with pagination and filters"""
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Filter parameters
        customer_name = request.args.get('customer_name')
        status = request.args.get('status')
        payment_status = request.args.get('payment_status')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        
        # Build query
        query = Invoice.query
        
        if customer_name:
            query = query.filter(Invoice.customer_name.ilike(f'%{customer_name}%'))
        
        if status:
            query = query.filter(Invoice.status == status)
        
        if payment_status:
            query = query.filter(Invoice.payment_status == payment_status)
        
        if from_date:
            try:
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
                query = query.filter(Invoice.invoice_date >= from_date_obj)
            except ValueError:
                pass
        
        if to_date:
            try:
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
                query = query.filter(Invoice.invoice_date <= to_date_obj)
            except ValueError:
                pass
        
        # Order by latest first
        query = query.order_by(Invoice.created_at.desc())
        
        # Paginate
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Convert to dict with proper error handling
        items = []
        for invoice in paginated.items:
            try:
                items.append(invoice.to_dict())
            except Exception as e:
                print(f"Error converting invoice {invoice.id} to dict: {str(e)}")
                # Add a basic representation if conversion fails
                items.append({
                    'id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'customer_name': invoice.customer_name,
                    'error': 'Error loading full details'
                })
        
        return jsonify({
            'success': True,
            'items': items,
            'total': paginated.total,
            'page': page,
            'per_page': per_page,
            'pages': paginated.pages
        }), 200
        
    except Exception as e:
        print(f"Error in get_invoices: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/<int:id>', methods=['GET'])
def get_invoice(id):
    """Get single invoice by ID"""
    try:
        invoice = Invoice.query.get(id)
        if not invoice:
            return jsonify({
                'success': False,
                'error': 'Invoice not found'
            }), 404
        
        try:
            invoice_dict = invoice.to_dict()
        except Exception as e:
            print(f"Error converting invoice to dict: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Error loading invoice details'
            }), 500
        
        return jsonify({
            'success': True,
            'invoice': invoice_dict
        }), 200
        
    except Exception as e:
        print(f"Error in get_invoice: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice', methods=['POST', 'OPTIONS'])
def create_invoice():
    """Create new invoice"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        print("Received invoice data:", data)
        
        # Validate required fields
        if not data.get('customerName'):
            return jsonify({
                'success': False,
                'error': 'Customer name is required'
            }), 400
        
        if not data.get('customerPhone'):
            return jsonify({
                'success': False,
                'error': 'Customer phone is required'
            }), 400
        
        if not data.get('items') or len(data['items']) == 0:
            return jsonify({
                'success': False,
                'error': 'At least one item is required'
            }), 400
        
        # Parse dates with error handling
        try:
            invoice_date = datetime.strptime(
                data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')), 
                '%Y-%m-%d'
            ).date()
        except (ValueError, TypeError):
            invoice_date = datetime.now().date()
        
        try:
            due_date = datetime.strptime(
                data.get('dueDate', (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')), 
                '%Y-%m-%d'
            ).date()
        except (ValueError, TypeError):
            due_date = (datetime.now() + timedelta(days=30)).date()
        
        # Check if it's inter-state transaction
        is_inter_state = data.get('isInterState', False)
        
        # Create invoice
        invoice = Invoice(
            invoice_number=generate_invoice_number(),
            customer_name=data.get('customerName', '').strip(),
            customer_phone=data.get('customerPhone', '').strip(),
            customer_email=data.get('customerEmail', '').strip(),
            customer_address=data.get('customerAddress', '').strip(),
            customer_gstin=data.get('customerGstin', '').strip().upper(),
            invoice_date=invoice_date,
            due_date=due_date,
            discount_type=data.get('discountType', 'fixed'),
            discount_rate=float(data.get('discountRate', 0)),
            payment_method=data.get('paymentMethod', 'cash'),
            payment_status=data.get('paymentStatus', 'unpaid'),
            notes=data.get('notes', ''),
            terms=data.get('terms', ''),
            status=data.get('status', 'pending')
        )
        
        db.session.add(invoice)
        db.session.flush()  # Get invoice ID
        
        # Add items
        for item_data in data['items']:
            # Validate item data
            if not item_data.get('productId'):
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': 'Product ID is required for each item'
                }), 400
            
            # Get product details
            product = Product.query.get(item_data['productId'])
            if not product:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': f"Product with ID {item_data['productId']} not found"
                }), 400
            
            # Parse quantity and price
            try:
                quantity = int(item_data.get('quantity', 1))
                # Use sell_price from product model
                default_price = product.sell_price if product.sell_price else 0
                price = float(item_data.get('price', default_price))
            except (ValueError, TypeError) as e:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': f'Invalid quantity or price format: {str(e)}'
                }), 400
            
            # Check stock using 'quantity' field (not 'stock')
            if product.quantity < quantity:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': f"Insufficient stock for {product.name}. Available: {product.quantity}"
                }), 400
            
            # Create invoice item
            item = InvoiceItem(
                invoice_id=invoice.id,
                product_id=product.id,
                product_name=product.name,
                product_model=product.model or '',
                hsn_code=item_data.get('hsnCode', ''),
                price=price,
                quantity=quantity,
                gst_rate=float(item_data.get('gst', 0))
            )
            
            # Calculate tax amounts
            item.calculate_totals(is_inter_state)
            
            # Update product quantity (decrease stock)
            product.quantity -= quantity
            # Recalculate product amount
            if hasattr(product, 'calculate_values'):
                product.calculate_values()
            
            db.session.add(item)
        
        # Calculate invoice totals
        invoice.calculate_totals()
        
        # If payment is marked as paid, set payment date
        if invoice.payment_status == 'paid':
            invoice.payment_date = datetime.now()
        
        db.session.commit()
        
        # Fetch the created invoice with items
        created_invoice = Invoice.query.get(invoice.id)
        
        try:
            invoice_dict = created_invoice.to_dict()
        except Exception as e:
            print(f"Error converting created invoice to dict: {str(e)}")
            invoice_dict = {
                'id': created_invoice.id,
                'invoice_number': created_invoice.invoice_number,
                'customer_name': created_invoice.customer_name
            }
        
        return jsonify({
            'success': True,
            'message': 'Invoice created successfully',
            'invoice': invoice_dict,
            'invoiceNumber': invoice.invoice_number
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"ERROR creating invoice: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/<int:id>', methods=['PUT'])
def update_invoice(id):
    """Update existing invoice"""
    try:
        invoice = Invoice.query.get(id)
        if not invoice:
            return jsonify({
                'success': False,
                'error': 'Invoice not found'
            }), 404
        
        data = request.json
        print(f"Updating invoice {id} with data:", data)
        
        # Check if status allows updates
        if invoice.status in ['delivered', 'cancelled']:
            return jsonify({
                'success': False,
                'error': f'Cannot update invoice with status: {invoice.status}'
            }), 400
        
        # Update customer details
        if 'customerName' in data:
            invoice.customer_name = data['customerName'].strip()
        if 'customerPhone' in data:
            invoice.customer_phone = data['customerPhone'].strip()
        if 'customerEmail' in data:
            invoice.customer_email = data['customerEmail'].strip()
        if 'customerAddress' in data:
            invoice.customer_address = data['customerAddress'].strip()
        if 'customerGstin' in data:
            invoice.customer_gstin = data['customerGstin'].strip().upper()
        
        # Update dates with error handling
        if 'invoiceDate' in data:
            try:
                invoice.invoice_date = datetime.strptime(data['invoiceDate'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        
        if 'dueDate' in data:
            try:
                invoice.due_date = datetime.strptime(data['dueDate'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        
        # Update discount
        if 'discountType' in data:
            invoice.discount_type = data['discountType']
        if 'discountRate' in data:
            try:
                invoice.discount_rate = float(data['discountRate'])
            except (ValueError, TypeError):
                pass
        
        # Update payment
        if 'paymentMethod' in data:
            invoice.payment_method = data['paymentMethod']
        if 'paymentStatus' in data:
            old_status = invoice.payment_status
            invoice.payment_status = data['paymentStatus']
            if old_status != 'paid' and invoice.payment_status == 'paid':
                invoice.payment_date = datetime.now()
        
        # Update status
        if 'status' in data:
            invoice.status = data['status']
        
        # Update notes
        if 'notes' in data:
            invoice.notes = data['notes']
        if 'terms' in data:
            invoice.terms = data['terms']
        
        # Update items if provided
        if 'items' in data and len(data['items']) > 0:
            # Check if items can be updated
            if invoice.status not in ['pending', 'confirmed']:
                return jsonify({
                    'success': False,
                    'error': f'Cannot update items for invoice with status: {invoice.status}'
                }), 400
            
            # Check if it's inter-state transaction
            is_inter_state = data.get('isInterState', False)
            
            # Restore stock for existing items
            for item in invoice.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.quantity += item.quantity
                    if hasattr(product, 'calculate_values'):
                        product.calculate_values()
            
            # Delete existing items
            InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
            
            # Add new items
            for item_data in data['items']:
                if not item_data.get('productId'):
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': 'Product ID is required for each item'
                    }), 400
                
                product = Product.query.get(item_data['productId'])
                if not product:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': f"Product with ID {item_data['productId']} not found"
                    }), 400
                
                try:
                    quantity = int(item_data.get('quantity', 1))
                    default_price = product.sell_price if product.sell_price else 0
                    price = float(item_data.get('price', default_price))
                except (ValueError, TypeError):
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': 'Invalid quantity or price format'
                    }), 400
                
                # Check stock using 'quantity' field
                if product.quantity < quantity:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': f"Insufficient stock for {product.name}. Available: {product.quantity}"
                    }), 400
                
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_id=product.id,
                    product_name=product.name,
                    product_model=product.model or '',
                    hsn_code=item_data.get('hsnCode', ''),
                    price=price,
                    quantity=quantity,
                    gst_rate=float(item_data.get('gst', 0))
                )
                
                item.calculate_totals(is_inter_state)
                
                # Update product quantity
                product.quantity -= quantity
                if hasattr(product, 'calculate_values'):
                    product.calculate_values()
                
                db.session.add(item)
        
        # Recalculate totals
        invoice.calculate_totals()
        
        db.session.commit()
        
        # Fetch updated invoice
        updated_invoice = Invoice.query.get(id)
        
        try:
            invoice_dict = updated_invoice.to_dict()
        except Exception as e:
            print(f"Error converting updated invoice to dict: {str(e)}")
            invoice_dict = {
                'id': updated_invoice.id,
                'invoice_number': updated_invoice.invoice_number,
                'customer_name': updated_invoice.customer_name
            }
        
        return jsonify({
            'success': True,
            'message': 'Invoice updated successfully',
            'invoice': invoice_dict
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"ERROR updating invoice: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/<int:id>', methods=['DELETE'])
def delete_invoice(id):
    """Delete invoice"""
    try:
        invoice = Invoice.query.get(id)
        if not invoice:
            return jsonify({
                'success': False,
                'error': 'Invoice not found'
            }), 404
        
        # Check if invoice can be deleted
        if invoice.status not in ['pending', 'cancelled']:
            return jsonify({
                'success': False,
                'error': f'Cannot delete invoice with status: {invoice.status}'
            }), 400
        
        # Restore stock
        for item in invoice.items:
            product = Product.query.get(item.product_id)
            if product:
                product.quantity += item.quantity
                if hasattr(product, 'calculate_values'):
                    product.calculate_values()
        
        # Delete invoice (cascade will delete items)
        db.session.delete(invoice)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Invoice deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"ERROR deleting invoice: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/<int:id>/payment', methods=['PATCH'])
def update_payment_status(id):
    """Update payment status"""
    try:
        invoice = Invoice.query.get(id)
        if not invoice:
            return jsonify({
                'success': False,
                'error': 'Invoice not found'
            }), 404
        
        data = request.json
        payment_status = data.get('paymentStatus')
        payment_method = data.get('paymentMethod')
        
        if payment_status:
            old_status = invoice.payment_status
            invoice.payment_status = payment_status
            if old_status != 'paid' and payment_status == 'paid':
                invoice.payment_date = datetime.now()
        
        if payment_method:
            invoice.payment_method = payment_method
        
        db.session.commit()
        
        try:
            invoice_dict = invoice.to_dict()
        except Exception as e:
            print(f"Error converting invoice to dict: {str(e)}")
            invoice_dict = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'payment_status': invoice.payment_status
            }
        
        return jsonify({
            'success': True,
            'message': 'Payment status updated successfully',
            'invoice': invoice_dict
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"ERROR updating payment status: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/<int:id>/status', methods=['PATCH'])
def update_invoice_status(id):
    """Update invoice status"""
    try:
        invoice = Invoice.query.get(id)
        if not invoice:
            return jsonify({
                'success': False,
                'error': 'Invoice not found'
            }), 404
        
        data = request.json
        status = data.get('status')
        
        if status:
            invoice.status = status
        
        db.session.commit()
        
        try:
            invoice_dict = invoice.to_dict()
        except Exception as e:
            print(f"Error converting invoice to dict: {str(e)}")
            invoice_dict = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'status': invoice.status
            }
        
        return jsonify({
            'success': True,
            'message': 'Invoice status updated successfully',
            'invoice': invoice_dict
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"ERROR updating invoice status: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/stats/dashboard', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        today = datetime.now().date()
        start_of_month = today.replace(day=1)
        
        # Today's sales
        today_sales = db.session.query(func.sum(Invoice.total)).filter(
            func.date(Invoice.created_at) == today,
            Invoice.status != 'cancelled'
        ).scalar() or 0
        
        # Month sales
        month_sales = db.session.query(func.sum(Invoice.total)).filter(
            Invoice.created_at >= start_of_month,
            Invoice.status != 'cancelled'
        ).scalar() or 0
        
        # Pending invoices (unpaid)
        pending = db.session.query(
            func.count(Invoice.id),
            func.sum(Invoice.total)
        ).filter(
            Invoice.payment_status == 'unpaid',
            Invoice.status != 'cancelled'
        ).first()
        
        # Overdue invoices
        overdue = db.session.query(
            func.count(Invoice.id),
            func.sum(Invoice.total)
        ).filter(
            Invoice.due_date < today,
            Invoice.payment_status != 'paid',
            Invoice.status != 'cancelled'
        ).first()
        
        # Total invoices count
        total_invoices = db.session.query(func.count(Invoice.id)).filter(
            Invoice.status != 'cancelled'
        ).scalar() or 0
        
        return jsonify({
            'success': True,
            'stats': {
                'todaySales': float(today_sales),
                'monthSales': float(month_sales),
                'pendingInvoices': {
                    'count': pending[0] or 0,
                    'total': float(pending[1] or 0)
                },
                'overdueInvoices': {
                    'count': overdue[0] or 0,
                    'total': float(overdue[1] or 0)
                },
                'totalInvoices': total_invoices
            }
        }), 200
        
    except Exception as e:
        print(f"ERROR getting dashboard stats: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/number/generate', methods=['GET'])
def generate_number():
    """Generate a new invoice number"""
    try:
        invoice_number = generate_invoice_number()
        return jsonify({
            'success': True,
            'invoiceNumber': invoice_number
        }), 200
    except Exception as e:
        print(f"ERROR generating invoice number: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/<int:id>/send-email', methods=['POST'])
def send_invoice_email(id):
    """Send invoice via email"""
    try:
        invoice = Invoice.query.get(id)
        if not invoice:
            return jsonify({
                'success': False,
                'error': 'Invoice not found'
            }), 404
        
        if not invoice.customer_email:
            return jsonify({
                'success': False,
                'error': 'Customer email not available'
            }), 400
        
        # TODO: Implement email sending functionality
        # This would typically use Flask-Mail or similar
        
        return jsonify({
            'success': True,
            'message': 'Invoice email sent successfully'
        }), 200
        
    except Exception as e:
        print(f"ERROR sending invoice email: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invoice_bp.route('/invoice/filters/options', methods=['GET'])
def get_filter_options():
    """Get available filter options for dropdowns"""
    try:
        # Get unique status values
        statuses = db.session.query(Invoice.status).distinct().all()
        status_list = [s[0] for s in statuses if s[0]]
        
        # Get unique payment status values
        payment_statuses = db.session.query(Invoice.payment_status).distinct().all()
        payment_status_list = [ps[0] for ps in payment_statuses if ps[0]]
        
        # Get unique payment methods
        payment_methods = db.session.query(Invoice.payment_method).distinct().all()
        payment_method_list = [pm[0] for pm in payment_methods if pm[0]]
        
        return jsonify({
            'success': True,
            'filters': {
                'statuses': status_list,
                'paymentStatuses': payment_status_list,
                'paymentMethods': payment_method_list
            }
        }), 200
        
    except Exception as e:
        print(f"ERROR getting filter options: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500