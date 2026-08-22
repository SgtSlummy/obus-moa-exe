"""
OBus MOA - Credit and Token Management System

Tracks per-agent (card) credit/token usage, handles refresh timing,
and provides auto-cycling when providers run out of credits.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field


@dataclass
class QuotaInfo:
    """Credit/token information for a provider/key"""
    key_id: str
    provider: str
    model: str
    
    # Credit limits (None = unlimited/local)
    total_credits: Optional[int] = None
    remaining_credits: Optional[int] = None
    
    # Rate limiting
    requests_per_minute: Optional[int] = None
    tokens_per_minute: Optional[int] = None
    
    # Refresh timing
    refresh_type: str = "manual"  # manual, hourly, daily, monthly, local
    last_refresh: Optional[str] = None
    next_refresh: Optional[str] = None
    
    # Current status
    status: str = "unknown"  # available, running, low, rate_limited, out_of_credits, cooldown, offline, unverified
    
    # Usage tracking
    last_error: Optional[str] = None
    requests_this_minute: int = 0
    tokens_this_minute: int = 0
    minute_window_start: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {}
        for key, value in asdict(self).items():
            if key != 'to_dict':
                result[key] = value
        return result


@dataclass
class AgentCreditWindow:
    """Credit window for a specific agent/card"""
    card_id: str
    key_id: str
    
    # Current usage
    credits_used: int = 0
    credits_allocated: int = 100  # Default allocation per window
    
    # Refresh cycle  
    refresh_cycle_seconds: int = 3600  # 1 hour default
    last_refresh: Optional[str] = None
    next_refresh: Optional[str] = None
    
    # Status
    status: str = "active"  # active, low_credits, out_of_credits, cooldown
    window_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for key, value in asdict(self).items():
            if key != 'to_dict':
                result[key] = value
        return result


class CreditManager:
    """Manages credit/token tracking for all providers and agents"""
    
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.credits_file = state_dir / 'credit_tracker.json'
        self.windows_file = state_dir / 'agent_windows.json'
        
        # Ensure directory exists
        state_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize credit data
        self.provider_credits: Dict[str, QuotaInfo] = {}
        self.agent_windows: Dict[str, AgentCreditWindow] = {}
        
        self._load_credits()
        self._load_windows()
    
    def _load_credits(self):
        """Load provider credit info from disk"""
        if self.credits_file.exists():
            try:
                with open(self.credits_file) as f:
                    data = json.load(f)
                    for key_id, info in data.items():
                        self.provider_credits[key_id] = QuotaInfo(**info)
            except Exception:
                pass
    
    def _load_windows(self):
        """Load agent credit windows from disk"""
        if self.windows_file.exists():
            try:
                with open(self.windows_file) as f:
                    data = json.load(f)
                    for card_key, info in data.items():
                        self.agent_windows[card_key] = AgentCreditWindow(**info)
            except Exception:
                pass
    
    def _save_credits(self):
        """Save provider credit info to disk"""
        data = {k: v.to_dict() for k, v in self.provider_credits.items()}
        with open(self.credits_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_windows(self):
        """Save agent credit windows to disk"""
        data = {k: v.to_dict() for k, v in self.agent_windows.items()}
        with open(self.windows_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _now_iso(self) -> str:
        """Get current ISO timestamp with timezone"""
        return datetime.now(timezone.utc).isoformat()
    
    def _calculate_next_refresh(self, refresh_type: str) -> str:
        """Calculate next refresh time based on refresh type"""
        now = datetime.now(timezone.utc)
        
        if refresh_type == "hourly":
            next_time = now + timedelta(hours=1)
        elif refresh_type == "daily":
            next_time = now + timedelta(days=1)
        elif refresh_type == "monthly":
            next_time = now + timedelta(days=30)
        else:  # manual or local
            next_time = now + timedelta(days=365)  # Far future for manual/local
        
        return next_time.isoformat()
    
    def register_provider(self, key_id: str, provider: str, model: str,
                         total_credits: Optional[int] = None,
                         refresh_type: str = "manual",
                         is_local: bool = False) -> QuotaInfo:
        """Register a new provider for credit tracking"""
        if is_local:
            refresh_type = "local"
        
        info = QuotaInfo(
            key_id=key_id,
            provider=provider,
            model=model,
            total_credits=total_credits,
            remaining_credits=total_credits,
            refresh_type=refresh_type,
            last_refresh=self._now_iso(),
            next_refresh=self._calculate_next_refresh(refresh_type),
            status="active" if total_credits is None else "unknown"  # Local or unknown
        )
        self.provider_credits[key_id] = info
        self._save_credits()
        return info
    
    def get_agent_window(self, card_id: str, key_id: str) -> AgentCreditWindow:
        """Get or create credit window for an agent"""
        window_key = f"{card_id}:{key_id}"
        
        if window_key not in self.agent_windows:
            window = AgentCreditWindow(
                card_id=card_id,
                key_id=key_id,
                last_refresh=self._now_iso(),
                next_refresh=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            )
            self.agent_windows[window_key] = window
        
        return self.agent_windows[window_key]
    
    def update_from_response(self, key_id: str, response_headers: dict = None, 
                            error: Optional[str] = None) -> Dict:
        """Update quota info from provider response or error"""
        provider = self.provider_credits.get(key_id)
        if not provider:
            return {"status": "provider_not_found"}
        
        if error:
            provider.last_error = error
            provider.status = "error"
            
            # Detect error type from message
            if "rate limit" in error.lower() or "429" in error:
                provider.status = "rate_limited"
                provider.cooldown_until = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
            elif "quota" in error.lower() or "credit" in error.lower() or "402" in error:
                provider.status = "out_of_credits"
                provider.cooldown_until = provider.next_refresh
            self._save_credits()
            return provider.to_dict()
        
        # Extract quota info from headers
        if response_headers:
            # OpenAI-style headers
            remaining = response_headers.get('x-ratelimit-remaining-requests') or response_headers.get('x-ratelimit-remaining')
            limit = response_headers.get('x-ratelimit-limit-requests') or response_headers.get('x-ratelimit-limit')
            
            if remaining is not None:
                try:
                    provider.remaining_credits = int(remaining)
                    if limit:
                        provider.total_credits = int(limit)
                    
                    # Update status based on remaining
                    if provider.total_credits:
                        ratio = provider.remaining_credits / provider.total_credits
                        if ratio < 0.1:
                            provider.status = "low"
                            provider.refresh_type = "unknown"
                        else:
                            provider.status = "available"
                    
                    reset = response_headers.get('x-ratelimit-reset-requests') or response_headers.get('x-ratelimit-reset')
                    if reset:
                        reset_seconds = int(float(reset))
                        provider.cooldown_until = (datetime.now(timezone.utc) + timedelta(seconds=reset_seconds)).isoformat()
                        provider.reset_seconds = reset_seconds
                except (ValueError, TypeError):
                    pass
        
        provider.last_error = None
        self._save_credits()
        return provider.to_dict()
    
    def get_status_message(self, card_id: str, key_id: str) -> Dict[str, Any]:
        """Get dynamic credit message for an agent/card"""
        provider = self.provider_credits.get(key_id)
        window = self.get_agent_window(card_id, key_id)
        
        # Check if provider needs refresh check
        self._maybe_refresh_provider(key_id)
        
        # Refresh window if needed
        self._maybe_refresh_window(window, provider)
        
        # Build comprehensive status
        status_data = {
            "card_id": card_id,
            "key_id": key_id,
            "agent_status": window.status,
            "agent_message": window.window_message,
            "agent_credits_used": window.credits_used,
            "agent_credits_allocated": window.credits_allocated,
            "agent_credits_remaining": max(0, window.credits_allocated - window.credits_used),
            "agent_refresh_seconds": self._get_refresh_seconds(window.next_refresh),
            "provider_status": provider.status if provider else "unknown",
            "provider_credits_remaining": provider.remaining_credits if provider else None,
            "provider_refresh_seconds": self._get_provider_refresh_seconds(provider) if provider else None,
            "can_execute": self._can_execute(card_id, key_id)
        }
        
        return status_data
    
    def _maybe_refresh_provider(self, key_id: str):
        """Check and refresh provider if at reset time"""
        provider = self.provider_credits.get(key_id)
        if not provider or provider.refresh_type == "local":
            return
        
        if provider.next_refresh:
            try:
                next_dt = datetime.fromisoformat(provider.next_refresh.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) >= next_dt:
                    provider.status = "refreshing"
                    provider.last_refresh = self._now_iso()
                    provider.next_refresh = self._calculate_next_refresh(provider.refresh_type)
                    if provider.total_credits:
                        provider.remaining_credits = provider.total_credits
                    provider.status = "available"
                    provider.last_error = None
                    self._save_credits()
            except Exception:
                pass
    
    def _maybe_refresh_window(self, window: AgentCreditWindow, provider: Optional[QuotaInfo]):
        """Check and refresh agent window if needed"""
        if not window.next_refresh:
            return
        
        try:
            next_dt = datetime.fromisoformat(window.next_refresh.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) >= next_dt:
                window.credits_used = 0
                window.status = "active"
                window.last_refresh = self._now_iso()
                window.next_refresh = (datetime.now(timezone.utc) + timedelta(seconds=window.refresh_cycle_seconds)).isoformat()
                window.window_message = "Credits refreshed"
        except Exception:
            pass
    
    def _can_execute(self, card_id: str, key_id: str) -> bool:
        """Check if agent can execute with this provider"""
        provider = self.provider_credits.get(key_id)
        window = self.get_agent_window(card_id, key_id)
        
        # Check provider status
        if provider:
            if provider.status in ["out_of_credits", "rate_limited", "offline", "error"]:
                if not provider.cooldown_until:
                    return False
                try:
                    cooldown_dt = datetime.fromisoformat(provider.cooldown_until.replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) >= cooldown_dt:
                        provider.status = "available"
                    else:
                        return False
                except Exception:
                    return False
        
        # Check window status
        if window.status == "out_of_credits":
            return False
        
        return True
    
    def _get_refresh_seconds(self, next_refresh: Optional[str]) -> Optional[int]:
        """Get seconds until refresh"""
        if not next_refresh:
            return None
        try:
            next_dt = datetime.fromisoformat(next_refresh.replace('Z', '+00:00'))
            delta = (next_dt - datetime.now(timezone.utc)).total_seconds()
            return max(0, int(delta))
        except Exception:
            return None
    
    def _get_provider_refresh_seconds(self, provider: Optional[QuotaInfo]) -> Optional[int]:
        """Get seconds until provider refresh"""
        if not provider:
            return None
        return self._get_refresh_seconds(provider.next_refresh)
    
    def get_all_agent_statuses(self) -> List[Dict[str, Any]]:
        """Get status for all agents"""
        statuses = []
        for key_id, provider in self.provider_credits.items():
            # Get windows for this provider
            for window_key, window in self.agent_windows.items():
                if window.key_id == key_id:
                    statuses.append(self.get_status_message(window.card_id, key_id))
        return statuses
    
    def should_cycle_provider(self, card_id: str, key_id: str) -> tuple[bool, Optional[str]]:
        """Check if provider should be cycled for this agent"""
        window = self.get_agent_window(card_id, key_id)
        provider = self.provider_credits.get(key_id)
        
        if window.status == "out_of_credits":
            return True, "window_depleted"
        
        if provider:
            if provider.status == "out_of_credits":
                return True, "provider_depleted"
            if provider.status == "rate_limited":
                return True, "rate_limited"
            if provider.status == "error":
                return True, "provider_error"
            if provider.status == "refreshing":
                return True, "provider_refreshing"
        
        return False, None
    
    def get_alternative_provider(self, excluded_key_ids: List[str]) -> Optional[str]:
        """Get alternative provider when cycling is needed"""
        for key_id, provider in self.provider_credits.items():
            if key_id in excluded_key_ids:
                continue
            if provider.status in ["available", "active", "unknown"]:
                if not provider.cooldown_until:
                    return key_id
        
        return None
    
    def consume_agent_credits(self, card_id: str, key_id: str, credits: int = 1) -> Dict:
        """Consume credits for an agent"""
        provider = self.provider_credits.get(key_id)
        window = self.get_agent_window(card_id, key_id)
        
        # Check if provider has credits
        if provider and provider.remaining_credits is not None:
            if provider.remaining_credits < credits:
                return {
                    "success": False,
                    "reason": "provider_depleted",
                    "message": f"Provider {provider.provider} has no credits remaining",
                    "status": self.get_status_message(card_id, key_id)
                }
            provider.remaining_credits -= credits
        
        # Update window
        window.credits_used += credits
        
        # Update status based on usage
        if window.credits_used >= window.credits_allocated:
            window.status = "out_of_credits"
            window.window_message = "Credits depleted - refresh in progress"
        elif window.credits_used >= window.credits_allocated * 0.8:
            window.status = "low"
            window.window_message = "Low credits - consider switching provider"
        else:
            window.status = "active"
            window.window_message = f"{window.credits_allocated - window.credits_used} credits remaining"
        
        self._save_windows()
        if provider:
            self._save_credits()
        
        return {
            "success": True,
            "status": self.get_status_message(card_id, key_id)
        }