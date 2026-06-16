# phase1_user_personalization.py

import json
import datetime

def classify_user_profile(profile):
    age = profile["age"]
    risk = profile["risk_tolerance"]

    # Define age groups
    if age < 25:
        age_group = "A1_<25"
    elif 25 <= age <= 34:
        age_group = "A2_25-34"
    elif 35 <= age <= 50:
        age_group = "A3_35-50"
    else:
        age_group = "A4_50+"

    # Define risk groups
    if risk == "low":
        risk_group = "R1_Cons"
    elif risk == "moderate":
        risk_group = "R2_Mod"
    else:
        risk_group = "R3_High"

    return f"{age_group}_{risk_group}"

def run_user_quiz():
    print("Welcome to ThinkFree! Please answer a few questions to personalize your experience.\n")

    profile = {}

    # Basic Info
    profile['created_at'] = datetime.datetime.utcnow().isoformat()
    profile['age'] = int(input("What is your age? "))
    profile['experience_level'] = input("How would you describe your investing experience? (beginner/intermediate/advanced): ").strip().lower()
    profile['investment_goal'] = input("What is your primary investment goal? (growth/income/stability): ").strip().lower()
    profile['timeline'] = input("What is your investment timeline? (short-term/mid-term/long-term): ").strip().lower()
    profile['emotional_response'] = input("When markets drop, how do you usually react? (sell/hold/buy more): ").strip().lower()

    # Risk scoring logic (simple baseline)
    risk_points = 0

    if profile['age'] < 30:
        risk_points += 2
    elif profile['age'] < 50:
        risk_points += 1

    if profile['experience_level'] == 'advanced':
        risk_points += 2
    elif profile['experience_level'] == 'intermediate':
        risk_points += 1

    if profile['investment_goal'] == 'growth':
        risk_points += 2
    elif profile['investment_goal'] == 'income':
        risk_points += 1

    if profile['emotional_response'] == 'buy more':
        risk_points += 2
    elif profile['emotional_response'] == 'hold':
        risk_points += 1

    # Assigning risk tolerance based on score
    if risk_points >= 7:
        profile['risk_tolerance'] = 'high'
    elif risk_points >= 4:
        profile['risk_tolerance'] = 'moderate'
    else:
        profile['risk_tolerance'] = 'low'

    profile['risk_score'] = risk_points
    profile['profile_id'] = classify_user_profile(profile)

    # Save profile
    with open('user_profile.json', 'w') as f:
        json.dump(profile, f, indent=4)

    print("\nThank you! Your profile has been saved.")

if __name__ == "__main__":
    run_user_quiz()
