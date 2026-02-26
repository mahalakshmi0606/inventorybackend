from app import db
from datetime import datetime

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100))
    type = db.Column(db.String(100))
    watts = db.Column(db.Float)

    buy_price = db.Column(db.Float, nullable=False)
    sell_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    profit_percent = db.Column(db.Float)
    amount = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def calculate_values(self):
        if self.buy_price and self.buy_price > 0:
            self.profit_percent = round(
                ((self.sell_price - self.buy_price) / self.buy_price) * 100, 2
            )
        else:
            self.profit_percent = 0

        self.amount = round(self.sell_price * self.quantity, 2)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "type": self.type,
            "watts": self.watts,
            "buyPrice": self.buy_price,
            "sellPrice": self.sell_price,
            "quantity": self.quantity,
            "profitPercent": self.profit_percent,
            "amount": self.amount,
            "created_at": self.created_at
        }