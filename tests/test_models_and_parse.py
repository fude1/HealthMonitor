from datetime import datetime, timezone

from healthmonitor.clients.huawei_health_kit import HuaweiHealthKitClient
from healthmonitor.config import HuaweiConfig
from healthmonitor.engine import demo_snapshot
from healthmonitor.models import DeviceSnapshot


def test_demo_snapshot_shape():
    snap = demo_snapshot("Huawei Watch GT 3 Pro")
    assert isinstance(snap, DeviceSnapshot)
    assert snap.source == "demo"
    assert snap.error == "huawei_not_configured"
    names = {m.name for m in snap.metrics}
    assert "heart_rate" in names
    assert "spo2" in names


def test_flatten_polymerize_heart_rate():
    cfg = HuaweiConfig(
        client_id="x",
        client_secret="y",
        refresh_token="z",
        api_base="https://example.invalid",
        oauth_token_url="https://example.invalid/token",
        device_label="GT3",
    )
    client = HuaweiHealthKitClient(cfg)
    payload = {
        "group": [
            {
                "sampleSet": [
                    {
                        "dataTypeName": "com.huawei.instantaneous.heart_rate",
                        "samplePoints": [
                            {
                                "endTime": 1_730_000_000_000,
                                "value": [{"floatValue": 72.0}],
                            }
                        ],
                    }
                ]
            }
        ]
    }
    metrics = client._flatten_polymerize(payload)
    assert len(metrics) == 1
    assert metrics[0].name == "heart_rate"
    assert metrics[0].value == 72.0
    assert metrics[0].unit == "bpm"
    assert isinstance(metrics[0].recorded_at, datetime)
    assert metrics[0].recorded_at.tzinfo == timezone.utc
