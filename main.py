import streamlit as st
import json
import os
import base64
from nfl_data import NFL_SCHEDULE, NFL_SOS

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

def get_all_teams():
    """Flatten all teams from NFL_STRUCTURE."""
    all_teams = []
    for conf in NFL_STRUCTURE.values():
        for div in conf.values():
            all_teams.extend(div)
    return all_teams

def get_opponent_from_gamestr(game_str):
    """Extract opponent from game string."""
    game_lower = game_str.lower()
    if "bye" in game_lower:
        return None
    if game_lower.startswith("at "):
        return game_str[3:].strip()
    else:
        return game_str.replace("vs ", "").replace("vs. ", "").strip()

def generate_game_id(week_num, team1, team2):
    """Create deterministic game ID using alphabetical sorting."""
    teams = sorted([team1, team2])
    return f"week{week_num}_{teams[0].replace(' ', '')}vs{teams[1].replace(' ', '')}"

def load_user_picks_local(username):
    """Load picks from local JSON file."""
    local_file = f"picks_{username}.json"
    if os.path.exists(local_file):
        try:
            with open(local_file, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def load_user_picks_github(username):
    """Load picks from GitHub."""
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        if not token:
            return {}
        
        import requests
        headers = {"Authorization": f"token {token}"}
        url = f"https://api.github.com/repos/mailit2brian/nfl-predictor/contents/picks_{username}.json"
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()
            file_content = base64.b64decode(content["content"]).decode()
            return json.loads(file_content)
        else:
            return {}
    except:
        return {}

def save_user_pick_github(username, picks_dict):
    """Save picks to GitHub."""
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        if not token:
            return False
        
        import requests
        headers = {"Authorization": f"token {token}"}
        url = f"https://api.github.com/repos/mailit2brian/nfl-predictor/contents/picks_{username}.json"
        
        # Prepare the file content
        file_content = json.dumps(picks_dict, indent=2)
        file_content_b64 = base64.b64encode(file_content.encode()).decode()
        
        # Check if file exists to get the SHA
        response = requests.get(url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json()["sha"]
        
        # Prepare the request
        data = {
            "message": f"Update picks for {username}",
            "content": file_content_b64,
        }
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=headers, json=data)
        return response.status_code in [200, 201]
    except Exception as e:
        st.warning(f"Could not sync to GitHub: {e}")
        return False

def save_user_pick_local(username, picks_dict):
    """Save picks to local JSON file."""
    try:
        with open(f"picks_{username}.json", "w") as f:
            f.write(json.dumps(picks_dict, indent=2))
    except Exception as e:
        st.error(f"Error saving pick locally: {e}")

def get_pick_for_game(game_id, home_team, away_team, team_perspective):
    """Retrieve pick for a game from a team's perspective."""
    picks_dict = st.session_state.get("user_predictions", {})
    
    if game_id not in picks_dict:
        return "No Pick"

    pick_result = picks_dict[game_id]
    
    # pick_result is now the name of the winning team
    if pick_result == team_perspective:
        return "Win"
    else:
        return "Loss"

def set_pick_for_game(gid, ht, at, tp, wk):
    """Set pick for a game (automatically syncs both teams)."""
    win_or_loss = st.session_state[wk]
    
    # If "No Pick" selected, don't save anything
    if win_or_loss == "No Pick":
        if gid in st.session_state.user_predictions:
            del st.session_state.user_predictions[gid]
    else:
        # Save the WINNING team name, not home_win/away_win
        if win_or_loss == "Win":
            pick_result = tp  # Team perspective wins
        else:
            # Determine which team loses (the one that's NOT the perspective)
            pick_result = ht if tp == at else at  # The other team wins
        
        st.session_state.user_predictions[gid] = pick_result
    
    # Save to both local and GitHub
    save_user_pick_local(username, st.session_state.user_predictions)
    save_user_pick_github(username, st.session_state.user_predictions)

def calculate_team_record(team_name):
    """Calculate W-L record from picks."""
    schedule = NFL_SCHEDULE.get(team_name, [])
    w, l = 0, 0
    
    for week_num, game_info in enumerate(schedule, start=1):
        game_str = str(game_info)
        if "bye" in game_str.lower():
            continue
        
        opponent = get_opponent_from_gamestr(game_str)
        if not opponent:
            continue

        if game_str.lower().startswith("at "):
            home_team = opponent
            away_team = team_name
        else:
            home_team = team_name
            away_team = opponent

        game_id = generate_game_id(week_num, home_team, away_team)
        result = get_pick_for_game(game_id, home_team, away_team, team_name)
        
        if result == "Win":
            w += 1
        elif result == "Loss":
            l += 1
    
    return w, l

# --- SIDEBAR: USER PROFILE SELECTION ---
st.sidebar.title("NFL Navigation")
st.sidebar.subheader("User Profile")
username = st.sidebar.text_input("Enter Your Name:", value="My Picks").strip()

if not username:
    username = "DefaultUser"

if "current_user" not in st.session_state or st.session_state.current_user != username:
    st.session_state.current_user = username
    # Load from local first (for current session data)
    local_picks = load_user_picks_local(username)
    # Load from GitHub as backup
    github_picks = load_user_picks_github(username)
    # Prioritize local picks if they exist, otherwise use GitHub
    st.session_state.user_predictions = local_picks if local_picks else github_picks

if "user_predictions" not in st.session_state:
    local_picks = load_user_picks_local(username)
    github_picks = load_user_picks_github(username)
    st.session_state.user_predictions = local_picks if local_picks else github_picks

# --- MAIN UI ---
st.sidebar.markdown("---")
selected_conference = st.sidebar.selectbox("Select Conference:", list(NFL_STRUCTURE.keys()))
selected_division = st.sidebar.selectbox("Select Division:", list(NFL_STRUCTURE[selected_conference].keys()))
selected_team = st.sidebar.selectbox("Select Team:", NFL_STRUCTURE[selected_conference][selected_division])

# --- PROJECTED RECORD (COMPACT IN BOX) ---
st.sidebar.markdown("")
w, l = calculate_team_record(selected_team)
st.sidebar.metric("Projected Record", f"{w}-{l}", label_visibility="collapsed")

# --- DIVISION STANDINGS WITH SOS (COMPACT BOX) ---
st.sidebar.markdown("---")
st.sidebar.subheader("Division Standings")
division_teams = NFL_STRUCTURE[selected_conference][selected_division]
standings = []
for team in division_teams:
    tw, tl = calculate_team_record(team)
    sos_data = NFL_SOS.get(team, {})
    sos_rank = sos_data.get("rank", "-")
    opp_win_pct = sos_data.get("opp_win_pct", 0)
    standings.append((team, tw, tl, sos_rank, opp_win_pct))

standings.sort(key=lambda x: (x[1], -x[2]), reverse=True)

# Display header
st.sidebar.caption("Rank | Team | W-L | SOS | Opp. Win %")
st.sidebar.caption("-----|------|-----|-----|----------")

for idx, (team, tw, tl, sos_rank, opp_pct) in enumerate(standings, start=1):
    st.sidebar.caption(f"{idx}. {team} ({tw}-{tl}) | {sos_rank} | .{int(opp_pct * 1000)}")

st.title(f"2026 Schedule & Predictions: {selected_team}")
st.markdown(f"*{selected_conference} - {selected_division}* (Editing as: **{username}**)")
st.write("Select whether your team will Win or Lose each matchup below:")
st.markdown("---")

schedule_list = NFL_SCHEDULE.get(selected_team, [])
wins = 0
losses = 0

for week_num, game_info in enumerate(schedule_list, start=1):
    game_str = str(game_info)
    
    if "bye" in game_str.lower():
        st.write(f"**Week {week_num}**: Bye Week")
        st.markdown("---")
        continue
        
    opponent = get_opponent_from_gamestr(game_str)
    if not opponent:
        continue

    if game_str.lower().startswith("at "):
        location = "Away"
        matchup_label = f"at {opponent}"
        home_team = opponent
        away_team = selected_team
    else:
        location = "Home"
        matchup_label = f"vs {opponent}"
        home_team = selected_team
        away_team = opponent

    game_id = generate_game_id(week_num, home_team, away_team)
    current_val = get_pick_for_game(game_id, home_team, away_team, selected_team)
    widget_key = f"radio_{game_id}_{selected_team}"

    if widget_key not in st.session_state:
        st.session_state[widget_key] = current_val

    result = st.radio(
        f"**Week {week_num}** {matchup_label} *({location})*",
        ["No Pick", "Win", "Loss"],
        key=widget_key,
        horizontal=True,
        on_change=set_pick_for_game,
        args=(game_id, home_team, away_team, selected_team, widget_key)
    )

    if result == "Win":
        wins += 1
    elif result == "Loss":
        losses += 1

    st.markdown("---")

st.sidebar.markdown("---")
st.sidebar.subheader("Playoff Picture")

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
        div_winners.append(team_records[0])
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
