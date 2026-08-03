# How to Upload Game Results

## File Format
Upload a JSON file with game results in this format:

```json
{
  "week1_BuffaloBillsvsHoustonTexans": "Buffalo Bills",
  "week1_DetroitLionsvsSanFrancisco49ers": "San Francisco 49ers",
  "week1_KansasCityChiefsvsColoradoRockeys": "Kansas City Chiefs"
}
```

## Key Points
- **Key format:** `week{NUMBER}_{Team1vs Team2}` (no spaces in team names)
- **Value:** The team name that WON that game (must match exactly: "Buffalo Bills", not "Bills")
- Teams must be in alphabetical order in the key (alphabetically first team comes first)

## Example Week 1 Results
```json
{
  "week1_BuffaloBillsvsHoustonTexans": "Buffalo Bills",
  "week1_ChicagoBearsvsPittsburghSteelers": "Chicago Bears",
  "week1_DallasCowboysvsNewYorkGiants": "Dallas Cowboys",
  "week1_DetroitLionsvsMiamiDolphins": "Miami Dolphins",
  "week1_GreenBayPackersvsMinnesotaVikings": "Green Bay Packers"
}
```

## Steps to Upload
1. Create a `.json` file (e.g., `week1_results.json`)
2. Paste in your game results using the format above
3. Go to your app → "Upload Weekly Results" section
4. Click the Upload button and select your JSON file
5. Results will be saved automatically and synced to GitHub!

## To Remove Test Data
If you upload test data and want to reset:
1. Go to your GitHub repository
2. Find and delete the `game_results.json` file
3. Refresh your app
4. All data will be cleared!

## Finding Game IDs
Game IDs follow this pattern: `week{week_number}_{Team1vs Team2}` where teams are sorted alphabetically.

Example:
- Buffalo Bills vs Houston Texans = `week1_BuffaloBillsvsHoustonTexans` (Buffalo comes before Houston alphabetically)
- New York Giants vs Dallas Cowboys = `week1_DallasCowboysvsNewYorkGiants` (Dallas comes before New York alphabetically)
