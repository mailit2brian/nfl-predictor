import streamlit as st
import json
import os
import psycopg2
from hashlib import md5
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

# --- DATABASE CONNECTION SETUP ---
def get_db_connection():
    try:
        if "postgres" in st.secrets:
            return psycopg2.connect(st.secrets["postgres"]["connection_string"])
    except:
        pass
    return None

def init_db():
    """Initialize game-centric schema."""
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        # Games table (immutable reference)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                week INT,
                home_team TEXT,
                away_team TEXT,
                game_datetime TIMESTAMP DEFAULT NOW()
            )
        """)
        # Picks table (normalized by game, not by team)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_picks (
                username TEXT,
                game_id TEXT,
                pick_result TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (username, game_id),
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        cur.close()
        conn.close()

init_db()

# --- GAME ID GENERATION ---
def generate_game_id(week_num, home_team, away_team):
    """
    Create deterministic game ID: week{week}_hometeam_awayteam_hash
    Ensures consistency across both teams' schedules.
    """
    key = f"{week_num}_{home_team}_{away_team}".lower()
    hash_suffix = md5(key.encode()).hexdigest()[:8]
    return f"week{week_num}_{home_team.replace(' ', '')}_{away_team.replace(' ', '')}_{hash_suffix}"

def seed_games_table():
    """
    Populate games table by traversing all teams' schedules once.
    Ensures each game appears exactly once in the DB.
    """
    conn = get_db_connection()
    if not conn:
        return

    cur = conn.cursor()
    seeded_game_ids = set()

    try:
        for team_name in get_all_teams():
            schedule = NFL_SCHEDULE.get(team_name, [])
            
            for week_num, game_info in enumerate(schedule, start=1):
                game_str = str(game_info)
                if "bye" in game_str.lower():
                    continue

                opponent = get_opponent_from_gamestr(game_str)
                if not opponent:
                    continue

                # Determine home/away
                if game_str.lower().startswith("at "):
                    home_team = opponent
                    away_team = team_name
                else:
                    home_team = team_name
                    away_team = opponent

                game_id = generate_game_id(week_num, home_team, away_team)

                # Idempotent: skip if already seeded
                if game_id in seeded_game_ids:
                    continue
                seeded_game_ids.add(game_id)

                # Insert or ignore
                cur.execute("""
                    INSERT INTO games (game_id, week, home_team, away_team)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (game_id) DO NOTHING
                """, (game_id, week_num, home_team, away_team))

        conn.commit()
    except Exception as e:
        st.error(f"Error seeding games: {e}")
    finally:
        cur.close()
        conn.close()

seed_games_table()

def get_all_teams():
    """Flatten all teams from NFL_STRUCTURE."""
    all_teams = []
    for conf in NFL_STRUCTURE.values():
        for div in conf.values():
            all_teams.extend(div)
    return all_teams

# --- PICK MANAGEMENT (GAME-CENTRIC) ---
def load_user_picks(username):
    """Load picks by game_id from DB, fall back to local JSON."""
    picks_dict = {}
    
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT game_id, pick_result 
                FROM user_picks 
                WHERE username = %s
            """, (username,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            for game_id, pick_result in rows:
                picks_dict[game_id] = pick_result
            return picks_dict
        except Exception as e:
            pass

    # Fallback to local JSON
    local_file = f"picks_{username}.json"
    if os.path.exists(local_file):
        try:
            with open(local_file, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_pick(username, game_id, pick_result):
    """Save a single pick to DB and local backup."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_picks (username, game_id, pick_result, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (username, game_id)
                DO UPDATE SET pick_result = EXCLUDED.pick_result, updated_at = NOW()
            """, (username, game_id, pick_result))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Error saving pick: {e}")

    # Local backup
    try:
        picks_dict = st.session_state.get("user_predictions", {})
        with open(f"picks_{username}.json", "w") as f:
            f.write(json.dumps(picks_dict))
    except:
        pass

def get_opponent_from_gamestr(game_str):
    """Extract opponent from game string."""
    game_lower = game_str.lower()
    if "bye" in game_lower:
        return None
    if game_lower.startswith("at "):
        return game_str[3:].strip()
    else:
        return game_str.replace("vs ", "").replace("vs. ", "").strip()

def get_pick_for_game(game_id, home_team, away_team, team_perspective):
    """
    Retrieve pick for a game from a team's perspective.
    
    Args:
        game_id: Unique game identifier
        home_team: Home team name
        away_team: Away team name
        team_perspective: The team making the prediction
    
    Returns:
        "Win" or "Loss" from the team_perspective's POV
    """
    picks_dict = st.session_state.get("user_predictions", {})
    
    if game_id not in picks_dict:
        return "Win"  # Default

    pick_result = picks_dict[game_id]
    
    # Convert game-centric pick to team-centric view
    if team_perspective == home_team:
        return "Win" if pick_result == "home_win" else "Loss"
    else:
        return "Win" if pick_result == "away_win" else "Loss"

def set_pick_for_game(game_id, home_team, away_team, team_perspective, win_or_loss):
    """
    Set pick for a game (automatically syncs both teams).
    
    Args:
        game_id: Unique game identifier
        home_team: Home team name
        away_team: Away team name
        team_perspective: The team making the prediction
        win_or_loss: "Win" or "Loss" from the team_perspective's POV
    """
    # Convert team-centric to game-centric
    if team_perspective == home_team:
        pick_result = "home_win" if win_or_loss == "Win" else "away_win"
    else:
        pick_result = "away_win" if win_or_loss == "Win" else "home_win"
    
    # Update session state and DB (atomic)
    st.session_state.user_predictions[game_id] = pick_result
    save_user_pick(username, game_id, pick_result)

# --- SIDEBAR: USER PROFILE SELECTION ---
st.sidebar.title("NFL Navigation")
st.sidebar.subheader("👤 User Profile")
username = st.sidebar.text_input("Enter Your Name:", value="My Picks").strip()

if not username:
    username = "DefaultUser"

if "current_user" not in st.session_state or st.session_state.current_user != username:
    st.session_state.current_user = username
    st.session_state.user_predictions = load_user_picks(username)

if "user_predictions" not in st.session_state:
    st.session_state.user_predictions = load_user_picks(username)

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

        # Determine home/away
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

# --- MAIN UI ---
st.sidebar.markdown("---")
selected_conference = st.sidebar.selectbox("Select Conference:", list(NFL_STRUCTURE.keys()))
selected_division = st.sidebar.selectbox("Select Division:", list(NFL_STRUCTURE[selected_conference].keys()))
selected_team = st.sidebar.selectbox("Select Team:", NFL_STRUCTURE[selected_conference][selected_division])

st.title(f"2026 Schedule & Predictions: {selected_team}")
st.markdown(f"*{selected_conference} - {selected_division}* (Editing as: **{username}**)")
st.write("Select whether your team will **Win** or **Lose** each matchup below:")
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
    widget_key = f"radio_{game_id}"

    # Seed widget cache with current value
    if widget_key not in st.session_state:
        st.session_state[widget_key] = current_val

    result = st.radio(
        f"**Week {week_num}** {matchup_label} *({location})*",
        ["Win", "Loss"],
        key=widget_key,
        horizontal=True,
        on_change=lambda gid=game_id, ht=home_team, at=away_team, tp=selected_team, wk=widget_key: 
                    set_pick_for_game(gid, ht, at, tp, st.session_state[wk])
    )

    if result == "Win":
        wins += 1
    elif result == "Loss":
        losses += 1
    st.markdown("---")

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
