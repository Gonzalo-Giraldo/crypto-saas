"""
TradingRuntime: capa de orquestación runtime para trading manual.
No acopla engines ni adapters, solo encapsula el flujo.
"""

class TradingRuntime:
    def __init__(self, market_data_engine, risk_engine, adapter):
        self.market_data_engine = market_data_engine
        self.risk_engine = risk_engine
        self.adapter = adapter

    def process_intent(self, user_id, broker, symbol, intent):
        # 1. Actualizar precio
        price_result = self.market_data_engine.update_binance_price(user_id, symbol, self.adapter)
        price_updated = price_result is not None

        # 2. Evaluar riesgo
        risk_result = self.risk_engine.evaluate_intent(intent)
        allowed = getattr(risk_result, "approved", False)
        reason = getattr(risk_result, "reason", None)

        return {
            "price_updated": price_updated,
            "risk": {
                "allowed": allowed,
                "reason": reason,
            }
        }

# Ejemplo de uso:
# from apps.worker.app.engine.market_data_engine import MarketDataEngine
# from apps.worker.app.engine.risk_engine import RiskEngine
# from apps.worker.app.engine.binance_market_data_adapter import BinanceMarketDataAdapter
# market_data_engine = MarketDataEngine()
# risk_engine = RiskEngine(market_data_engine=market_data_engine)
# adapter = BinanceMarketDataAdapter()
# runtime = TradingRuntime(market_data_engine, risk_engine, adapter)
# result = runtime.process_intent(user_id, broker, symbol, intent)
# print(result)
