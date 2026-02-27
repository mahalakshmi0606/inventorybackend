📦 Inventory Backend API

A simple and scalable Inventory Management Backend built using Flask, MySQL, and SQLAlchemy.
This project provides RESTful APIs for managing users, suppliers, products, billing, and inventory operations.

🚀 Features

User Registration & Login

Supplier Management

Product Management

Billing Management

Inventory Tracking

Database Migration Support (Flask-Migrate)

CORS Enabled

Modular Folder Structure

RESTful API Design

🛠️ Tech Stack

Backend Framework: Flask

Database: MySQL

ORM: SQLAlchemy

Migration Tool: Flask-Migrate (Alembic)

Authentication: Flask-Login / JWT (if implemented)

Environment Management: Python Virtual Environment

📂 Project Structure
inventory-backend/
│
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── routes/
│   ├── services/
│
├── migrations/
├── config.py
├── requirements.txt
├── run.py
└── README.md
⚙️ Installation & Setup
1️⃣ Clone the Repository
git clone https://github.com/mahalakshmi0606/inventorybackend.git
cd inventorybackend
2️⃣ Create Virtual Environment
python -m venv venv

Activate virtual environment:

Windows:

venv\Scripts\activate

Mac/Linux:

source venv/bin/activate
3️⃣ Install Dependencies
pip install -r requirements.txt
4️⃣ Configure Environment Variables

Update your config.py with your MySQL database details:

SQLALCHEMY_DATABASE_URI = "mysql+pymysql://username:password@localhost/database_name"
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = "your_secret_key"
5️⃣ Run Database Migration
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
6️⃣ Run the Application
python run.py

Or

flask run

Server will run at:

http://127.0.0.1:5000/
📡 API Endpoints (Example)
🔐 Authentication

POST /api/register

POST /api/login

👤 Users

GET /api/users

POST /api/users

PUT /api/users/<id>

DELETE /api/users/<id>

🏢 Suppliers

GET /api/suppliers

POST /api/suppliers

📦 Products

GET /api/products

POST /api/products

🧾 Billing

GET /api/bills

POST /api/bills

🧪 Testing APIs

You can test the APIs using:

Postman

Thunder Client (VS Code)

cURL

📌 Future Improvements

Role-Based Access Control

JWT Authentication

Dashboard Analytics

Deployment using Docker

Unit Testing

API Documentation (Swagger)

👩‍💻 Author

Mahalakshmi M
B.Tech Information Technology
Full Stack Developer | Backend Developer

GitHub: https://github.com/mahalakshmi0606

📄 License

This project is open-source and available for learning and development purposes.
