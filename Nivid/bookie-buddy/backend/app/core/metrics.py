from prometheus_client import Counter, Histogram

recommendation_counter = Counter(
    "valuebet_recommendations_total",
    "Total recommendations generated",
    labelnames=("label", "risk_tier"),
)

order_counter = Counter(
    "valuebet_orders_total",
    "Total simulated/live orders submitted",
    labelnames=("mode", "status"),
)

poll_latency = Histogram(
    "valuebet_poll_seconds",
    "Polling latency in seconds",
)
