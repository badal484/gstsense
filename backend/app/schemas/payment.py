import uuid
from decimal import Decimal

from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    scan_id: uuid.UUID


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    amount_rupees: Decimal
    currency: str = "INR"
    key_id: str
    scan_id: uuid.UUID


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    scan_id: uuid.UUID


class VerifyPaymentResponse(BaseModel):
    success: bool
    scan_id: uuid.UUID
    message: str


class WebhookPayload(BaseModel):
    event: str
    payload: dict
