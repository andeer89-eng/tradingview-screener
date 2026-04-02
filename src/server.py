"""
Flask application factory for the TradingView Indicator Extension.
Serves the frontend, provides webhook and signal API endpoints.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

from .alerts.parser  import AlertParser
from .alerts.handler import AlertHandler
from .alerts.router  import AlertRouter
from .indicators     import CustomSignalEngine
from .utils          import DataFetcher


def create_app(
    fetcher: DataFetcher | None = None,
    router:  AlertRouter | None = None,
) -> Flask:
    root_dir = Path(__file__).resolve().parent.parent
    app = Flask(__name__, static_folder=None)

    _fetcher = fetcher or DataFetcher()
    _router  = router or AlertRouter()
    _parser  = AlertParser()
    _handler = AlertHandler(fetcher=_fetcher)
    _engine  = CustomSignalEngine()

    # -- Serve frontend --------------------------------------------------------
    @app.route("/")
    def index():
        return send_from_directory(str(root_dir), "index.html")

    # -- Health ----------------------------------------------------------------
    @app.route("/health")
    def health():
        return jsonify({
            "status": "ok",
            "service": "tradingview-screener",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    # -- Webhook (TradingView alerts) ------------------------------------------
    @app.route("/webhook", methods=["POST"])
    @app.route("/alert", methods=["POST"])
    def webhook():
        # Optional secret check
        from config import cfg
        if cfg.WEBHOOK_SECRET:
            secret = request.headers.get("X-Webhook-Secret", "")
            if secret != cfg.WEBHOOK_SECRET:
                return jsonify({"error": "unauthorized"}), 401

        t0 = time.time()
        alert = _parser.parse(request.data)
        result = _handler.handle(alert)

        if result is None:
            return jsonify({
                "status": "skipped",
                "reason": alert.error or "handler returned None",
            }), 400

        _router.dispatch(result)
        latency = (time.time() - t0) * 1000

        return jsonify({
            "status":  "processed",
            "ticker":  result.alert.ticker,
            "rating":  result.composite.rating,
            "score":   result.composite.score,
            "signals": {
                "rsi":  result.composite.rsi_signal,
                "macd": result.composite.macd_signal,
                "bb":   result.composite.bb_signal,
                "st":   result.composite.st_signal,
                "vwap": result.composite.vwap_signal,
            },
            "latency_ms": round(latency, 1),
        })

    # -- Signal query ----------------------------------------------------------
    @app.route("/signal/<ticker>")
    def signal(ticker: str):
        interval = request.args.get("interval", "1h")
        ticker   = ticker.upper()

        try:
            ohlcv = _fetcher.get(ticker, interval)
        except Exception as exc:
            return jsonify({"error": f"Data fetch failed: {exc}"}), 500

        try:
            result = _engine.run(
                high   = ohlcv["high"],
                low    = ohlcv["low"],
                close  = ohlcv["close"],
                volume = ohlcv.get("volume"),
            )
        except Exception as exc:
            return jsonify({"error": f"Indicator calculation failed: {exc}"}), 500

        return jsonify({
            "ticker":   ticker,
            "interval": interval,
            "rating":   result.rating,
            "score":    result.score,
            "signals": {
                "rsi":  result.rsi_signal,
                "macd": result.macd_signal,
                "bb":   result.bb_signal,
                "st":   result.st_signal,
                "vwap": result.vwap_signal,
            },
            "components": result.components,
        })

    return app
