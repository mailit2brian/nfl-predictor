import streamlit as st
import json
import os
from nfl_data import NFL_SCHEDULE

# Define conferences and divisions structure
NFL_STRUCTURE = {
    "AFC": {
        "AFC East": ["Miami Dolphins", "Buffalo Bills", "New York Jets", "New England Patriots"],
        "AFC North": ["Cincinnati Bengals", "Pittsburgh Steelers", "Cleveland Browns", "Baltimore Ravens"],
        "AFC South": ["Indianapolis Colts", "Houston Texans", "Tennessee Titans", "Jacksonville Jaguars"],
        "AFC West": ["Los Angeles Chargers", "Kansas City Chiefs", "Las Vegas Raiders", "Denver Broncos"]
    },
    "NFC": {
        "NFC East": ["New York Giants", "Washington Commanders", "Philadelphia Eagles", "Dallas Cowboys"],
        "NFC North": ["Minnesota Vikings", "Chicago Bears", "Green Bay Packers", "Detroit Lions"],
        "NFC South": ["New Orleans Saints", "Tampa Bay Buccaneers", "Atlanta Falcons", "Carolina Panthers"],
        "NFC West": ["Los Angeles Rams", "Seattle Seahawks", "Arizona Cardinals", "San Francisco 49ers"]
    }
}

# File to store user picks permanently on the computer
PICKS_FILE = "saved_picks.json"

def load_saved_picks():
    """Loads saved picks from local storage file if it exists."""
    if os.path.exists(PICKS_FILE):
        try:
            with open(PICKS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_picks_to_disk():
    """Saves current dictionary picks to local storage file."""
    try:
        with open(PICKS_FILE, "w") as f:
            json.dump(st.session_state.user_predictions, f)
    except:
        pass

# Initialize session state from local file
if "user_predictions" not in st.session_state:
    st.session_state.user_predictions = load_saved_picks()

def get_corresponding_prediction(team, week_num, opponent):
    primary_key = f"{team}_week_{week_num}"
    if primary_key in st.session_state.user_predictions:
        return st.session_state.user_predictions[primary_key]
        
    if opponent in NFL_SCHEDULE:
        opp_schedule = NFL_SCHEDULE[opponent]
        if len(opp_schedule) >= week_num:
            opp_key = f"{opponent}_week_{week_num}"
            if opp_key in st.session_state.user_predictions:
                opp_choice = st.session_state.user_predictions[opp_key]
                return "Loss" if opp_choice == "Win" else "Win"
                    
    return "Win"

def calculate_team_record(team_name):
    schedule = NFL_SCHEDULE.get(team_name, [])
    w = 0
    l = 0
    for w_num, game_info in enumerate(schedule, start=1):
        game_str = str(game_info)
        if "Bye" in game_str:
            continue
        if game_str.lower().startswith("at "):
            opp = game_str[3:].strip()
        else:
            opp = game_str.replace("vs ", "").replace("vs. ", "").strip()
            
        p_key = f"{team_name}_week_{w_num}"
        if p_key in st.session_state.user_predictions:
            res = st.session_state.user_predictions[p_key]
        else:
            res = get_corresponding_prediction(team_name, w_num, opp)
            st.session_state.user_predictions[p_key] = res
            
        if res == "Win":
            w += 1
        else:
            l += 1
    return w, l

st.sidebar.title("NFL Navigation")

# Conference selection
selected_conference = st.sidebar.selectbox("Select Conference:", list(NFL_STRUCTURE.keys()))

# Division selection
selected_division = st.sidebar.selectbox("Select Division:", list(NFL_STRUCTURE[selected_conference].keys()))

# Team selection
selected_team = st.sidebar.selectbox("Select Team:", NFL_STRUCTURE[selected_conference][selected_division])

st.title(f"2026 Schedule & Predictions: {selected_team}")
st.markdown(f"*{selected_conference} - {selected_division}*")
st.write("Select whether your team will **Win** or **Lose** each matchup below:")
st.markdown("---")

schedule_list = NFL_SCHEDULE.get(selected_team, [])

wins = 0
losses = 0

for week_num, game_info in enumerate(schedule_list, start=1):
    game_str = str(game_info)
    
    if "Bye" in game_str:
        st.write(f"**Week {week_num}**: Bye Week")
        st.markdown("---")
        continue
        
    if game_str.lower().startswith("at "):
        opponent = game_str[3:].strip()
        location = "Away"
        matchup_label = f"at {opponent}"
    else:
        opponent = game_str.replace("vs ", "").replace("vs. ", "").strip()
        location = "Home"
        matchup_label = f"vs {opponent}"

    prediction_key = f"{selected_team}_week_{week_num}"
    
    current_val = get_corresponding_prediction(selected_team, week_num, opponent)
    st.session_state.user_predictions[prediction_key] = current_val
    
    default_index = 0 if current_val == "Win" else 1

    result = st.radio(
        f"**Week {week_num}** {matchup_label} *({location})*",
        ["Win", "Loss"],
        index=default_index,
        key=f"radio_{selected_team}_{week_num}",
        horizontal=True
    )
    
    # Update state and immediately save to disk
    if st.session_state.user_predictions[prediction_key] != result:
        st.session_state.user_predictions[prediction_key] = result
        save_picks_to_disk()

    if result == "Win":
        wins += 1
    else:
        losses += 1
    st.markdown("---")

# --- SIDEBAR PROJECTED RECORD & PLAYOFF PICTURE ---
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Projected Record")
st.sidebar.write(selected_team)
st.sidebar.markdown(f"### {wins} - {losses}")

st.sidebar.markdown("---")
st.sidebar.subheader("🏆 Playoff Picture")

for conf_name, divs in NFL_STRUCTURE.items():
    st.sidebar.markdown(f"### {conf_name} Playoff Race")
    
    div_winners = []
    wild_card_pool = []
    
    for div_name, teams in divs.items():
        team_records = []
        for t in teams:
            tw, tl = calculate_team_record(t)
            team_records.append((t, tw, tl))
        
        team_records.sort(key=lambda x: (x[1], -x[2]), reverse=True)
        winner = team_records[0]
        div_winners.append(winner)
        
        for tr in team_records[1:]:
            wild_card_pool.append(tr)
            
    div_winners.sort(key=lambda x: (x[1], -x[2]), reverse=True)
    wild_card_pool.sort(key=lambda x: (x[1], -x[2]), reverse=True)
    wild_card_teams = wild_card_pool[:3]
    
    st.sidebar.markdown("**Division Winners (Seeds 1-4)**")
    for idx, (t_name, tw, tl) in enumerate(div_winners, start=1):
        st.sidebar.write(f"Seed {idx}: {t_name} ({tw}-{tl})")
        
    st.sidebar.markdown("**Wild Card Teams (Seeds 5-7)**")
    for idx, (t_name, tw, tl) in enumerate(wild_card_teams, start=5):
        st.sidebar.write(f"Seed {idx}: {t_name} ({tw}-{tl})")
    
    st.sidebar.markdown("---")