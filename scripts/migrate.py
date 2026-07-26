#!/usr/bin/env python3
"""
Migration script: Convert old per-team pick storage to new game-centric storage.

Run this ONCE before deploying the refactored main.py

Usage:
    python scripts/migrate.py
"""

import json
import os
import sys
from hashlib import md5
try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# Import NFL schedule
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nfl_data import NFL_SCHEDULE

# --- CONFIG ---
# Update these if needed (or load from .streamlit/secrets.toml)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set.")
    print("Set it with: export DATABASE_URL='postgresql://user:pass@host/dbname'")
    sys.exit(1)

def get_db_connection():
    """Connect to PostgreSQL."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

def generate_game_id(week_num, home_team, away_team):
    """Match main.py's game ID generation."""
    key = f"{week_num}_{home_team}_{away_team}".lower()
    hash_suffix = md5(key.encode()).hexdigest()[:8]
    return f"week{week_num}_{home_team.replace(' ', '')}_{away_team.replace(' ', '')}_{hash_suffix}"

def get_opponent_from_gamestr(game_str):
    """Extract opponent from game string."""
    game_lower = game_str.lower()
    if "bye" in game_lower:
        return None
    if game_lower.startswith("at "):
        return game_str[3:].strip()
    else:
        return game_str.replace("vs ", "").replace("vs. ", "").strip()

def get_all_teams():
    """Get all NFL teams."""
    teams = []
    # Hard-coded for consistency with main.py
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
    for conf in NFL_STRUCTURE.values():
        for div in conf.values():
            teams.extend(div)
    return teams

def init_db(conn):
    """Ensure new schema exists."""
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                week INT,
                home_team TEXT,
                away_team TEXT,
                game_datetime TIMESTAMP DEFAULT NOW()
            )
        """)
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
        print("✓ Schema initialized")
    except Exception as e:
        print(f"ERROR initializing schema: {e}")
        sys.exit(1)
    finally:
        cur.close()

def seed_games(conn):
    """Populate games table from NFL_SCHEDULE."""
    cur = conn.cursor()
    seeded_game_ids = set()
    count = 0
    
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

                if game_str.lower().startswith("at "):
                    home_team = opponent
                    away_team = team_name
                else:
                    home_team = team_name
                    away_team = opponent

                game_id = generate_game_id(week_num, home_team, away_team)

                if game_id in seeded_game_ids:
                    continue
                seeded_game_ids.add(game_id)

                cur.execute("""
                    INSERT INTO games (game_id, week, home_team, away_team)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (game_id) DO NOTHING
                """, (game_id, week_num, home_team, away_team))
                count += 1

        conn.commit()
        print(f"✓ Seeded {count} games")
    except Exception as e:
        print(f"ERROR seeding games: {e}")
        sys.exit(1)
    finally:
        cur.close()

def migrate_picks(conn):
    """Convert old per-team picks to game-centric picks."""
    cur = conn.cursor()
    migrated = 0
    
    try:
        # Get all users from old user_picks table (if it exists)
        try:
            cur.execute("SELECT DISTINCT username FROM user_picks WHERE picks_data IS NOT NULL")
            users = [row[0] for row in cur.fetchall()]
        except:
            print("  (No existing old-format user_picks data found, skipping migration)")
            return 0
        
        for username in users:
            # Get old picks for this user
            cur.execute("SELECT picks_data FROM user_picks WHERE username = %s LIMIT 1", (username,))
            row = cur.fetchone()
            if not row or not row[0]:
                continue
            
            try:
                old_picks = json.loads(row[0])
            except:
                print(f"  WARNING: Could not parse picks for {username}, skipping")
                continue
            
            # Convert each old pick
            for team_name in get_all_teams():
                schedule = NFL_SCHEDULE.get(team_name, [])
                
                for week_num, game_info in enumerate(schedule, start=1):
                    game_str = str(game_info)
                    if "bye" in game_str.lower():
                        continue
                    
                    opponent = get_opponent_from_gamestr(game_str)
                    if not opponent:
                        continue
                    
                    old_key = f"{team_name}_week_{week_num}"
                    
                    if old_key in old_picks:
                        # Determine home/away
                        if game_str.lower().startswith("at "):
                            home_team = opponent
                            away_team = team_name
                        else:
                            home_team = team_name
                            away_team = opponent
                        
                        game_id = generate_game_id(week_num, home_team, away_team)
                        old_pick = old_picks[old_key]
                        
                        # Convert to game-centric
                        if team_name == home_team:
                            pick_result = "home_win" if old_pick == "Win" else "away_win"
                        else:
                            pick_result = "away_win" if old_pick == "Win" else "home_win"
                        
                        # Insert into new table (only if game_id is new to this username)
                        cur.execute("""
                            INSERT INTO user_picks (username, game_id, pick_result)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (username, game_id) DO NOTHING
                        """, (username, game_id, pick_result))
                        migrated += 1
        
        conn.commit()
        print(f"✓ Migrated {migrated} picks from {len(users)} users")
        return migrated
    except Exception as e:
        print(f"ERROR during migration: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()

def main():
    print("\n=== NFL Predictor: Migration Script ===")
    print("\nThis will convert your old per-team pick storage to game-centric storage.")
    print("Backup your database before running this!\n")
    
    conn = get_db_connection()
    db_name = DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL
    print(f"Connected to database: {db_name}")
    
    init_db(conn)
    seed_games(conn)
    migrate_picks(conn)
    
    conn.close()
    print("\n✓ Migration complete!")
    print("\nNext steps:")
    print("  1. Test the app locally: streamlit run main.py")
    print("  2. Switch teams to verify picks are synced")
    print("  3. Deploy to production")

if __name__ == "__main__":
    main()
