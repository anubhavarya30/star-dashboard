"""
Position & Risk Management
Risk per trade: 1-2% of portfolio
Dynamic position sizing
"""


class PositionManager:
    """Manage positions, sizing, and risk"""

    def __init__(self, account_balance: float, risk_per_trade: float = 0.02):
        """
        Args:
            account_balance: Total trading account size
            risk_per_trade: Risk per trade as % (0.01 = 1%)
        """
        self.account_balance = account_balance
        self.risk_per_trade = risk_per_trade

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> dict:
        """
        Calculate position size based on risk per trade

        Returns:
            {
                'quantity': int,
                'risk_amount': float,
                'potential_loss': float
            }
        """
        risk_amount = self.account_balance * self.risk_per_trade
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance == 0:
            return {"quantity": 0, "risk_amount": 0, "potential_loss": 0}

        quantity = int(risk_amount / stop_distance)
        potential_loss = quantity * stop_distance

        return {
            "quantity": max(quantity, 1),  # Minimum 1 unit
            "risk_amount": risk_amount,
            "potential_loss": potential_loss,
            "position_size_usd": quantity * entry_price
        }

    def calculate_exit_levels(self, entry_price: float, signal: dict) -> dict:
        """
        Calculate profit targets and trailing stops

        Returns:
            {
                'stop_loss': float,
                'take_profit_1': float,
                'take_profit_2': float,
                'trailing_stop_pct': float
            }
        """
        stop_loss = signal.get('stop_loss', entry_price * 0.98)
        risk_amount = entry_price - stop_loss

        return {
            "stop_loss": stop_loss,
            "take_profit_1": entry_price + (risk_amount * 1),  # 1:1 RR
            "take_profit_2": entry_price + (risk_amount * 2),  # 1:2 RR
            "take_profit_signal": signal.get('take_profit'),
            "trailing_stop_pct": 0.01  # 1% trailing stop
        }

    def should_exit(self, current_price: float, position: dict) -> dict:
        """
        Check if position should be exited

        Returns:
            {
                'should_exit': bool,
                'reason': str,
                'exit_price': float
            }
        """
        entry_price = position.get('entry_price')
        stop_loss = position.get('stop_loss')
        take_profit = position.get('take_profit')
        entry_time = position.get('entry_time')

        # Stop loss hit
        if current_price <= stop_loss:
            return {
                "should_exit": True,
                "reason": "stop_loss_hit",
                "exit_price": current_price,
                "pnl_pct": ((current_price - entry_price) / entry_price * 100)
            }

        # Take profit hit
        if current_price >= take_profit:
            return {
                "should_exit": True,
                "reason": "take_profit_hit",
                "exit_price": current_price,
                "pnl_pct": ((current_price - entry_price) / entry_price * 100)
            }

        return {"should_exit": False}

    def calculate_pnl(self, entry_price: float, current_price: float, quantity: int) -> dict:
        """Calculate P&L for a position"""
        pnl = (current_price - entry_price) * quantity
        pnl_pct = ((current_price - entry_price) / entry_price * 100)

        return {
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "pnl_status": "winning" if pnl > 0 else "losing"
        }

    def is_position_healthy(self, position: dict, current_price: float) -> bool:
        """Check if position is still healthy"""
        stop_loss = position.get('stop_loss')
        max_loss_pct = position.get('max_loss_pct', 0.05)  # 5%

        # Check stop loss
        if current_price <= stop_loss:
            return False

        # Check max drawdown
        entry_price = position.get('entry_price')
        loss_pct = (entry_price - current_price) / entry_price
        if loss_pct > max_loss_pct:
            return False

        return True
