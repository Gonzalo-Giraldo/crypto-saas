import asyncio
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

BINANCE_USER_DATA_STREAM_URL = "wss://stream.binance.com:9443/ws/{listen_key}"


class BinanceUserDataStreamListenerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedExecutionReport:
    order_id: str
    trade_id: Optional[str]
    price: Decimal
    qty: Decimal
    commission: Decimal
    commission_asset: Optional[str]
    executed_at: Optional[int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "trade_id": self.trade_id,
            "price": self.price,
            "qty": self.qty,
            "commission": self.commission,
            "commission_asset": self.commission_asset,
            "executed_at": self.executed_at,
        }


async def get_listen_key_placeholder() -> str:
    """
    Placeholder seguro.

    No llama Binance directamente.
    Este módulo queda aislado hasta que exista un cliente aprobado para crear
    listenKey de forma controlada.
    """
    return "PLACEHOLDER_LISTEN_KEY_DO_NOT_USE_FOR_PRODUCTION"


def build_user_data_stream_url(listen_key: str) -> str:
    if not listen_key or not listen_key.strip():
        raise BinanceUserDataStreamListenerError("listenKey vacío o inválido")

    return BINANCE_USER_DATA_STREAM_URL.format(listen_key=listen_key.strip())


def parse_execution_report(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Mapea Binance executionReport a estructura interna.

    Campos Binance usados:
    - e: event type
    - i: orderId
    - t: tradeId
    - L: last executed price
    - l: last executed quantity
    - n: commission amount
    - N: commission asset
    - T: transaction time
    """
    if message.get("e") != "executionReport":
        return None

    order_id = message.get("i")
    if order_id is None:
        raise BinanceUserDataStreamListenerError(
            "executionReport inválido: falta order_id campo 'i'"
        )

    parsed = ParsedExecutionReport(
        order_id=str(order_id),
        trade_id=None if message.get("t") is None else str(message.get("t")),
        price=Decimal(str(message.get("L") or "0")),
        qty=Decimal(str(message.get("l") or "0")),
        commission=Decimal(str(message.get("n") or "0")),
        commission_asset=message.get("N"),
        executed_at=message.get("T"),
    )

    return parsed.as_dict()


async def connect(
    listen_key: str,
    websocket_connect: Optional[Callable[[str], Awaitable[Any]]] = None,
) -> Any:
    """
    Abre conexión WebSocket.

    websocket_connect se inyecta para test/mocks.
    Si no se inyecta, intenta usar websockets.connect, pero no se ejecuta
    automáticamente en import ni desde app principal.
    """
    url = build_user_data_stream_url(listen_key)

    if websocket_connect is None:
        try:
            import websockets
        except ImportError as exc:
            raise BinanceUserDataStreamListenerError(
                "Dependencia websockets no disponible; inyecte websocket_connect "
                "en tests o agregue dependencia explícitamente antes de uso real"
            ) from exc

        websocket_connect = websockets.connect

    logger.info("Connecting Binance userData stream listener")
    return await websocket_connect(url)


async def listen(
    websocket: Any,
    *,
    on_execution_report: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    message_timeout_seconds: float = 30.0,
) -> None:
    """
    Escucha mensajes y procesa únicamente executionReport.

    No persiste en DB.
    No llama execution.
    No modifica estado financiero.
    """
    while True:
        try:
            raw_message = await asyncio.wait_for(
                websocket.recv(),
                timeout=message_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Binance userData stream listener timeout waiting for message"
            )
            continue

        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("Ignoring non-JSON Binance userData stream message")
            continue

        parsed = parse_execution_report(message)
        if parsed is None:
            logger.debug(
                "Ignoring Binance userData stream event type=%s",
                message.get("e"),
            )
            continue

        logger.info(
            "Received Binance executionReport order_id=%s trade_id=%s qty=%s price=%s",
            parsed["order_id"],
            parsed["trade_id"],
            parsed["qty"],
            parsed["price"],
        )

        if on_execution_report is not None:
            await on_execution_report(parsed)


async def start_user_data_stream_listener(
    *,
    listen_key: Optional[str] = None,
    listen_key_provider: Optional[Callable[[], Awaitable[str]]] = None,
    websocket_connect: Optional[Callable[[str], Awaitable[Any]]] = None,
    on_execution_report: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    reconnect_delay_seconds: float = 5.0,
    message_timeout_seconds: float = 30.0,
    max_reconnect_attempts: Optional[int] = 3,
) -> None:
    """
    Inicia listener aislado Binance userData stream.

    Seguro por diseño:
    - No obtiene listenKey real salvo que se inyecte provider externo aprobado.
    - No persiste DB.
    - No llama execution.
    - No crea threads globales.
    - No se ejecuta en import.
    """
    if listen_key is None:
        provider = listen_key_provider or get_listen_key_placeholder
        listen_key = await provider()

    attempts = 0

    while True:
        if max_reconnect_attempts is not None and attempts >= max_reconnect_attempts:
            raise BinanceUserDataStreamListenerError(
                "Max reconnect attempts reached for Binance userData stream listener"
            )

        attempts += 1

        try:
            websocket = await connect(
                listen_key,
                websocket_connect=websocket_connect,
            )
            logger.info(
                "Binance userData stream listener connected attempt=%s",
                attempts,
            )
            await listen(
                websocket,
                on_execution_report=on_execution_report,
                message_timeout_seconds=message_timeout_seconds,
            )
        except asyncio.CancelledError:
            logger.info("Binance userData stream listener cancelled")
            raise
        except Exception:
            logger.exception(
                "Binance userData stream listener failed attempt=%s; retrying",
                attempts,
            )
            await asyncio.sleep(reconnect_delay_seconds)
