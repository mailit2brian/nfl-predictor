import streamlit as st
import json
import os
import base64
import hashlib
from nfl_data import NFL_SCHEDULE, NFL_SOS
from datetime import datetime

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

# Vegas Over/Under Win Totals (as of July 27, 2026)
VEGAS_ODDS = {
    "Buffalo Bills": 10.5,
    "Miami Dolphins": 4.5,
    "New England Patriots": 10.5,
    "New York Jets": 5.5,
    "Baltimore Ravens": 11.5,
    "Cincinnati Bengals": 10.5,
    "Cleveland Browns": 6.5,
    "Pittsburgh Steelers": 8.5,
    "Houston Texans": 9.5,
    "Indianapolis Colts": 8.5,
    "Jacksonville Jaguars": 9.5,
    "Tennessee Titans": 6.5,
    "Denver Broncos": 9.5,
    "Kansas City Chiefs": 10.5,
    "Las Vegas Raiders": 5.5,
    "Los Angeles Chargers": 10.5,
    "Dallas Cowboys": 9.5,
    "New York Giants": 7.5,
    "Philadelphia Eagles": 10.5,
    "Washington Commanders": 7.5,
    "Chicago Bears": 9.5,
    "Detroit Lions": 10.5,
    "Green Bay Packers": 10.5,
    "Minnesota Vikings": 8.5,
    "Atlanta Falcons": 6.5,
    "Carolina Panthers": 7.5,
    "New Orleans Saints": 8.5,
    "Tampa Bay Buccaneers": 8.5,
    "Arizona Cardinals": 4.5,
    "Los Angeles Rams": 11.5,
    "San Francisco 49ers": 10.5,
    "Seattle Seahawks": 10.5,
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

def load_game_results_local():
    """Load game results from local JSON file."""
    local_file = "game_results.json"
    if os.path.exists(local_file):
        try:
            with open(local_file, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except:
            return {}
    return {}

def load_game_results_github():
    """Load game results from GitHub."""
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        if not token:
            return {}
        
        import requests
        headers = {"Authorization": f"token {token}"}
        url = "https://api.github.com/repos/mailit2brian/nfl-predictor/contents/game_results.json"
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()
            file_content = base64.b64decode(content["content"]).decode()
            data = json.loads(file_content)
            return data if isinstance(data, dict) else {}
        return {}
    except:
        return {}

def save_game_results_local(results_dict):
    """Save game results to local JSON file."""
    try:
        with open("game_results.json", "w") as f:
            f.write(json.dumps(results_dict, indent=2))
    except Exception as e:
        st.error(f"Error saving game results locally: {e}")

def save_game_results_github(results_dict):
    """Save game results to GitHub."""
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        if not token:
            st.error("No GitHub token found in secrets")
            return False
        
        import requests
        headers = {"Authorization": f"token {token}"}
        url = "https://api.github.com/repos/mailit2brian/nfl-predictor/contents/game_results.json"
        
        file_content = json.dumps(results_dict, indent=2)
        file_content_b64 = base64.b64encode(file_content.encode()).decode()
        
        # Get fresh SHA every time before saving
        response = requests.get(url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json()["sha"]
        elif response.status_code != 404:
            st.error(f"Failed to get file SHA: {response.status_code}")
            return False
        
        data = {
            "message": f"Update game results {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": file_content_b64,
        }
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            return True
        else:
            st.error(f"Failed to save to GitHub: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        st.error(f"Error saving game results to GitHub: {str(e)}")
        return False

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

def calculate_actual_team_record(team_name):
    """Calculate actual W-L record from uploaded game results."""
    schedule = NFL_SCHEDULE.get(team_name, [])
    game_results = st.session_state.get("game_results", {})
    wins, losses = 0, 0
    
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
        actual_winner = game_results.get(game_id)
        if not actual_winner:
            continue
        
        if actual_winner == team_name:
            wins += 1
        else:
            losses += 1
    
    return wins, losses

def calculate_season_accuracy(username):
    """Calculate user's season accuracy as (correct, incorrect)."""
    user_picks = st.session_state.get("user_predictions", {})
    game_results = st.session_state.get("game_results", {})
    
    correct = 0
    incorrect = 0
    
    for game_id, predicted_winner in user_picks.items():
        actual_winner = game_results.get(game_id)
        if not actual_winner:
            continue
        if predicted_winner == actual_winner:
            correct += 1
        else:
            incorrect += 1
    
    return correct, incorrect

def get_accuracy_percentage():
    """Calculate current user's season accuracy percentage."""
    username = st.session_state.get("current_user", "DefaultUser")
    correct, incorrect = calculate_season_accuracy(username)
    total = correct + incorrect
    if total == 0:
        return 0.0
    return (correct / total) * 100

def get_all_users_accuracy():
    """Get accuracy for all tracked users: Brian, Chris, Jason, Mike."""
    tracked_users = ["Brian", "Chris", "Jason", "Mike"]
    game_results = st.session_state.get("game_results", {})
    user_accuracy = []

    for user in tracked_users:
        local_picks = load_user_picks_local(user)
        github_picks = load_user_picks_github(user)
        user_picks = local_picks if local_picks else github_picks

        correct = 0
        incorrect = 0

        for game_id, actual_winner in game_results.items():
            if game_id in user_picks:
                predicted_winner = user_picks[game_id]
                if predicted_winner == actual_winner:
                    correct += 1
                else:
                    incorrect += 1

        total = correct + incorrect
        accuracy_pct = (correct / total * 100) if total > 0 else 0.0
        user_accuracy.append({
            "user": user,
            "correct": correct,
            "incorrect": incorrect,
            "record": f"{correct}-{incorrect}",
            "accuracy": accuracy_pct,
        })

    user_accuracy.sort(key=lambda x: x["accuracy"], reverse=True)
    return user_accuracy

# --- PAGE NAVIGATION ---
page = st.sidebar.radio("Navigate:", ["Teams & Picks", "Admin - Enter Results", "Leaderboard"], key="page_selector")

# --- SIDEBAR: USER PROFILE SELECTION ---
st.sidebar.markdown("---")
st.sidebar.title("Core Four Picks")
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

# Always reload game results from GitHub to ensure fresh data
local_results = load_game_results_local()
github_results = load_game_results_github()
st.session_state.game_results = local_results if local_results else github_results

correct_picks, incorrect_picks = calculate_season_accuracy(username)
accuracy_pct = get_accuracy_percentage()
st.sidebar.write(f"**Season Accuracy: {correct_picks}-{incorrect_picks} ({accuracy_pct:.1f}%)**")

# --- PAGE: ADMIN - ENTER RESULTS ---
if page == "Admin - Enter Results":
    st.title("📋 Admin: Enter Weekly Results")
    st.markdown("---")
    
    week_num = st.selectbox("Select Week:", list(range(1, 19)), key="week_selector")
    
    # Collect all games for this week from all teams
    week_games = {}
    for team_name, schedule in NFL_SCHEDULE.items():
        if week_num <= len(schedule):
            game_info = schedule[week_num - 1]
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
            
            # Only add each game once (not once per team)
            if game_id not in week_games:
                week_games[game_id] = (home_team, away_team)
    
    if not week_games:
        st.info(f"No games found for Week {week_num}")
    else:
        st.write(f"**Week {week_num}** - {len(week_games)} games")
        st.markdown("---")
        
        # Clear week button
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🗑️ Clear Week", key="clear_week_btn", use_container_width=True, help="Delete all results for this week"):
                # Remove all games from this week
                for game_id in week_games.keys():
                    if game_id in st.session_state.game_results:
                        del st.session_state.game_results[game_id]
                
                # Save to GitHub
                save_game_results_local(st.session_state.game_results)
                save_game_results_github(st.session_state.game_results)
                st.success(f"✅ Cleared all results for Week {week_num}")
                st.rerun()
        
        st.markdown("---")
        
        # Initialize session state for admin selections
        if "admin_selections" not in st.session_state:
            st.session_state.admin_selections = {}
        
        current_game_results = st.session_state.get("game_results", {})
        
        for game_id, (home_team, away_team) in sorted(week_games.items()):
            # Load current value from game_results
            current_winner = current_game_results.get(game_id)
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**{away_team}** @ **{home_team}**")
            
            # Away team button
            with col2:
                if st.button(f"⬅️ {away_team}", key=f"away_{game_id}", use_container_width=True):
                    st.session_state.admin_selections[game_id] = away_team
                    st.session_state.game_results[game_id] = away_team
            
            # Home team button
            with col3:
                if st.button(f"{home_team} ➡️", key=f"home_{game_id}", use_container_width=True):
                    st.session_state.admin_selections[game_id] = home_team
                    st.session_state.game_results[game_id] = home_team
            
            # Display current selection (highlighted)
            selected = st.session_state.admin_selections.get(game_id, current_winner)
            if selected:
                st.caption(f"✅ Winner: **{selected}**")
            else:
                st.caption("— No selection")
            st.markdown("---")
        
        # Save button
        if st.button("💾 Save Week Results", key="save_results_btn", use_container_width=True):
            # Transfer admin selections to game_results BEFORE saving
            for game_id, winner in st.session_state.admin_selections.items():
                st.session_state.game_results[game_id] = winner
            
            st.write(f"DEBUG: Data to save: {st.session_state.game_results}")
            
            save_game_results_local(st.session_state.game_results)
            success = save_game_results_github(st.session_state.game_results)
            
            if success:
                st.success(f"✅ Saved Week {week_num} results to GitHub!")
                st.session_state.admin_selections = {}
            else:
                st.error("❌ Failed to save to GitHub")

# --- PAGE: LEADERBOARD ---
elif page == "Leaderboard":
    import pandas as pd
    st.title("Season Accuracy Leaderboard")
    st.markdown("---")

    game_results = st.session_state.get("game_results", {})
    if not game_results:
        st.info("No results uploaded yet. Go to Admin tab to enter game results.")
    else:
        leaderboard_data = get_all_users_accuracy()
        rows = []
        for idx, entry in enumerate(leaderboard_data, start=1):
            rows.append({
                "Rank": idx,
                "User": entry["user"],
                "Record": entry["record"],
                "Accuracy %": f"{entry['accuracy']:.1f}%",
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("---")
        st.write("*Updates automatically when weekly results are entered in Admin tab*")

# --- PAGE: TEAMS & PICKS ---
else:
    st.sidebar.markdown("---")
    selected_conference = st.sidebar.selectbox("Select Conference:", list(NFL_STRUCTURE.keys()))
    selected_division = st.sidebar.selectbox("Select Division:", list(NFL_STRUCTURE[selected_conference].keys()))
    selected_team = st.sidebar.selectbox("Select Team:", NFL_STRUCTURE[selected_conference][selected_division])
    
    # --- PROJECTED RECORD AND VEGAS O/U ---
    st.sidebar.markdown("")
    w, l = calculate_team_record(selected_team)
    vegas_ou = VEGAS_ODDS.get(selected_team, "N/A")
    
    st.sidebar.write(f"**Projected Record:** {w}-{l}")
    st.sidebar.write(f"**Vegas O/U:** {vegas_ou}")
    
    # --- DIVISION STANDINGS ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("Division Standings")
    division_teams = NFL_STRUCTURE[selected_conference][selected_division]
    standings = []
    for team in division_teams:
        projected_w, projected_l = calculate_team_record(team)
        actual_w, actual_l = calculate_actual_team_record(team)
        sos_data = NFL_SOS.get(team, {})
        sos_rank = sos_data.get("rank", "-")
        opp_win_pct = sos_data.get("opp_win_pct", 0)
        standings.append((team, actual_w, actual_l, projected_w, projected_l, sos_rank, opp_win_pct))
    
    # Check if we have actual game results
    has_uploaded_results = len(st.session_state.get("game_results", {})) > 0
    
    # Build standings data
    proj_standings = sorted(standings, key=lambda x: (-x[3], x[4]))
    actual_standings = sorted(standings, key=lambda x: (-x[1], x[2]))
    
    # Display side-by-side standings
    col_left, col_right = st.sidebar.columns(2)
    
    with col_left:
        st.caption("**Projected**")
        st.caption("Rank | Team | W-L | SOS")
        st.caption("-----|------|-----|-----")
        for idx, (team, _, _, projected_w, projected_l, sos_rank, _) in enumerate(proj_standings, start=1):
            st.caption(f"{idx}. {team} | {projected_w}-{projected_l} | {sos_rank}")
    
    with col_right:
        st.caption("**Actual**")
        st.caption("Rank | Team | W-L")
        st.caption("-----|------|-----")
        if has_uploaded_results:
            for idx, (team, actual_w, actual_l, _, _, _, _) in enumerate(actual_standings, start=1):
                st.caption(f"{idx}. {team} | {actual_w}-{actual_l}")
        else:
            st.caption("*(No results yet)*")
    
    # --- MAIN CONTENT: SCHEDULE ---
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
    
    # Build playoff picture data
    playoff_data = {}
    for conf_name, divs in NFL_STRUCTURE.items():
        div_winners = []
        wild_card_pool = []
        
        for div_name, teams in divs.items():
            team_records = []
            for t in teams:
                tw, tl = calculate_team_record(t)
                team_records.append((t, tw, tl))
            team_records.sort(key=lambda x: (-x[1], x[2]))
            div_winners.append(team_records[0])
            for tr in team_records[1:]:
                wild_card_pool.append(tr)
                
        div_winners.sort(key=lambda x: (-x[1], x[2]))
        wild_card_pool.sort(key=lambda x: (-x[1], x[2]))
        wild_card_teams = wild_card_pool[:3]
        
        playoff_data[conf_name] = {
            "div_winners": div_winners,
            "wild_card": wild_card_teams
        }
    
    # --- PLAYOFF PICTURE SECTION ---
    st.sidebar.subheader("Playoff Picture")
    col1, col2 = st.sidebar.columns([1, 0.3])
    with col1:
        pass
    with col2:
        if st.sidebar.button("🖨️", key="print_playoff", help="Print", use_container_width=True):
            tracked_users = ["Brian", "Chris", "Jason", "Mike"]
            users_html = "".join(f'<span>{user}</span>' for user in tracked_users)

            playoff_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>2026 NFL Playoff Picture</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1 {{ text-align: center; font-size: 24px; margin-bottom: 5px; }}
                    .tracked-users {{
                        display: flex;
                        justify-content: center;
                        gap: 18px;
                        flex-wrap: wrap;
                        margin-bottom: 20px;
                        color: #333;
                        font-size: 18px;
                        font-weight: bold;
                    }}
                    h2 {{ font-size: 18px; margin-top: 25px; border-bottom: 2px solid #000; padding-bottom: 10px; }}
                    h3 {{ font-size: 14px; margin-top: 15px; font-weight: bold; }}
                    .seed {{ margin-left: 20px; font-size: 13px; line-height: 1.6; }}
                    @media print {{ body {{ margin: 10px; }} }}
                </style>
            </head>
            <body>
                <h1>2026 NFL Playoff Picture</h1>
                <div class="tracked-users">{users_html}</div>
            """
            
            for conf_name, data in playoff_data.items():
                playoff_html += f"<h2>{conf_name}</h2>"
                playoff_html += "<h3>Division Winners (Seeds 1-4)</h3>"
                for idx, (t_name, tw, tl) in enumerate(data["div_winners"], start=1):
                    playoff_html += f'<div class="seed">Seed {idx}: {t_name} ({tw}-{tl})</div>'
                
                playoff_html += "<h3>Wild Card Teams (Seeds 5-7)</h3>"
                for idx, (t_name, tw, tl) in enumerate(data["wild_card"], start=5):
                    playoff_html += f'<div class="seed">Seed {idx}: {t_name} ({tw}-{tl})</div>'
            
            playoff_html += """
            </body>
            </html>
            <script>
            window.onafterprint = function() { window.close(); };
            window.print();
            </script>
            """
            
            st.components.v1.html(playoff_html, height=0, width=1)
    
    # Display playoff picture
    for conf_name, data in playoff_data.items():
        st.sidebar.markdown(f"### {conf_name} Playoff Race")
        st.sidebar.markdown("**Division Winners (Seeds 1-4)**")
        for idx, (t_name, tw, tl) in enumerate(data["div_winners"], start=1):
            st.sidebar.write(f"Seed {idx}: {t_name} ({tw}-{tl})")
            
        st.sidebar.markdown("**Wild Card Teams (Seeds 5-7)**")
        for idx, (t_name, tw, tl) in enumerate(data["wild_card"], start=5):
            st.sidebar.write(f"Seed {idx}: {t_name} ({tw}-{tl})")
        st.sidebar.markdown("---")
    
    # --- ALL DIVISIONS SECTION ---
    st.sidebar.markdown("**All Divisions Standings**")
    col1, col2 = st.sidebar.columns([1, 0.3])
    with col1:
        pass
    with col2:
        if st.sidebar.button("🖨️", key="print_divisions", help="Print", use_container_width=True):
            # Build divisions HTML - Landscape with side-by-side layout and FIXED column widths, with username
            divisions_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>2026 NFL Division Standings</title>
                <style>
                    @page {{ size: landscape; margin: 0.3in; }}
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{ font-family: Arial, sans-serif; font-size: 10px; line-height: 1.2; }}
                    h1 {{ text-align: center; font-size: 16px; margin-bottom: 5px; }}
                    .username {{ text-align: center; font-size: 14px; font-weight: bold; margin-bottom: 10px; color: #333; }}
                    .container {{ display: flex; gap: 12px; }}
                    .conference {{ flex: 1; }}
                    .conf-title {{ font-size: 13px; font-weight: bold; text-align: center; margin-bottom: 8px; border-bottom: 2px solid #000; padding-bottom: 4px; }}
                    .division {{ margin-bottom: 6px; page-break-inside: avoid; }}
                    .div-title {{ font-size: 10px; font-weight: bold; margin-bottom: 2px; color: #333; }}
                    table {{ width: 100%; border-collapse: collapse; font-size: 9px; table-layout: fixed; }}
                    th, td {{ border: 0.5px solid #999; padding: 2px 3px; text-align: left; overflow: hidden; }}
                    th {{ background-color: #e8e8e8; font-weight: bold; font-size: 8px; }}
                    td {{ font-size: 8px; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    /* Fixed column widths */
                    .col-r {{ width: 20px; }}
                    .col-team {{ width: 100px; }}
                    .col-wl {{ width: 40px; }}
                    .col-sos {{ width: 35px; }}
                    .col-pct {{ width: 30px; }}
                    @media print {{ 
                        body {{ font-size: 10px; }}
                        .conf-title {{ font-size: 12px; }}
                        .div-title {{ font-size: 9px; }}
                        table {{ font-size: 8px; }}
                    }}
                </style>
            </head>
            <body>
                <h1>2026 NFL Division Standings</h1>
                <div class="username">{username}</div>
                <div class="container">
            """
            
            # Build AFC (left column)
            divisions_html += '<div class="conference">'
            divisions_html += '<div class="conf-title">AFC</div>'
            
            for div_name, teams in NFL_STRUCTURE["AFC"].items():
                divisions_html += '<div class="division">'
                divisions_html += f'<div class="div-title">{div_name}</div>'
                divisions_html += "<table><tr><th class='col-r'>R</th><th class='col-team'>Team</th><th class='col-wl'>W-L</th><th class='col-sos'>SOS</th><th class='col-pct'>%</th></tr>"
                
                team_records = []
                for t in teams:
                    tw, tl = calculate_team_record(t)
                    sos_data = NFL_SOS.get(t, {})
                    sos_rank = sos_data.get("rank", "-")
                    opp_win_pct = sos_data.get("opp_win_pct", 0)
                    team_records.append((t, tw, tl, sos_rank, opp_win_pct))
                
                team_records.sort(key=lambda x: (-x[1], x[2]))
                
                for idx, (team, tw, tl, sos_rank, opp_pct) in enumerate(team_records, start=1):
                    divisions_html += f"<tr><td class='col-r'>{idx}</td><td class='col-team'>{team}</td><td class='col-wl'>{tw}-{tl}</td><td class='col-sos'>{sos_rank}</td><td class='col-pct'>.{int(opp_pct * 1000) / 1000}</td></tr>"
                
                divisions_html += "</table>"
                divisions_html += '</div>'
            
            divisions_html += '</div>'
            
            # Build NFC (right column)
            divisions_html += '<div class="conference">'
            divisions_html += '<div class="conf-title">NFC</div>'
            
            for div_name, teams in NFL_STRUCTURE["NFC"].items():
                divisions_html += '<div class="division">'
                divisions_html += f'<div class="div-title">{div_name}</div>'
                divisions_html += "<table><tr><th class='col-r'>R</th><th class='col-team'>Team</th><th class='col-wl'>W-L</th><th class='col-sos'>SOS</th><th class='col-pct'>%</th></tr>"
                
                team_records = []
                for t in teams:
                    tw, tl = calculate_team_record(t)
                    sos_data = NFL_SOS.get(t, {})
                    sos_rank = sos_data.get("rank", "-")
                    opp_win_pct = sos_data.get("opp_win_pct", 0)
                    team_records.append((t, tw, tl, sos_rank, opp_win_pct))
                
                team_records.sort(key=lambda x: (-x[1], x[2]))
                
                for idx, (team, tw, tl, sos_rank, opp_pct) in enumerate(team_records, start=1):
                    divisions_html += f"<tr><td class='col-r'>{idx}</td><td class='col-team'>{team}</td><td class='col-wl'>{tw}-{tl}</td><td class='col-sos'>{sos_rank}</td><td class='col-pct'>.{int(opp_pct * 1000) / 1000}</td></tr>"
                
                divisions_html += "</table>"
                divisions_html += '</div>'
            
            divisions_html += '</div></div>'
            
            divisions_html += """
            </body>
            </html>
            <script>
            window.onafterprint = function() { window.close(); };
            window.print();
            </script>
            """
            
            st.components.v1.html(divisions_html, height=0, width=1)
