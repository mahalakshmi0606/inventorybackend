from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from config import Config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize database
    db.init_app(app)
    migrate.init_app(app, db)

    # Enable CORS for React frontend
    CORS(
        app,
        supports_credentials=True,
        origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000"
        ],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        expose_headers=["Content-Type", "Authorization"]
    )

    # Import models so Flask-Migrate detects them
    from app import models

    # Register Blueprints
    from app.routes.login_routes import login_bp
    from app.routes.product_routes import product_bp
    from app.routes.billing_routes import billing_bp
    from app.routes.supplier_routes import supplier_bp


    app.register_blueprint(login_bp, url_prefix="/api")
    app.register_blueprint(product_bp, url_prefix="/api")
    app.register_blueprint(billing_bp, url_prefix="/api")
    app.register_blueprint(supplier_bp)
   

    # Health Check Route
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return {
            "status": "healthy",
            "message": "API is working"
        }, 200

    return app