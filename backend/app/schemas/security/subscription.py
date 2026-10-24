from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.security.subscription import SecuritySubscriptionStatus, SecurityFeatureName


class SecurityPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    monthly_price: float
    default_features: List[str]
    is_active: bool


class SecurityFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feature_name: SecurityFeatureName
    is_enabled: bool


class SecurityFeatureToggle(BaseModel):
    feature_name: SecurityFeatureName
    is_enabled: bool


class SecuritySubscriptionCreate(BaseModel):
    property_id: int
    plan_id: int
    beat_account_id: Optional[str] = None
    contract_number: Optional[str] = None


class SecuritySubscriptionUpdate(BaseModel):
    status: Optional[SecuritySubscriptionStatus] = None
    beat_account_id: Optional[str] = None
    contract_number: Optional[str] = None


class SecuritySubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    plan_id: int
    status: SecuritySubscriptionStatus
    beat_account_id: Optional[str] = None
    contract_number: Optional[str] = None
    activated_at: Optional[datetime] = None
    features: List[SecurityFeatureResponse] = []
