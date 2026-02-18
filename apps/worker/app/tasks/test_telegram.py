from apps.worker.app.engine.notifier import notify

def test_telegram():
    notify("✅ <b>Telegram conectado</b>\nMicro-Live Monitor listo.")

