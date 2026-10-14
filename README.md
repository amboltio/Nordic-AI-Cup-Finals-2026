# Nordic AI Cup Finals 2026

Welcome to the **Nordic AI Cup Finals**, hosted by [Ambolt AI](https://ambolt.io/).
The winners of the national rounds of the [Nordic AI Cup 2026](https://github.com/amboltio/Nordic-AI-Cup-2026)
meet here to compete for the Nordic title, with a partner organization in each
participating country.

| Country | Partner |
| --- | --- |
| 🇸🇪 Sweden | [Wallenberg AI, Autonomous Systems and Software Program (WASP)](https://wasp-sweden.org/) |
| 🇩🇰 Denmark | [Danish Data Science Academy (DDSA)](https://ddsa.dk/) · [Pioneer Centre for Artificial Intelligence](https://www.aicentre.dk/) |
| 🇫🇮 Finland | [Finnish Center for Artificial Intelligence (FCAI)](https://fcai.fi/) |
| 🇳🇴 Norway | [Norwegian Artificial Intelligence Research Consortium (NORA)](https://www.nora.ai/) |
| 🇮🇸 Iceland | [Center for Analysis and Design of Intelligent Agents (CADIA)](https://cadia.is/) |

In this repository you will find everything you need to compete in the finals.
Please read this page in full before you start on the case, and then read the
whole case description.

## The case

The finals have a single case, and it is a reinforcement learning one:

**[Robot Robbers](robot-robbers/)**: steer five robbers through a city of
obstacles. Grab the cash bags, bring them to the drop spots, and stay out of
reach of the scrooges. Your agent is called once per game tick and answers
with a move for each robot.

![Robot Robbers](images/robot_robbers.png)

Clone this repository to get the template, the game and the local test tools:

```
git clone https://github.com/amboltio/Nordic-AI-Cup-Finals-2026.git
```

Like the main competition, the template is built on
[FastAPI](https://fastapi.tiangolo.com/). You serve an endpoint, and the
evaluation service calls it.

## Who can compete

The finals are open to the winners from the national competitions.

You compete as the same team, with the same API key, as in the main
competition. Only finalist teams can queue attempts.

## When

The finals are planned to run from
**14 October 2026, 09:00** to **15 October 2026, 09:00** Reykjavik time
(UTC+0). The finals page shows the exact times in your own time zone.

Attempts can only be queued while the finals are open.

## Submission

Everything happens on the finals page,
[cases.nordicaicup.com/finals](https://cases.nordicaicup.com/finals). Open the Robot
Robbers challenge there and enter your API key and the URL of your endpoint.

1. **Check team status** to confirm your API key identifies your team.
2. **Test the connection.** It sends a single request to your endpoint and
   checks the shape of your answer.
3. **Queue a validation** as often as you like. Each validation attempt plays a full
   game on a new random map, and your best validation score appears on the
   finals leaderboard. Only one attempt runs at a time per team.
4. **Run final evaluation** once. The evaluation attempt plays one game on a fixed,
   unpublished map. **You get one completed evaluation attempt**, and it
   decides your placement.

The evaluation map is different from every validation map, so do not tune your
agent to the maps you happen to have seen.

## Results and the award ceremony

The validation leaderboard is live throughout the finals, so you can see how
you compare. **Evaluation scores are not.** Your evaluation score is hidden
from everyone, you included, until it is revealed at the award ceremony,
together with replays of the evaluation games. The results are made public on
the finals page two hours after the ceremony starts.

The team with the highest evaluation score wins. If two teams have the same
evaluation score, the team whose evaluation attempt finished first ranks
higher.

The top teams are asked to hand in their code and agent for verification by
the Scientific Jury, as in the main competition. Send it to
[magnus@ambolt.io](mailto:magnus@ambolt.io) by the time the finals close.

## Getting started

Start with the [Robot Robbers README](robot-robbers/README.md). The quickstart
there gets you from a clone to a served baseline agent and a local score in a
few commands. The request and response formats are in
[`robot-robbers/dtos.py`](robot-robbers/dtos.py), and they have to match
exactly for the evaluation service to work.

### Hosting your endpoint

The evaluation service has to reach your endpoint over the internet, and it
calls it once per game tick, so a server with a short round trip to the
evaluation service matters more here than in the main competition. A virtual
machine from a cloud provider is the simplest option. With
[Azure for Students](https://azure.microsoft.com/en-us/free/students/) you get
free credits for one:

* [Creating a Linux virtual machine](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/quick-create-portal)
* [Creating an inbound security rule](https://learn.microsoft.com/en-us/azure/virtual-network/tutorial-filter-network-traffic) (so the evaluation service can reach your API)

You can also serve from your own machine, but that needs a public IP and an
open port.

**Get your server up and validating early.** If something is wrong with your
deployment, you want to find out on the first morning, not an hour before the
finals close.

## Frequently Asked Questions

**Q: Can I use a pretrained model or an existing RL library?**

**A:** Yes. If you can find something that fits, use it, just like you would
when solving a problem for a company.

**Q: Can I train against the game?**

**A:** Yes, and you should. `robot-robbers/game/environment.py` is the same
game the evaluation service plays, and you can run it as fast as your machine
allows. **We do not provide servers for training.**

**Q: Are we allowed to use OpenAI / Google Cloud / AWS / Azure APIs?**

**A:** Not during inference. You are welcome to use cloud services to build
and train your agent, but when the evaluation service calls your endpoint,
your agent must run on its own without calling out to other APIs. Given the
time budget, it would be too slow anyway.

**Q: Can my agent keep state between ticks?**

**A:** Yes. The service sends one game per attempt, one tick at a time, in
order. A new game starts when `game_ticks` is `0`.
