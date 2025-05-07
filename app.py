import os

import httpx
from flask import Flask
from flask_cors import CORS
from typing import List, Dict, Any, Coroutine

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
CLAN_TAG = "%232LPOGLU2U"  # URL encoded clan tag

@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'

@app.route('/leaderboard/<clan_tag>')
def get_leaderboard(clan_tag: str) -> dict[str, Any] | None:
    """Get the current league information and process wars."""
    try:
        response = httpx.get(
            f"{BASE_URL}/clans/{clan_tag.replace('#', '%23')}/currentwar/leaguegroup",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        data = response.json()
        for clan in data['clans']:
            if clan['tag'] == clan_tag:
                break
        if data.get("state") in ["inWar", "ended"]:
            summ_clan = find_wars(clan_tag, data.get("rounds", []))
            rankings = consolidate_leaderboard(summ_clan)
            return {'clanTag': clan['tag'], 'clanName': clan['name'], 'clanLogo': clan['badgeUrls']['large'], 'leaderboard': rankings, 'state': 'SUCCESS'}
        else:
            return {'state': 'NON-CWL'}
    except Exception as e:
        print(f"Error getting league: {e}")



def get_war(clan_tag: str, war_tag: str) -> List[Dict[str, Any]] | None:
    """Get war information and process member data."""
    try:
        response = httpx.get(
            f"{BASE_URL}/clanwarleagues/wars/{war_tag.replace('#', '%23')}",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        data = response.json()

        if data["clan"]["tag"] == clan_tag:
            clan = data["clan"]["members"]
            opps = data["opponent"]["members"]
        elif data["opponent"]["tag"] == clan_tag:
            clan = data["opponent"]["members"]
            opps = data["clan"]["members"]
        else:
            return None

        summ_opps = [
            {"tag": opp["tag"], "th": opp["townhallLevel"], "pos": opp["mapPosition"]}
            for opp in opps
        ]

        summ_clan = []
        for member in clan:
            stars = 0
            perc = 0
            opp_tag = ""

            if member.get("attacks"):
                opp_tag = member["attacks"][0]["defenderTag"]
                opp = next((o for o in summ_opps if o["tag"] == opp_tag), None)

                if opp:
                    higher_th_opps = [o for o in summ_opps if o["pos"] < opp["pos"] and o["th"] < opp["th"]]
                    opp_th = min(higher_th_opps, key=lambda x: x["th"])["th"] if higher_th_opps else opp["th"]

                    stars = member["attacks"][0]["stars"]
                    if member["townhallLevel"] < opp_th and stars != 0:
                        stars += (opp_th - member["townhallLevel"])
                    elif member["townhallLevel"] > opp_th and stars < 3:
                        stars -= (member["townhallLevel"] - opp_th)
                    perc = member["attacks"][0]["destructionPercentage"]

            summ_clan.append({
                "tag": member["tag"],
                "name": member["name"],
                "th": member["townhallLevel"],
                "opp": opp_tag,
                "stars": stars,
                "percentage": perc
            })

        return summ_clan
    except Exception as e:
        print(f"Error getting war: {e}")



def find_wars(clan_tag: str, rounds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process all wars in the given rounds."""
    summ_clan = []
    for round_data in rounds:
        war_tags = round_data.get("warTags", [])
        for war_tag in war_tags:
            if war_tag != "#0":
                war_info = get_war(clan_tag, war_tag)
                if war_info:
                    summ_clan.extend(war_info)
                    break
    return summ_clan


def consolidate_leaderboard(summ_clan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Consolidate leaderboard entries and sort them."""
    rankings = []
    for sum_data in summ_clan:
        if not rankings:
            rankings.append({
                "tag": sum_data["tag"],
                "name": sum_data["name"],
                "stars": sum_data["stars"],
                "percentage": sum_data["percentage"],
                "th": sum_data["th"]
            })
        else:
            index = next((i for i, r in enumerate(rankings) if r["tag"] == sum_data["tag"]), -1)
            if index == -1:
                rankings.append({
                    "tag": sum_data["tag"],
                    "name": sum_data["name"],
                    "stars": sum_data["stars"],
                    "percentage": sum_data["percentage"],
                    "th": sum_data["th"]
                })
            else:
                rankings[index]["stars"] += sum_data["stars"]
                rankings[index]["percentage"] += sum_data["percentage"]
                if sum_data["th"] > rankings[index]["th"]:
                    rankings[index]["th"] = sum_data["th"]

    # Sort rankings
    rankings.sort(key=lambda x: (-x["stars"], -x["percentage"]))
    sorted_rankings = []
    counter = 0
    bonus_counter = 6
    for ranking in rankings:
        counter += 1
        sorted_rankings.append({
            'rank': counter,
            'tag': ranking["tag"],
            'name': ranking["name"],
            'stars': ranking["stars"],
            'percentage': ranking["percentage"],
            'th': ranking["th"],
            'bonus': True if counter <= bonus_counter else False
        })
    return sorted_rankings

def test_leaderboard():
    get_leaderboard(API_KEY)


if __name__ == '__main__':
    app.run()
