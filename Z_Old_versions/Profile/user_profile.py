# defines UserProfile class (logic + storage)
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
class UserProfile:
    def __init__(self, profile_path: str = "user_profile.json"):
        self.profile_path = profile_path
        self.profile_data = self._load_profile()
    def _load_profile(self) -> Dict[str, Any]:
        """Load existing profile or return empty dict."""
        if os.path.exists(self.profile_path):
            with open(self.profile_path, 'r') as f:
                return json.load(f)
        return {}
    def save_profile(self, data: Dict[str, Any]) -> None:
        """Save profile data to file."""
        with open(self.profile_path, 'w') as f:
            json.dump(data, f, indent=4)
        self.profile_data = data
    def update_profile(self, new_data: Dict[str, Any]) -> None:
        """Update existing profile with new data."""
        self.profile_data.update(new_data)
        self.save_profile(self.profile_data)
    def get_profile(self) -> Dict[str, Any]:
        """Return current profile data."""
        return self.profile_data
    def calculate_risk_score(self) -> int:
        """Calculate numerical risk score based on profile data."""
        score = 0
    
        # Age factor
        age = self.profile_data.get('age', 0)
        if age < 30:
            score += 3  # Young investors can take more risk
        elif age < 50:
            score += 2
        else:
            score += 1
        # Experience factor
        experience_map = {'none': 1, 'some': 2, 'experienced': 3}
        experience = self.profile_data.get('experience', 'none').lower()
        score += experience_map.get(experience, 1)
        # Goal factor
        goal_map = {'quick returns': 3, 'long-term growth': 2, 'income': 1}
        goal = self.profile_data.get('goal', 'income').lower()
        score += goal_map.get(goal, 1)
        # Market reaction factor
        reaction_map = {'buy more': 3, 'hold': 2, 'sell': 1}
        reaction = self.profile_data.get('reaction', 'hold').lower()
        score += reaction_map.get(reaction, 2)
        # Timeline factor
        timeline_map = {'<1 year': 1, '1-3 years': 2, '3+ years': 3}
        timeline = self.profile_data.get('timeline', '1-3 years').lower()
        score += timeline_map.get(timeline, 2)
        return score
    def get_investment_preferences(self) -> Dict[str, Any]:
        """Generate investment preferences based on profile."""
        risk_score = self.calculate_risk_score()
        
        preferences = {
            'risk_tolerance': 'low' if risk_score <= 8 else 'medium' if risk_score <= 12 else 'high',
            'suggested_assets': self._get_suggested_assets(risk_score),
            'investment_horizon': self.profile_data.get('timeline', 'medium-term'),
            'last_updated': datetime.now().isoformat()
        }
    
        return preferences
    def _get_suggested_assets(self, risk_score: int) -> Dict[str, float]:
        """Generate asset allocation based on risk score."""
        if risk_score <= 8:  # Conservative
            return {
                'bonds': 0.60,
                'large_cap_stocks': 0.25,
                'international_stocks': 0.10,
                'cash': 0.05
            }
        elif risk_score <= 12:  # Moderate
            return {
                'bonds': 0.40,
                'large_cap_stocks': 0.35,
                'international_stocks': 0.20,
                'small_cap_stocks': 0.05
            }
        else:  # Aggressive
            return {
                'bonds': 0.20,
                'large_cap_stocks': 0.40,
                'international_stocks': 0.25,
                'small_cap_stocks': 0.15
            }
    def validate_profile(self) -> bool:
        """Validate that all required profile fields are present."""
        required_fields = ['age', 'experience', 'goal', 'reaction', 'timeline']
        return all(field in self.profile_data for field in required_fields)