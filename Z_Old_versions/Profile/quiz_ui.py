# handles the user-facing quiz, saves profile

import sys
from user_profile import UserProfile

def ask_question(prompt, options=None):
    print(prompt)
    if options:
        for idx, option in enumerate(options, 1):
            print(f"  {idx}. {option}")
        while True:
            try:
                choice = int(input("> "))
                if 1 <= choice <= len(options):
                    return options[choice - 1]
            except ValueError:
                pass
            print("Invalid input. Please enter a number.")
    else:
        return input("> ")


def main():
    profile = UserProfile()
    data = {}
    print("\n=== ThinkFree Profile Setup ===\n")
    try:
        data['age'] = int(ask_question("What's your age?"))
    except ValueError:
        print("Invalid input for age. Exiting.")
        sys.exit(1)
    data['experience'] = ask_question("How would you rate your investment experience?", [
        "None", "Some", "Experienced"
    ])
    data['goal'] = ask_question("What's your primary investment goal?", [
        "Quick Returns", "Long-Term Growth", "Income"
    ])
    data['reaction'] = ask_question("How would you react if the market dropped 20% in one day?", [
        "Buy more", "Hold", "Sell"
    ])
    data['timeline'] = ask_question("What is your investment timeline?", [
        "<1 year", "1-3 years", "3+ years"
    ])
    # First update the profile with user input data
    profile.update_profile(data)

    # Then get investment preferences
    preferences = profile.get_investment_preferences()
    
    # Update the profile with calculated preferences
    profile.update_profile(preferences)
    
    print("\nProfile saved successfully!\n")
    print("Suggested Preferences:")
    for k, v in preferences.items():
        print(f"- {k}: {v}")

if __name__ == "__main__":
    main()
