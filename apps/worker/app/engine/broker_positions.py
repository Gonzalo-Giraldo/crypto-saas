
from typing import List, Dict


def get_open_positions(user_id: str) -> List[Dict]:
    """
    Capa unificada para obtener posiciones abiertas desde brokers.

    NOTA:
    - Actualmente solo stub (no conecta aún a broker real)
    - Debe ser extendido por broker (Binance / IBKR)
    """

    positions = []

    # --- FUTURO: BINANCE ---
    # positions += get_binance_positions(user_id)

    # --- FUTURO: IBKR ---
    # positions += get_ibkr_positions(user_id)

    return positions
