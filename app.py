from flask import Flask, render_template, request, redirect, url_for, session, flash

import json
import os
from random import shuffle
from dotenv import load_dotenv
import os


# Path to the JSON file
DATA_FILE = "members.json"

# Load members from the JSON file
def load_members():
    if os.path.exists(DATA_FILE):
        if os.path.getsize(DATA_FILE) > 0:  # Check if the file is not empty
            with open(DATA_FILE, "r") as file:
                return json.load(file)
    return []  # Return an empty list if the file doesn't exist or is empty


# Save members to the JSON file
def save_members():
    with open(DATA_FILE, "w") as file:
        json.dump(members, file)


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_key")  # Use env variable or fallback
app.config['APPLICATION_ROOT'] = '/flask'


# Secure session cookies
# app.config["SESSION_COOKIE_HTTPONLY"] = True  # Prevent JavaScript access to cookies
# app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # Mitigate CSRF risks

# Load variables from .env
load_dotenv()

# Login credentials
USERNAME = os.getenv("APP_USERNAME")
PASSWORD = os.getenv("APP_PASSWORD")

print(f"USERNAME: {USERNAME}, PASSWORD: {PASSWORD}")

# In-memory database for members (loaded from file)
members = load_members()

# @app.route("/", methods=["GET", "POST"])
@app.route('/flask/', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == USERNAME and password == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.")
    return render_template("login.html")

# @app.route("/dashboard")
@app.route('/flask/dashboard')
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("dashboard.html",members =members)

@app.route("/flask/add_member", methods=["GET", "POST"])
def add_member():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if request.method == "POST":
        first_name = request.form["first_name"].strip()
        last_name = request.form["last_name"].strip()
        gender = request.form["gender"]
        star_rating = request.form["star_rating"]
        
        # Check for duplicate members
        for member in members:
            if (member["first_name"] == first_name and 
                member["last_name"] == last_name and 
                member["gender"] == gender):
                flash("Member already exists!")
                return redirect(url_for("dashboard"))
        
        # Add the new member if not a duplicate
        members.append({
            "first_name": first_name,
            "last_name": last_name,
            "gender": gender,
            "star_rating": star_rating
        })
        save_members()  # Save to JSON file
        flash("Member added successfully!")
        return redirect(url_for("dashboard"))
    return render_template("add_member.html")

@app.route("/flask/edit_members")
def edit_members():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("edit_members.html", members=members)

@app.route("/flask/edit_member/<int:member_id>", methods=["GET", "POST"])
def edit_member(member_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    # Retrieve the member to edit
    member = members[member_id]

    if request.method == "POST":
        # Update member details
        member["first_name"] = request.form["first_name"].strip()
        member["last_name"] = request.form["last_name"].strip()
        member["gender"] = request.form["gender"]
        member["star_rating"] = request.form["star_rating"]
        save_members()  # Save the updated members list to the JSON file
        flash("Member details updated successfully!")
        return redirect(url_for("edit_members"))

    return render_template("edit_member.html", member=member)


@app.route("/flask/generate_matches", methods=["POST"])
def generate_matches():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    # Get selected members
    selected_members = session.get("selected_members", [])

    if request.method == "POST":
        # Check if new members were selected
        selected_indexes = request.form.getlist("selected_members")
        if selected_indexes:
            selected_indexes = [int(index) for index in selected_indexes]  # Convert to integers
            selected_members = [members[idx] for idx in selected_indexes]
            session["selected_members"] = selected_members  # Save the new selection to session

    # If no selected members exist, redirect back to dashboard
    if not selected_members:
        flash("No members selected for reshuffling!")
        return redirect(url_for("dashboard"))

    # Retrieve previous matches from session
    previous_matches = session.get("previous_matches", [])

    # Determine match generation type from form data
    generate_type = request.form.get("type", "random")

    if generate_type == "balanced":
        doubles_matches, singles_match, waiting_member, updated_matches = generate_balanced_matches(
            selected_members, previous_matches
        )
        session["previous_matches"] = updated_matches  # Store updated match history
    elif generate_type == "fair_balanced":
        doubles_matches, singles_match, waiting_member, updated_matches = generate_fair_balanced_matches(
            selected_members, previous_matches
        )
        session["previous_matches"] = updated_matches  # Store updated match history
    else:
        doubles_matches, singles_match, waiting_member = generate_random_matches(selected_members)

    return render_template(
        "matches.html",
        doubles_matches=doubles_matches,
        singles_match=singles_match,
        waiting_member=waiting_member
    )

def generate_random_matches(selected_members):
    """Generates multiple random matches."""
    shuffle(selected_members)  # Shuffle members for randomness

    doubles_matches = []
    singles_match = None
    waiting_member = []

    # Create doubles matches in groups of 4
    while len(selected_members) >= 4:
        doubles_matches.append(selected_members[:4])  # Take the first 4 members
        selected_members = selected_members[4:]      # Remove the used members

    # Assign remaining members to singles or waiting
    if len(selected_members) == 2:
        singles_match = selected_members[:2]
    elif len(selected_members) > 0:
        waiting_member = selected_members

    return doubles_matches, singles_match, waiting_member


def generate_balanced_matches(selected_members, previous_matches=None):
    """Generates multiple balanced matches based on star ratings and avoids repeats."""
    if previous_matches is None:
        previous_matches = []

    # Sort members by star rating (descending)
    sorted_members = sorted(selected_members, key=lambda m: int(m["star_rating"]), reverse=True)

    doubles_matches = []
    singles_match = None
    waiting_member = []

    # Helper function to check if a match is new
    def is_new_match(team1, team2):
        team1_tuple = tuple(sorted(player["first_name"] + player["last_name"] for player in team1))
        team2_tuple = tuple(sorted(player["first_name"] + player["last_name"] for player in team2))
        return (team1_tuple, team2_tuple) not in previous_matches

    # Assign players to balanced doubles matches in groups of 4
    while len(sorted_members) >= 4:
        # Find the best possible match that hasn't been played
        found_match = False
        for i in range(len(sorted_members) - 3):
            for j in range(i + 1, len(sorted_members) - 2):
                for k in range(j + 1, len(sorted_members) - 1):
                    for l in range(k + 1, len(sorted_members)):
                        team1 = [sorted_members[i], sorted_members[l]]
                        team2 = [sorted_members[j], sorted_members[k]]
                        if is_new_match(team1, team2):
                            # Save the match to history
                            team1_tuple = tuple(sorted(player["first_name"] + player["last_name"] for player in team1))
                            team2_tuple = tuple(sorted(player["first_name"] + player["last_name"] for player in team2))
                            previous_matches.append((team1_tuple, team2_tuple))
                            
                            doubles_matches.append(team1 + team2)
                            # Remove selected players from the pool
                            sorted_members = [
                                member
                                for idx, member in enumerate(sorted_members)
                                if idx not in [i, j, k, l]
                            ]
                            found_match = True
                            break
                    if found_match:
                        break
                if found_match:
                    break
            if found_match:
                break
        if not found_match:
            break

    # Attempt to use waiting members for additional matches
    if len(sorted_members) >= 4:
        waiting_match_team1 = sorted_members[:2]
        waiting_match_team2 = sorted_members[2:4]
        doubles_matches.append(waiting_match_team1 + waiting_match_team2)
        sorted_members = sorted_members[4:]
    elif len(sorted_members) == 2:
        singles_match = sorted_members[:2]
        sorted_members = []

    # Any remaining members are considered waiting
    if sorted_members:
        waiting_member = sorted_members

    return doubles_matches, singles_match, waiting_member, previous_matches

def generate_fair_balanced_matches(selected_members, previous_matches=None):
    """Generates fair balanced matches ensuring teammates and opponents have a max star rating difference of 2."""
    if previous_matches is None:
        previous_matches = []

    # Sort players by star rating (highest to lowest)
    sorted_members = sorted(selected_members, key=lambda m: int(m["star_rating"]), reverse=True)

    doubles_matches = []
    singles_match = None
    waiting_members = []

    # Helper function to check if a match is valid
    def is_valid_match(team1, team2):
        """Ensures all players in the match have a max 2-star rating difference."""
        all_players = team1 + team2
        ratings = [int(player["star_rating"]) for player in all_players]
        return max(ratings) - min(ratings) <= 2

    # Helper function to check if match was played before
    def is_new_match(team1, team2):
        team1_tuple = tuple(sorted(player["first_name"] + player["last_name"] for player in team1))
        team2_tuple = tuple(sorted(player["first_name"] + player["last_name"] for player in team2))
        return (team1_tuple, team2_tuple) not in previous_matches

    while len(sorted_members) >= 4:
        found_match = False
        for i in range(len(sorted_members) - 3):
            for j in range(i + 1, len(sorted_members) - 2):
                for k in range(j + 1, len(sorted_members) - 1):
                    for l in range(k + 1, len(sorted_members)):
                        team1 = [sorted_members[i], sorted_members[l]]
                        team2 = [sorted_members[j], sorted_members[k]]

                        if is_valid_match(team1, team2) and is_new_match(team1, team2):
                            team1_tuple = tuple(sorted(player["first_name"] + player["last_name"] for player in team1))
                            team2_tuple = tuple(sorted(player["first_name"] + player["last_name"] for player in team2))
                            previous_matches.append((team1_tuple, team2_tuple))
                            
                            doubles_matches.append(team1 + team2)
                            sorted_members = [m for m in sorted_members if m not in team1 + team2]
                            found_match = True
                            break
                    if found_match:
                        break
                if found_match:
                    break
            if found_match:
                break
        if not found_match:
            break

    # **NEW: Handle remaining players**
    while len(sorted_members) >= 4:
        team1 = [sorted_members.pop(0), sorted_members.pop(-1)]
        team2 = [sorted_members.pop(0), sorted_members.pop(-1)]
        doubles_matches.append(team1 + team2)

    # Assign remaining players to singles or waiting
    if len(sorted_members) == 2:
        if abs(int(sorted_members[0]["star_rating"]) - int(sorted_members[1]["star_rating"])) <= 2:
            singles_match = sorted_members[:2]
        else:
            waiting_members = sorted_members
    elif len(sorted_members) > 0:
        waiting_members = sorted_members

    return doubles_matches, singles_match, waiting_members, previous_matches


@app.route("/flask/logout")
def logout():
    session.pop("logged_in", None)
    flash("You have been logged out.")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

