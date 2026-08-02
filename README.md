# NFL Predictor

Streamlit app for making NFL game predictions with automatic sync across teams.

## ✨ What's New (Refactored)

✅ **Game-Centric Storage**: Each game is stored once instead of duplicated per team
✅ **Automatic Sync**: Pick a result for one team, the opponent automatically reflects the opposite result
✅ **No More Sync Bugs**: Fixed widget state management and data consistency issues
✅ **PostgreSQL Integration**: Normalized schema with `games` and `user_picks` tables
✅ **Preserved UI**: Same interface, same playoff logic, same multi-user support

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up PostgreSQL

Create a PostgreSQL database and get your connection string:

```
postgresql://username:password@host:port/dbname
```

### 3. Configure Secrets

Create `.streamlit/secrets.toml`:

```toml
[postgres]
connection_string = "postgresql://username:password@host:port/dbname"
```

Or set environment variable for migration script:

```bash
export DATABASE_URL="postgresql://username:password@host:port/dbname"
```

### 4. Run Migration (One-Time, if you have existing data)

If you're upgrading from the old per-team storage format:

```bash
python scripts/migrate.py
```

This will:
- Create the new `games` table
- Create the new `user_picks` table  
- Seed all games from the NFL schedule
- Convert any existing picks to the new format

### 5. Run the App

```bash
streamlit run main.py
```

Visit `http://localhost:8501` in your browser.

## Usage

1. **Enter your name** in the sidebar
2. **Select conference → division → team**
3. **Pick wins/losses** for each game
4. **View your record** in the sidebar
5. **Upload weekly actual results** in the sidebar using `game_results.json` format
6. **Track season accuracy** under your username (`correct-incorrect (percentage)`)
7. **Check playoff standings** at the bottom

### 🎯 Key Behavior

- Picking **"Win"** for Buffalo Bills vs Miami Dolphins automatically sets Miami's pick to **"Loss"** for that same game
- Switching teams and coming back shows your picks for that team (automatically converted from game perspective)
- All picks are saved to PostgreSQL (with local JSON backup)
- Both teams always see the same game result—no more conflicts!

## 📊 Database Schema

### `games` Table

Stores the 2026 NFL schedule (immutable reference):

```sql
CREATE TABLE games (
    game_id TEXT PRIMARY KEY,
    week INT,
    home_team TEXT,
    away_team TEXT,
    game_datetime TIMESTAMP
);
```

**Example:**
```
game_id                                    | week | home_team      | away_team
--------------------------------------------|------|----------------|----------------
week1_BuffaloBills_MiamiDolphins_a1b2c3d4  | 1    | Buffalo Bills  | Miami Dolphins
```

### `user_picks` Table

Stores predictions per user per game:

```sql
CREATE TABLE user_picks (
    username TEXT,
    game_id TEXT,
    pick_result TEXT,  -- 'home_win' or 'away_win'
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    PRIMARY KEY (username, game_id)
);
```

**Example:**
```
username | game_id                                    | pick_result
---------|--------------------------------------------|-----------
brian    | week1_BuffaloBills_MiamiDolphins_a1b2c3d4  | home_win
```

This means: Brian picked Buffalo (home team) to win.

## 🔄 Migration from Old Format

The old format stored picks **per team**:

```python
# Old format (❌ caused sync issues)
{
  "Miami Dolphins_week_1": "Win",
  "Buffalo Bills_week_1": "Loss",
  "Miami Dolphins_week_2": "Loss",
  "Buffalo Bills_week_2": "Win",
  ...
}
```

This led to problems:
- Two separate entries for the same game
- Manually mirroring results (easy to forget)
- Widget state conflicts when switching teams

The new format stores picks **per game**:

```python
# New format (✅ automatic sync)
{
  "week1_BuffaloBills_MiamiDolphins_a1b2c3d4": "home_win",
  "week2_MiamiDolphins_BuffaloBills_b2c3d4e5": "away_win",
  ...
}
```

Now:
- One entry per game (source of truth)
- Converted automatically based on team perspective
- No conflicts, no manual mirroring

**To migrate existing data:**

```bash
export DATABASE_URL="postgresql://user:pass@host/dbname"
python scripts/migrate.py
```

## 📁 Files

- **main.py** - Main Streamlit app
- **nfl_data.py** - 2026 NFL schedule data
- **scripts/migrate.py** - One-time migration script for existing data
- **requirements.txt** - Python dependencies
- **README.md** - This file

## 🐛 Troubleshooting

### "Connection refused" error

```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Solution:**
- Make sure PostgreSQL is running
- Check your `DATABASE_URL` or `.streamlit/secrets.toml`
- Test with: `psql your_connection_string`

### "Table doesn't exist" error

```
ProgrammingError: relation "games" does not exist
```

**Solution:**
- The app auto-creates tables on first run
- If you get this after startup, check PostgreSQL logs
- Try dropping and re-creating the schema manually

### Picks not syncing between teams

**Solution:**
- Restart the app: `ctrl+c` then `streamlit run main.py`
- Verify the `games` table is seeded: `SELECT COUNT(*) FROM games;`
- Check that both teams' picks have the same `game_id`

### Migration failing

```
ERROR: Could not connect to database: ...
```

**Solution:**
- Set `DATABASE_URL`: `export DATABASE_URL="postgresql://..."`
- Make sure you're not running the cloud version (Streamlit Cloud can't execute migration scripts)
- Run locally first, then test with cloud

## 🚀 Future Improvements

- [ ] Week-by-week leaderboard comparing multiple users
- [ ] Season history/rollback
- [ ] Export picks to CSV
- [ ] Real NFL team stats API integration
- [ ] Interactive playoff bracket visualization
- [ ] Score predictions (not just W/L)

---

**Questions?** Check the GitHub issues or review the code comments in `main.py`.
