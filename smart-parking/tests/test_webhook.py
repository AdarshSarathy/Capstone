import pytest
from fastapi.testclient import TestClient
import hmac
import hashlib
import json

from apps.api.main import app
from apps.api.routers.billing import RAZORPAY_WEBHOOK_SECRET

client = TestClient(app)

def test_webhook_security_valid_signature():
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test123",
                    "order_id": "order_test123"
                }
            }
        }
    }
    body = json.dumps(payload).encode()
    
    signature = hmac.new(
        key=RAZORPAY_WEBHOOK_SECRET.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"x-razorpay-signature": signature}
    )
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_webhook_security_invalid_signature():
    payload = {"event": "payment.captured"}
    body = json.dumps(payload).encode()
    
    # Send with wrong signature
    response = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"x-razorpay-signature": "invalid_signature_hash"}
    )
    
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid signature"}

def test_webhook_security_missing_signature():
    payload = {"event": "payment.captured"}
    body = json.dumps(payload).encode()
    
    # Send without signature header
    response = client.post(
        "/api/v1/payments/webhook",
        content=body
    )
    
    assert response.status_code == 422 # FastAPI validation error for missing header
