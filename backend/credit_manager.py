"""
Credit Manager - Integrated with OBus Backend
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional

class ProviderQuota:
    """Credit/token info for a provider"""
    def __init__(self, key_id: str, provider: str, model: str, 
                 is_local: bool = False, total_credits: Optional[int] = None,
                 can_aggregate: bool = False):
        self.key_id = key_id
        self.provider = provider
        self.model = model
        self.is_local = is_local
        self.total_credits = total_credits
        self.remaining_credits = total_credits
        self.status = "active" if is_local else "unverified"
        self.cooldown_until = None
        self.reset_seconds = None
        self.last_refresh = datetime.now(timezone.utc).isoformat()
        self.next_refresh = self._calc_next_refresh(is_local, total_credits is None)
        self.can_aggregate = can_aggregate
        self.last_error = ""
        self.max_context_tokens = 8192
    
    def _calc_next_refresh(self, is_local: bool, is_unlimited: bool) -> str:
        now = datetime.now(timezone.utc)
        if is_local or is_unlimited:
            return (now + timedelta(days=365)).isoformat()
        return (now + timedelta(hours=1)).isoformat()
    
    def to_dict(self) -> Dict:
        return {
            'key_id': self.key_id, 'provider': self.provider, 'model': self.model,
            'is_local': self.is_local, 'total_credits': self.total_credits,
            'remaining_credits': self.remaining_credits, 'status': self.status,
            'cooldown_until': self.cooldown_until, 'reset_seconds': self.reset_seconds,
            'last_refresh': self.last_refresh, 'next_refresh': self.next_refresh,
            'can_aggregate': self.can_aggregate, 'last_error': self.last_error,
            'max_context_tokens': self.max_context_tokens
        }


class AgentWindow:
    """Credit window for an agent/card"""
    def __init__(self, card_id: str, key_id: str, context_max: int = 8192):
        self.card_id = card_id
        self.key_id = key_id
        self.credits_used = 0
        self.credits_allocated = 100
        self.status = "active"
        self.message = "Ready"
        self.refresh_seconds = None
        self.context_used = 0
        self.context_max = context_max
    
    def to_dict(self) -> Dict:
        return {
            'card_id': self.card_id, 'key_id': self.key_id,
            'credits_used': self.credits_used, 'credits_allocated': self.credits_allocated,
            'status': self.status, 'message': self.message,
            'refresh_seconds': self.refresh_seconds,
            'context_used': self.context_used, 'context_max': self.context_max
        }


class CreditManager:
    """Manages credit/token tracking for providers and agents"""
    
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.quotas: Dict[str, ProviderQuota] = {}
        self.windows: Dict[str, AgentWindow] = {}
        self._load_state()
    
    def _load_state(self):
        try:
            f = self.state_dir / 'credit_state.json'
            if f.exists():
                with open(f) as fp:
                    data = json.load(fp)
                    for k, v in data.get('quotas', {}).items():
                        p = ProviderQuota(v['key_id'], v['provider'], v['model'])
                        for field in ['is_local', 'total_credits', 'remaining_credits', 'status',
                                     'cooldown_until', 'reset_seconds', 'last_refresh', 'next_refresh',
                                     'can_aggregate', 'last_error', 'max_context_tokens']:
                            if field in v:
                                setattr(p, field, v[field])
                        self.quotas[k] = p
        except:
            pass
    
    def _save_state(self):
        data = {
            'quotas': {k: v.to_dict() for k, v in self.quotas.items()},
            'windows': {k: v.to_dict() for k, v in self.windows.items()}
        }
        with open(self.state_dir / 'credit_state.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def register_provider(self, key_id: str, provider: str, model: str,
                         is_local: bool = False, total_credits: Optional[int] = None,
                         can_aggregate: bool = False) -> ProviderQuota:
        quota = ProviderQuota(key_id, provider, model, is_local, total_credits, can_aggregate)
        self.quotas[key_id] = quota
        self._save_state()
        return quota
    
    def get_quota(self, key_id: str) -> Optional[ProviderQuota]:
        return self.quotas.get(key_id)
    
    def get_window(self, card_id: str, key_id: str) -> AgentWindow:
        wk = f"{card_id}:{key_id}"
        if wk not in self.windows:
            max_ctx = 8192
            if key_id in self.quotas:
                max_ctx = self.quotas[key_id].max_context_tokens or 8192
            if not max_ctx:
                max_ctx = 8192
            self.windows[wk] = AgentWindow(card_id, key_id, max_ctx)
        return self.windows[wk]
    
    def get_agent_status(self, card_id: str, key_id: str) -> Dict:
        quota = self.quotas.get(key_id)
        window = self.get_window(card_id, key_id)
        
        # Check refresh
        if quota and not quota.is_local and quota.next_refresh:
            try:
                nd = datetime.fromisoformat(quota.next_refresh.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) >= nd:
                    if quota.total_credits:
                        quota.remaining_credits = quota.total_credits
                        quota.status = "available"
            except:
                pass
        
        # Calculate refresh seconds
        refresh_sec = None
        if window.refresh_seconds:
            refresh_sec = window.refresh_seconds
        elif quota and quota.next_refresh:
            try:
                nd = datetime.fromisoformat(quota.next_refresh.replace('Z', '+00:00'))
                refresh_sec = max(0, int((nd - datetime.now(timezone.utc)).total_seconds()))
            except:
                pass
        
        # Context remaining
        ctx_rem = max(0, window.context_max - window.context_used)
        
        return {
            'card_id': card_id, 'key_id': key_id,
            'agent_status': window.status, 'agent_message': window.message,
            'agent_credits_used': window.credits_used,
            'agent_credits_allocated': window.credits_allocated,
            'agent_credits_remaining': max(0, window.credits_allocated - window.credits_used),
            'agent_context_used': window.context_used,
            'agent_context_max': window.context_max,
            'agent_context_remaining': ctx_rem,
            'provider_status': quota.status if quota else 'unknown',
            'provider_credits_remaining': quota.remaining_credits if quota else None,
            'provider_refresh_seconds': refresh_sec,
            'can_execute': self._can_execute(card_id, key_id)
        }
    
    def _can_execute(self, card_id: str, key_id: str) -> bool:
        quota = self.quotas.get(key_id)
        window = self.get_window(card_id, key_id)
        
        if quota:
            if quota.status in ["out_of_credits", "rate_limited", "error"]:
                if quota.cooldown_until:
                    try:
                        cd = datetime.fromisoformat(quota.cooldown_until.replace('Z', '+00:00'))
                        if datetime.now(timezone.utc) >= cd:
                            quota.status = "available"
                        else:
                            return False
                    except:
                        return False
                else:
                    return False
        
        if window.status == "out_of_credits":
            return False
        
        return True
    
    def consume_tokens(self, card_id: str, key_id: str, tokens: int = 1, ctx: int = 0) -> Dict:
        quota = self.quotas.get(key_id)
        window = self.get_window(card_id, key_id)
        
        if quota and quota.remaining_credits is not None:
            if quota.remaining_credits < tokens:
                return {'success': False, 'reason': 'depleted', 'status': self.get_agent_status(card_id, key_id)}
            quota.remaining_credits -= tokens
        
        window.credits_used += tokens
        window.context_used += ctx
        
        if window.credits_used >= window.credits_allocated:
            window.status = "out_of_credits"
            window.message = "Credits depleted"
        elif quota and quota.total_credits and quota.total_credits > 0:
            ratio = quota.remaining_credits / quota.total_credits
            window.status = "low" if ratio < 0.1 else "active"
            window.message = f"{quota.remaining_credits} remaining"
        else:
            window.status = "active"
            window.message = "Ready"
        
        self._save_state()
        return {'success': True, 'status': self.get_agent_status(card_id, key_id)}