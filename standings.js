import { NFL_SOS } from './nfl_data.py';

async function loadStandings() {
  try {
    const response = await fetch('/api/standings');
    const standings = await response.json();
    
    const tbody = document.querySelector('.standings-table tbody');
    
    tbody.innerHTML = standings.map(team => {
      const sosData = NFL_SOS[team.name];
      
      return `
        <tr>
          <td class="rank">${sosData.rank}</td>
          <td class="team">${team.name}</td>
          <td class="record">${team.wins}-${team.losses}</td>
          <td class="sos">${sosData.rank}</td>
          <td class="opp-win-pct">${sosData.opp_win_pct.toFixed(3)}</td>
        </tr>
      `;
    }).join('');
  } catch (error) {
    console.error('Error loading standings:', error);
  }
}

document.addEventListener('DOMContentLoaded', loadStandings);
