# Historical Football Database V1 — Research Audit

## Dataset counts
- TeamSeasons: 10
- PlayerSeasons: 185
- Team-level possession records: 10
- FIFA reference rating rows: 185
- Excluded roster records after verification pass: 5

- barcelona_2010_11 — FC Barcelona — 2010/11 — 20 players
- chelsea_2011_12 — Chelsea FC — 2011/12 — 21 players
- man_united_2007_08 — Manchester United — 2007/08 — 21 players
- real_madrid_2011_12 — Real Madrid — 2011/12 — 19 players
- bayern_2012_13 — Bayern München — 2012/13 — 19 players
- man_city_2011_12 — Manchester City — 2011/12 — 19 players
- dortmund_2012_13 — Borussia Dortmund — 2012/13 — 16 players
- inter_2009_10 — Inter Milan — 2009/10 — 17 players
- juventus_2011_12 — Juventus — 2011/12 — 15 players
- arsenal_2012_13 — Arsenal — 2012/13 — 18 players

## Exclusions
- `essien_rm_2011_12` from `real_madrid_2011_12`: Michael Essien joined Real Madrid for 2012/13, not 2011/12.
- `sommer_2012_13` from `bayern_2012_13`: Yann Sommer is not listed in Bayern Munich 2012/13 squad research and was at Borussia Mönchengladbach in that period.
- `given_2011_12` from `man_city_2011_12`: Shay Given transferred from Manchester City to Aston Villa in July 2011.
- `wright_phillips_2011_12` from `man_city_2011_12`: Shaun Wright-Phillips transferred from Manchester City to QPR in August 2011.
- `neto_juve_2011_12` from `juventus_2011_12`: Neto was not a Juventus 2011/12 squad member.

## Methodology
- Specialized engine abilities are computed from FIFA historical attributes without adding FIFA Overall a second time.
- FIFA Overall is preserved separately for future UI/Overall design.
- Discipline is neutral 0.50 where direct disciplinary evidence was not supplied; this is intentionally not treated as historical measurement.
- Possession is team-season-level and independent of player records.
- PES is not populated in V1 because no PES records were supplied in the input research.

## Verification note
Transfermarkt historical squad pages were used to catch obvious season-membership conflicts before inclusion. For example, Manchester City 2011/12 sources show Shaun Wright-Phillips left for QPR, while Bayern Munich 2012/13 sources list Neuer, Starke and Raeder as goalkeepers.