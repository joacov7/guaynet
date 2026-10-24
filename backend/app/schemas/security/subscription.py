from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.security.subscription import SecuritySubscriptionStatus, SecurityFeatureName


class SecurityPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    price: float
    default_features: Optional[list] = None
    is_active: bool
    includes_monitoring: bool = False


class SecurityFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feature_name: SecurityFeatureName
    enabled: bool


class SecurityFeatureToggle(BaseModel):
    feature_name: SecurityFeatureName
    enabled: bool


class SecuritySubscriptionCreate(BaseModel):
    property_id: int
    plan_id: int
    beat_account_id: Optional[str] = None
    contract_start: Optional[date] = None
    billing_day: int = 1
    notes: Optional[str] = None


class SecuritySubscriptionUpdate(BaseModel):
    status: Optional[SecuritySubscriptionStatus] = None
    beat_account_id: Optional[str] = None
    client_telegram_id: Optional[str] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    billing_day: Optional[int] = None
    notes: Optional[str] = None


class SecuritySubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    plan_id: int
    status: SecuritySubscriptionStatus
    beat_account_id: Optional[str] = None
    client_telegram_id: Optional[str] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    billing_day: int
    notes: Optional[str] = None
    features: List[SecurityFeatureResponse] = []
