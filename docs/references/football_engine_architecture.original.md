# Football Match Simulation Engine — Architecture Checkpoint

> **Status:** Architecture locked through Section N  
> **Current next step:** Section J/K — Player Performance + Match Events

---

## 0. Project Goal

هدف پروژه ساخت یک **Football Match Simulation / Prediction Engine** است که بتواند تیم‌های تاریخی را به‌صورت snapshot بازسازی کند و مسابقه‌های واقعی و فرضی را به‌شکل احتمالاتی و قابل‌توضیح شبیه‌سازی کند.

ویژگی‌های کلیدی معماری:

- ماژولار و قابل دیباگ
- قابل calibration با داده تاریخی
- جلوگیری از double-counting
- جداسازی Prediction / Probability / Simulation
- پشتیبانی از TeamSeasonهای تاریخی
- Sequential temporal simulation
- تولید upset از خود توزیع احتمال، نه با mechanic مصنوعی
- قابلیت توسعه از V1 به V2/V3 بدون شکستن هسته مدل

---

# 1. Core Concept

اصل اصلی مدل این است:

```text
Player Season
    ↓
Team Dimensions + Team Identity
    ↓
Formation
    ↓
Tactical State
    ↓
Matchup Engine
    ↓
M + T
    ↓
λ_base
    ↓
Home Advantage
    ↓
Form (Tournament only)
    ↓
λ_final
    ↓
Probability Model (Dixon-Coles / Poisson)
    ↓
Sampling
    ↓
Match Event / Goal
    ↓
State Update
    ↓
Next Segment
```

---

# 2. سه لایه اصلی مدل

## 2.1 Prediction Layer

این لایه مشخص می‌کند قبل از sampling، تیم‌ها چه نرخ گلی دارند.

```text
Team Model → Matchup → M,T → λ
```

خروجی اصلی:

\[
\lambda_{home},\lambda_{away}
\]

---

## 2.2 Probability Layer

این لایه λ را به یک توزیع احتمال تبدیل می‌کند.

```text
λ → Poisson / Dixon-Coles → P(scoreline)
```

خروجی:

\[
P(X=x,Y=y)
\]

---

## 2.3 Simulation Layer

این لایه از توزیع یک outcome واقعی sample می‌کند.

```text
P(scoreline)
      ↓
Random Sample
      ↓
Observed Goal / Event
      ↓
State Update
```

اصل قفل‌شده:

\[
\boxed{Randomness \rightarrow Sampling}
\]

نه:

\[
Randomness \rightarrow \lambda
\]

و:

\[
\boxed{Goal\ Outcome \rightarrow Future\ State}
\]

نه اینکه outcome بتواند λ همان segment را retrospective تغییر دهد.

---

# 3. Team / Player Foundations

## 3.1 PlayerSeason

هر بازیکن به‌صورت season-specific snapshot تعریف می‌شود.

نمونه:

```text
messi_2010_11
messi_2018_19
```

در نتیجه، یک بازیکن مشترک در فصل‌های مختلف می‌تواند attributeهای متفاوت داشته باشد.

---

# 4. Team Dimensions

Team از PlayerSeasonها به چند dimension اصلی می‌رسد.

```text
Attack
Creation
Defense
Goalkeeping
```

این dimensionها با Role Weight و Formation context تعدیل می‌شوند.

اصل مهم:

> Team strength نباید به یک score عمومی 0–100 تبدیل شود که مستقیم λ را تعیین کند.

در عوض، dimensionها وارد Matchup Engine می‌شوند.

---

# 5. Formation Engine

Formation فقط یک نام مثل `4-3-3` نیست؛ یک ساختار است.

Formation Engine بر پایه:

- Position Pool
- Context Rules
- Structural Features
- Type A / B / C

کار می‌کند.

خروجی Formation Engine روی Role Weightها و structural context اثر می‌گذارد.

در معماری فعلی، همان TeamSeason می‌تواند بسته به formation انتخابی، Team Dimensions متفاوتی پیدا کند.

---

# 6. State Machine + Temporal Simulation

بازی به segmentهای زمانی تقسیم می‌شود.

V1 segmentهای پایه:

```text
S1 = 0–30
S2 = 30–60
S3 = 60–75
S4 = 75–90+
```

در هر segment:

```text
State
  ↓
Tactical Profile
  ↓
Matchup
  ↓
λ
  ↓
Sample
  ↓
State Update
```

### Splitting Events

رویدادهایی که می‌توانند segment را بشکنند:

- Goal
- Red Card

رویدادهایی که در V1 الزاماً segment را نمی‌شکنند:

- Yellow Card
- Ordinary Substitution
- Missed Chance
- Save

نکته مهم:

> زمان دقیق goal داخل segment تا وقتی Event Generator فعال نشود الزاماً معلوم نیست؛ در V1 می‌توان state را در مرز segmentها update کرد، یا بعداً segment را در زمان event شکست.

---

# 7. Tactical Profile

TacticalProfile نسخه runtime تاکتیک تیم است و می‌تواند از Team Identity پایه با State Adjustment ساخته شود.

متغیرهای مهمی که در Matchup Engine استفاده می‌شوند، از جمله:

- `press_final`
- `line_final`
- `width_final`
- `build_up_control_score`
- `defensive_cover_feature`
- `attack_pace_factor`

---

# 8. Matchup Engine

## 8.1 Inputs

```text
Team A:
  Dimensions
  Formation
  Identity
  TacticalProfile

Team B:
  Dimensions
  Formation
  Identity
  TacticalProfile
```

## 8.2 Outputs

```text
M_A→B^Attack
M_B→A^Attack
T_A→B
T_B→A
```

اصل کلیدی:

> Matchup Engine نباید یک Generic Team Strength Score جدید بسازد.

مسیر درست:

```text
Dimensions
    ↓
Relative Strength
    ↓
Matchup Interactions
    ↓
Effective Attack / Creation / Defense
    ↓
λ
```

---

# 9. Base Relative Strength

برای A در برابر B:

\[
BaseRelativeStrength(A\to B)
=
\frac{Attack_A/GlobalAvgAttack}
{Defense_B/GlobalAvgDefense}
\times GK_Factor(B)
\]

و:

\[
GK_Factor(B)=1-k_{gk}
\frac{GK_B-GlobalAvgGK}{GlobalAvgGK}
\]

نکته:

- Global averages فقط calibration anchors هستند.
- مقادیر اولیه نمونه در مثال قبلی 78 بودند.

---

# 10. Creation Factor

Creation از نسبت creation تیم به global average شروع می‌شود و possession فقط از مسیر realization وارد آن می‌شود.

### Possession Share

\[
PossessionShare(A)=sigmoid\left(
 k_{poss\_calc}\left[
 (A.possession\_tendency-B.possession\_tendency)
 +(A.build\_up\_control\_score-B.press\_final)
 \right]
\right)
\]

### Creation Realization

\[
CreationRealization(A)=0.6+0.4\,PossessionShare(A)
\]

### Creation Factor

\[
CreationFactor(A)=
\left(0.7+0.3\frac{Creation_A}{GlobalAvgCreation}\right)
\times CreationRealization(A)
\]

اصل مهم:

> Possession مسیر مستقیم مستقل به λ ندارد؛ فقط از طریق CreationRealization وارد CreationFactor می‌شود.

---

# 11. Single-Path Dependency Rules

هر football phenomenon فقط یک مسیر اصلی به λ دارد.

| Phenomenon | Exclusive Path |
|---|---|
| Press quality | `M` via `I_press` |
| Build-up control | `M` via `PressDisruption` |
| High line | `T` via `SpaceBehindDefense` |
| Width mismatch | `M` via `I_width` |
| Tempo | `M` only |
| Transition tendency | `T` exclusively |
| Possession | only via `CreationRealization` |

این جدول برای جلوگیری از double-counting یکی از مهم‌ترین قفل‌های معماری است.

---

# 12. Matchup Interactions

## 12.1 Press

\[
I_{press}(A\to B)=1-k_p\,PressDisruption(B\to A)
\]

برای calibration تمیزتر بهتر است دو مفهوم از هم تفکیک شوند:

\[
PressDisruption^{M}
\]

برای disruption مستقیم حمله، و:

\[
PressTransitionOpportunity^{T}
\]

برای opportunity حاصل از turnover / transition.

این تفکیک numerical architecture را لزوماً تغییر نمی‌دهد، ولی dependency tracing و calibration را شفاف‌تر می‌کند.

## 12.2 Width

\[
I_{width}(A\to B)=1+k_w\,WidthMismatch(A,B)
\]

## 12.3 Tempo

\[
I_{tempo}(A\to B)=1+k_{te}A.tempo_{final}
\]

Tempo فقط در M قرار دارد و turnover-risk جداگانه به T اضافه نمی‌کند.

---

# 13. Adjusted Base + M

\[
AdjustedBase(A\to B)=
BaseRelativeStrength(A\to B)\times CreationFactor(A)
\]

سپس:

\[
\boxed{
M_{A\to B}^{Attack}
=
AdjustedBase(A\to B)
\times I_{press}(A\to B)
\times I_{width}(A\to B)
\times I_{tempo}(A\to B)
}
\]

---

# 14. Transition Threat T

تعریف space پشت خط دفاع:

\[
SpaceBehindDefense(B)=
B.line_{final}(1-B.defensive\_cover\_feature)
\]

و:

\[
T_{A\to B}
=
A.transition\_tendency_{final}
\times A.attack\_pace\_factor
\times SpaceBehindDefense(B)
+
PressTransitionOpportunity^{T}_{B\to A}
\times A.transition\_tendency_{final}
\times k_{t2}
\]

در نسخه قبلی notation ساده‌تر از `PressDisruption` استفاده می‌شد؛ separation بالا برای نسخه اجرایی توصیه شده است.

---

# 15. Example — Team B → Team A

نمونه historical matchup قبلی:

### Team A

```text
Attack = 85
Creation = 95
Defense = 80
GK = 85

possession = 0.90
press = 0.80
transition = 0.30
tempo = 0.65
risk = 0.55

press_final = 0.80
line_final = 0.85
width_final = 0.55
build_up_control_score = 0.92
defensive_cover_feature = 0.40
```

### Team B

```text
Attack = 88
Creation = 70
Defense = 82
GK = 80

possession = 0.35
press = 0.40
transition = 0.90
tempo = 0.55
risk = 0.60

press_final = 0.40
line_final = 0.35
width_final = 0.45
build_up_control_score = 0.55
defensive_cover_feature = 0.75
attack_pace_factor = 0.95
```

Global averages:

```text
78 / 78 / 78 / 78
```

نتیجه تقریبی:

\[
BaseRelativeStrength(B\to A)\approx1.089
\]

\[
PossessionShare(B)=sigmoid(-1.2)\approx0.231
\]

\[
CreationRealization(B)\approx0.692
\]

\[
CreationFactor(B)\approx0.671
\]

\[
AdjustedBase(B\to A)\approx0.731
\]

\[
I_{press}\approx0.856
\]

\[
I_{tempo}=1.0825
\]

\[
M_{B\to A}^{Attack}\approx0.677
\]

و:

\[
SpaceBehindDefense(A)=0.85(1-0.40)=0.51
\]

\[
T_{B\to A}\approx0.598
\]

نتیجه qualitative:

> B در حمله منظم ضعیف‌تر است ولی transition threat بالایی دارد.

این تفکیک دقیقاً هدف M و T است.

---

# 16. λ Architecture

## 16.1 Baseline

\[
BASELINE\_GOALS\_PER\_MATCH=1.35
\]

این مقدار فقط **calibration anchor** است و constant نهایی empirical محسوب نمی‌شود.

## 16.2 Base λ

\[
\boxed{
\lambda_{base}(A\to B)
=
1.35M_{A\to B}^{Attack}
+
0.55T_{A\to B}
}
\]

که در آن:

\[
TRANSITION\_GOAL\_WEIGHT=0.55
\]

یک prior اولیه است.

مثال B→A:

\[
\lambda_{base}
=1.35(0.677)+0.55(0.598)
\approx1.243
\]

---

# 17. Home Advantage

Home Advantage در Matchup Engine وارد نمی‌شود.

ساختار:

```text
Matchup Engine
      ↓
λ_base
      ↓
Home Advantage
```

prior اولیه:

\[
\lambda_{home}^*=1.10\lambda_{base,home}
\]

\[
\lambda_{away}^*=0.95\lambda_{base,away}
\]

این مقادیر universal truth نیستند و باید در calibration fit شوند.

---

# 18. Form vs Randomness

## 18.1 Form

Form یک signal اطلاعاتی **known-before-the-match** است و باید λ را به شکل سیستماتیک جابه‌جا کند.

\[
FormFactor(team)=clamp(1+k_{form}\times RecentPerformanceIndex(team),0.85,1.15)
\]

که:

\[
RecentPerformanceIndex\in[-1,+1]
\]

prior اولیه:

\[
k_{form}=0.15
\]

### Historical Sandbox Rule

برای یک matchup تاریخی آزاد و مستقل:

```text
FormFactor = 1.0
```

چون تیم تاریخی خارج از tournament جاری، form in-game ندارد.

اگر بازی بخشی از یک Season/Tournament شبیه‌سازی‌شده باشد:

```text
FormFactor ← results of previous simulated matches
```

بنابراین Form بخشی از **in-game state** است، نه attribute ثابت Team Identity.

---

# 19. Final λ

برای تیم A:

\[
\lambda_{base}(A\to B)
=
BASELINE\times M_{A\to B}
+
TRANSITION\_WEIGHT\times T_{A\to B}
\]

سپس contextual modifiers:

\[
\lambda_{contextual}(A\to B)
=
\lambda_{base}(A\to B)\times H_A
\times FormFactor(A)
\]

و:

\[
\boxed{
\lambda_{final}(A\to B)=\lambda_{contextual}(A\to B)
}
\]

Randomness اینجا ضریب جداگانه ندارد.

---

# 20. Randomness

## V1

منبع تصادف اصلی:

> Sampling از Dixon-Coles / Poisson

یعنی:

\[
(X,Y)\sim P_{model}(X,Y)
\]

و upset از همین فرآیند emerge می‌شود.

## V2+

در صورت مشاهده under-dispersion نسبت به داده واقعی، می‌توان یک layer نویز کوچک روی λ اضافه کرد، مثلاً:

\[
\lambda_{noisy}=\lambda_{final}(1+\epsilon)
\]

با:

\[
\epsilon\sim Normal(0,\sigma_{small})
\]

پیشنهاد اولیه:

```text
σ_small ≈ 0.05–0.08
```

اما این در V1 عمداً غیرفعال است.

---

# 21. Dixon-Coles Model

## 21.1 Independent Poisson

اگر گل‌های دو تیم مستقل باشند:

\[
P(X=x)=\frac{\lambda_H^x e^{-\lambda_H}}{x!}
\]

\[
P(Y=y)=\frac{\lambda_A^y e^{-\lambda_A}}{y!}
\]

و:

\[
P(X=x,Y=y)=P(X=x)P(Y=y)
\]

---

# 22. Dixon-Coles τ Correction

\[
P_{DC}(X=x,Y=y)
=
\tau(x,y,\lambda_H,\lambda_A,\rho)
P_{Poisson}(X=x)P_{Poisson}(Y=y)
\]

برای حالت‌های کم‌گل:

\[
\tau(0,0)=1-\lambda_H\lambda_A\rho
\]

\[
\tau(0,1)=1+\lambda_H\rho
\]

\[
\tau(1,0)=1+\lambda_A\rho
\]

\[
\tau(1,1)=1-\rho
\]

و برای:

\[
x\ge2 \quad \text{یا}\quad y\ge2
\]

داریم:

\[
\tau(x,y)=1
\]

پارامتر \(\rho\) یک correction parameter برای low-score dependence است.

prior اولیه پروژه:

\[
\rho=-0.13
\]

که باید calibration شود.

---

# 23. Normalization

پس از ساخت ماتریس محدود scorelineها:

\[
P_{DC}(x,y)=\tau(x,y)P_H(x)P_A(y)
\]

برای grid مثلاً 0 تا 8:

\[
P_{norm}(x,y)=
\frac{P_{DC}(x,y)}
{\sum_{i=0}^{K}\sum_{j=0}^{K}P_{DC}(i,j)}
\]

و:

\[
\sum_{x=0}^{K}\sum_{y=0}^{K}P_{norm}(x,y)=1
\]

---

# 24. Worked DC Example

مثال فرضی:

```text
Barcelona λ_home = 1.95
Bayern    λ_away = 1.15
ρ = -0.13
```

Independent Poisson values:

```text
P_H(0) ≈ 0.1423
P_H(1) ≈ 0.2775
P_A(0) ≈ 0.3166
P_A(1) ≈ 0.3641
```

نتایج کلیدی تقریباً:

```text
P_indep(0,0) ≈ 0.04504
P_indep(1,0) ≈ 0.08785
P_indep(0,1) ≈ 0.05182
P_indep(1,1) ≈ 0.10104
```

τها:

```text
τ(0,0) ≈ 1.2914
τ(1,0) ≈ 0.8505
τ(0,1) ≈ 0.7465
τ(1,1) = 1.13
```

پس تقریباً:

```text
P_DC(0,0) ≈ 0.05816
P_DC(1,0) ≈ 0.07472
P_DC(0,1) ≈ 0.03868
P_DC(1,1) ≈ 0.11418
```

این نشان می‌دهد DC probability mass را در low-score outcomes به شکل کنترل‌شده جابه‌جا می‌کند.

---

# 25. Win / Draw / Loss

بعد از ساخت ماتریس نهایی:

\[
P(HomeWin)=\sum_{x>y}P(x,y)
\]

\[
P(Draw)=\sum_{x=y}P(x,y)
\]

\[
P(AwayWin)=\sum_{x<y}P(x,y)
\]

Upset از همین جمع probabilityها حاصل می‌شود؛ mechanic جداگانه‌ای وجود ندارد.

---

# 26. Sampling

## 26.1 Duration Scaling

اگر λ به‌صورت 90-minute equivalent باشد و segment مدت \(d\) دقیقه داشته باشد:

\[
\lambda_H^{(d)}=\lambda_H^{90}\frac{d}{90}
\]

\[
\lambda_A^{(d)}=\lambda_A^{90}\frac{d}{90}
\]

---

## 26.2 DC Sampling برای Segmentهای V1

قانون فعلی:

```text
duration >= 15 min
    ↓
Dixon-Coles

duration < 15 min
    ↓
Independent Poisson
```

> Threshold 15 دقیقه یک **V1 design choice** است، نه یک قانون بنیادی ریاضی.

---

## 26.3 CDF Sampling

برای DC:

1. ماتریس \(P(x,y)\) ساخته می‌شود.
2. scorelineها flatten می‌شوند.
3. cumulative probability یا CDF ساخته می‌شود.
4. یک:

\[
u\sim Uniform(0,1)
\]

sample می‌شود.

5. اولین scoreline که:

\[
CDF\ge u
\]

باشد انتخاب می‌شود.

مثلاً:

```text
u = 0.31
```

و اگر:

```text
CDF(1-1) = 0.286
CDF(2-0) = 0.369
```

باشد:

```text
Sample = 2-0
```

---

# 27. Independent Poisson Sampling برای Segmentهای کوتاه

برای duration کمتر از threshold:

\[
X\sim Poisson(\lambda_H^{(d)})
\]

\[
Y\sim Poisson(\lambda_A^{(d)})
\]

و هرکدام مستقیماً sample می‌شوند.

تفاوت DC و Poisson در **probability construction** است؛ هر دو در نهایت random sample تولید می‌کنند.

---

# 28. Sampling Pseudocode

```text
function sample_dixon_coles(lambda_home_90,
                            lambda_away_90,
                            duration):

    lambda_home = lambda_home_90 * duration / 90
    lambda_away = lambda_away_90 * duration / 90

    matrix = []

    for x in 0..K:
        for y in 0..K:

            p_home = poisson_pmf(x, lambda_home)
            p_away = poisson_pmf(y, lambda_away)

            p = p_home * p_away

            tau = dc_tau(x, y,
                         lambda_home,
                         lambda_away,
                         rho)

            p = p * tau

            matrix.append((x, y, p))

    normalize(matrix)

    u = random_uniform(0, 1)
    cumulative = 0

    for (x, y, p) in matrix:
        cumulative += p
        if u <= cumulative:
            return (x, y)
```

---

# 29. Historical Team — Hybrid Model

TeamSeason تاریخی با مدل hybrid ساخته می‌شود، نه کاملاً derived و نه کاملاً manual.

## 29.1 چرا فقط Player-derived کافی نیست؟

چون سبک یک تیم تاریخی فقط مجموع attributeهای بازیکنان نیست؛ سیستم تاکتیکی، coaching philosophy و context تیم نیز مهم است.

## 29.2 چرا فقط manual کافی نیست؟

چون مقیاس‌پذیر نیست و consistency از بین می‌رود.

---

# 30. Hybrid Team Model

```text
PlayerSeason attributes
        ↓
Derived Team Dimensions
Derived Team Identity
        ↓
Historical Prior
        ↓
Final TeamSeason
```

فرمول اصلی:

\[
final=clamp(
\alpha\times derived
+(1-\alpha)\times historical\_prior,
0,1
)
\]

برای ویژگی‌هایی که historical prior ندارند، derived به‌تنهایی استفاده می‌شود.

---

# 31. Historical Tiering

## Tier 1 — Iconic Teams

تقریباً 30–50 تیم مهم تاریخی.

نمونه‌ها:

```text
Barcelona 2010/11
Milan 1988/89
Real Madrid 2016/17
```

ویژگی‌ها:

- historical prior کامل
- identity prior برای چند/تمام پارامترهای مهم
- optional dimension adjustment
- alpha پیشنهادی حدود 0.5–0.6

## Tier 2 — Notable Teams

Historical prior جزئی برای چند پارامتر کلیدی.

alpha حدود 0.75–0.85.

## Tier 3 — Generic Historical Teams

بدون historical prior.

\[
\alpha=1.0
\]

کاملاً derived.

---

# 32. Barcelona 2010/11 vs Later Barcelona

تفاوت تیم‌های یک باشگاه در فصل‌های مختلف از سه منبع می‌آید:

1. PlayerSeasonهای متفاوت
2. Squad متفاوت
3. Historical Prior متفاوت

در نتیجه:

```text
Barcelona 2010/11
Barcelona 2014/15
Barcelona 2018/19
```

می‌توانند TeamSeasonهای متفاوتی باشند حتی با وجود بازیکنان مشترک.

---

# 33. TeamSeason Entity

نمونه schema:

```text
TeamSeason {
  id: "barcelona_2010_11"
  club: "Barcelona"
  season: "2010/11"

  roster: [PlayerSeason references]

  historical_prior: {
      tier: 1,
      alpha: 0.55,
      identity_priors: {
          possession_tendency: 0.95,
          press_tendency: 0.90,
          transition_tendency: 0.25,
          tempo: 0.70,
          risk_tolerance: 0.50,
          compactness: 0.75
      },
      dimension_adjustment: {
          creation: +0.03
      }
  }

  computed_dimensions: {
      attack,
      creation,
      defense,
      goalkeeping
  }

  computed_identity: {
      possession,
      press,
      transition,
      tempo,
      risk,
      compactness
  }
}
```

`computed_dimensions` و `computed_identity` در runtime محاسبه می‌شوند؛ چون formation انتخابی می‌تواند آن‌ها را تغییر دهد.

---

# 34. TeamSeason Runtime Pipeline

```text
1. Select TeamSeason
2. Select Formation
3. Formation Engine
4. Compute Team Dimensions
5. Compute Team Identity
6. Apply Historical Prior
7. Generate final game-specific TeamSeason state
```

---

# 35. Calibration Methodology

سه سطح calibration قفل شده‌اند.

## Level 1 — Parameter Calibration

سؤال:

> آیا ضرایبی مثل \(\rho,k_p,k_{pos},k_w,k_{te},k_t,k_{t2},H_A,A_A,k_{form}\) مناسب‌اند؟

روش:

- Maximum Likelihood Estimation
- Grid Search
- Bayesian Optimization

Loss هر match:

\[
L_i=-\log(P_{model}(actual\_score_i|\lambda_{home,i},\lambda_{away,i},params))
\]

و:

\[
TotalLoss=\sum_i L_i
\]

---

# 36. Calibration Split

اصل:

\[
Train/Calibration\ Data \neq Test\ Data
\]

تقسیم پیشنهادی بر اساس زمان:

```text
Calibration:
2005–2018

Test:
2019–2024
```

نه random split.

دلیل:

> جلوگیری از temporal leakage.

---

# 37. Parameter Calibration Pseudocode

```text
function calibrate_parameters(calibration_matches):

    initial_params = {
        rho: -0.13,
        k_p: 0.40,
        k_pos_calc: 1.5,
        ...
    }

    function total_negative_log_likelihood(params):
        total_loss = 0

        for match in calibration_matches:
            λ_h, λ_a = compute_lambda(
                match.team_a,
                match.team_b,
                params
            )

            p = dixon_coles_probability(
                match.actual_score,
                λ_h,
                λ_a,
                params.rho
            )

            total_loss += -log(p + epsilon)

        return total_loss

    return minimize(
        total_negative_log_likelihood,
        initial_params
    )
```

---

# 38. Level 2 — Probability Calibration

هدف:

> وقتی مدل احتمال 70% می‌دهد، آیا در بلندمدت تقریباً 70% اتفاق واقعاً رخ می‌دهد؟

روش:

1. روی Test Set احتمال Home Win تولید شود.
2. احتمالات به 10 bucket تقسیم شوند.
3. average predicted probability با actual frequency مقایسه شود.
4. reliability curve ایده‌آل به خط \(y=x\) نزدیک باشد.

Metric اصلی:

\[
BS=\frac1N\sum_i(p_i-y_i)^2
\]

Brier Score نزدیک صفر بهتر است.

---

# 39. Level 2 Pseudocode

```text
function evaluate_probability_calibration(test_matches, params):

    buckets = [[] for _ in range(10)]

    for match in test_matches:
        p_home_win = compute_win_probability(
            match.team_a,
            match.team_b,
            params
        )

        bucket_idx = int(p_home_win * 10)
        actual = 1 if match.actual_result == "home_win" else 0

        buckets[bucket_idx].append(
            (p_home_win, actual)
        )

    reliability_data = []

    for bucket in buckets:
        if len(bucket) > 0:
            avg_predicted = mean([p for p,a in bucket])
            actual_frequency = mean([a for p,a in bucket])
            reliability_data.append(
                (avg_predicted,
                 actual_frequency,
                 len(bucket))
            )

    return reliability_data
```

---

# 40. Level 3 — Simulation Validation

برای matchupهای واقعی که داده کافی دارند، تعداد زیادی simulation اجرا می‌شود و distribution با واقعیت مقایسه می‌شود.

N پیشنهادی:

```text
10,000 – 100,000 simulations
```

معیارهای اصلی:

### Score Distribution Shape

مقایسه‌ی frequency نتایج مثل:

```text
0-0
1-0
1-1
2-0
2-1
...
```

### Total Goals Distribution

بررسی:

- mean
- variance
- tail behavior

### W/D/L Distribution

برای سطوح مختلف اختلاف قدرت.

### Upset Rate

بررسی درصد برد تیم ضعیف‌تر در matchupهای strong vs weak.

---

# 41. Acceptance Criteria پیشنهادی M.6

| Scenario | Acceptance Criterion |
|---|---|
| Elite vs Elite | Stronger win rate حدود 45–55%، Draw حدود 25–30% |
| Strong vs Medium | Stronger win rate حدود 55–65% |
| Strong vs Weak | Stronger win rate حدود 70–85% |
| Equal vs Equal | Draw حدود 25–30% و بردها متقارن |
| Mean goals | 2.4–2.9 |
| 0–0 | 7–11% |
| Total goals ≥ 5 | < 8% |
| Brier Score | < 0.22 |

> این‌ها **acceptance criteria طراحی V1** هستند و باید هنگام calibration با داده مرجع واقعی validate / adjust شوند.

---

# 42. Overfitting Control

ریسک اصلی:

> پارامترهای زیاد (~15–20) نسبت به اندازه/تنوع داده.

روش بررسی:

```text
Calibration Loss
vs
Test Loss
```

اگر:

\[
Loss_{Test}\gg Loss_{Calibration}
\]

نشانه overfit است.

Regularization پیشنهادی:

\[
TotalLoss
=
NLL(data)
+
\lambda_{reg}
\sum_j(param_j-prior_j)^2
\]

این پارامترها را به priors اولیه نزدیک نگه می‌دارد.

---

# 43. Full Calibration Pipeline

```text
1. Collect historical real matches
2. Split by season/time
3. Fit parameters on Calibration Set
4. Evaluate probability calibration on Test Set
5. Run Monte Carlo validation
6. Compare score / goals / WDL / upset distributions
7. Check overfitting
8. Revise priors/formulas if criteria fail
9. Lock final parameter set
10. Use in production
```

---

# 44. Locked Parameter Priors — Current V1

| Parameter | Role | Initial Prior | Path |
|---|---|---:|---|
| \(k_{gk}\) | GK effect on Base | 0.10 | BaseRelativeStrength |
| \(k_{poss\_calc}\) | Possession sensitivity | 1.5 | CreationRealization |
| \(k_p\) | Press impact | 0.40 | \(I_{press}\) |
| \(k_w\) | Width mismatch | 0.20 | \(I_{width}\) |
| \(k_{te}\) | Tempo effect | 0.15 | \(I_{tempo}\) |
| \(k_t\) | Base transition/space weight | 0.50 | Transition layer (definition to finalize in implementation) |
| \(k_{t2}\) | Turnover-to-transition | 0.50 | T second term |
| \(BASELINE\) | Base goals anchor | 1.35 | λ_base |
| \(TRANSITION\_WEIGHT\) | Transition contribution | 0.55 | λ_base |
| \(H_A\) | Home multiplier | 1.10 | Home Advantage |
| \(A_A\) | Away multiplier | 0.95 | Home Advantage |
| \(k_{form}\) | Form effect | 0.15 | FormFactor |
| \(\rho\) | DC low-score correction | -0.13 | Probability layer |

> همه این مقادیر، به‌جز قوانینی که ساختاری هستند، **calibration priors** محسوب می‌شوند نه truth نهایی.

---

# 45. Final Dependency Graph — Current Architecture

```text
                    PlayerSeason
                         │
                         ▼
                Formation + Roles
                         │
                         ▼
          ┌──────────────────────────┐
          │ Team Dimensions          │
          │ Attack / Creation       │
          │ Defense / Goalkeeping   │
          └──────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────┐
          │ Team Identity            │
          │ Possession / Press       │
          │ Transition / Tempo      │
          │ Risk / Compactness      │
          └──────────────────────────┘
                         │
                         ▼
                Historical Prior
                         │
                         ▼
                  TeamSeason State
                         │
                         ▼
               Tactical Profile
                         │
                         ▼
                 Matchup Engine
                     ┌────┴────┐
                     ▼         ▼
                     M         T
                     └────┬────┘
                          ▼
                       λ_base
                          │
                          ▼
                    Home Advantage
                          │
                          ▼
                  Form (if applicable)
                          │
                          ▼
                       λ_final
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
        duration scaling       game context
                │
                ▼
      ┌───────────────────────┐
      │ Probability Layer     │
      │ DC >= 15 min          │
      │ Poisson < 15 min      │
      └───────────────────────┘
                │
                ▼
              Sample
                │
                ▼
          Goal / Match Event
                │
                ▼
            State Update
                │
                ▼
          Next Sub-segment
```

---

# 46. Explicit Anti-Double-Counting Rules

این قوانین در architecture باید حفظ شوند:

1. Possession فقط از `CreationRealization` وارد λ شود.
2. Tempo فقط از طریق `M` وارد شود.
3. High line فقط از طریق `SpaceBehindDefense` به `T` برسد.
4. Transition tendency فقط در `T` باشد.
5. Home Advantage در Matchup Engine نباشد.
6. Form با Team Identity یکی نشود.
7. Randomness ضریب مستقل λ نباشد در V1.
8. Outcome یک segment نباید λ همان segment را retroactively تغییر دهد.
9. Goal / Red Card می‌توانند state آینده را تغییر دهند.
10. Player attribution نباید یک مسیر مستقل دوباره به team λ بسازد.

---

# 47. Current Status Checklist

```text
[LOCKED] Section 1 — PlayerSeason → Team Dimensions / Identity
[LOCKED] Section 2 — Formation Engine
[LOCKED] Section 3 — State Machine + Temporal Execution
[LOCKED] Section 4 — Matchup Engine
[LOCKED] Section 5 — λ Architecture + Home Advantage + Form
[LOCKED] Section 6 — Dixon-Coles + Sampling
[LOCKED] Section L — Historical Team Hybrid Model
[LOCKED] Section M — Calibration Methodology

[NEXT] Section N — Implementation Architecture + V1/V2/V3

[AFTER N] Section J/K — Player Performance + Match Events
```

---

# 48. Next Step — Section N

Section N باید معماری نظری را به specification اجرایی تبدیل کند.

موارد پیشنهادی:

```text
N.1 Final module architecture
N.2 Dependency graph in code
N.3 Runtime execution order
N.4 Immutable data vs runtime state
N.5 Interfaces / API contracts between modules
N.6 V1 scope
N.7 V2 scope
N.8 V3 scope
N.9 Logging / reproducibility / random seed
N.10 Production validation checklist
```

ترتیب منطقی بعد از N:

```text
N → J/K → Event Generator → Player Attribution → richer simulation
```

---

# 49. One-Sentence Architecture Definition

> **این موتور یک سیستم hybrid و causal برای شبیه‌سازی فوتبال تاریخی است که از PlayerSeason و Formation، Team Dimensions/Identity را می‌سازد؛ با Matchup Engine دو منبع M (organized attack) و T (transition threat) را استخراج می‌کند؛ آن‌ها را به λ تبدیل می‌کند؛ Home Advantage و Form را جداگانه اعمال می‌کند؛ سپس λ را با Dixon-Coles/Poisson به probability distribution و در نهایت به random game events تبدیل می‌کند، در حالی که state آینده می‌تواند از outcome فعلی تغییر کند بدون اینکه dependencyهای دوباره یا double-counting وارد مسیر λ شوند.**

---

---

# Section N — Implementation Architecture + V1/V2/V3

> **Status:** LOCKED  
> **این section معماری نظری را به specification اجرایی تبدیل می‌کند.**

---

## N.1 معماری نهایی ماژول‌ها

```text
┌─────────────────────────────────────────────────┐
│  DATA LAYER (Immutable, Pre-computed)            │
│  - PlayerSeason DB                               │
│  - TeamSeason DB (roster + historical_prior)     │
│  - Formation Templates (Position Pool)           │
└───────────────────┬──────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  MODULE 1: Formation Engine                      │
│  Input:  11 selected PlayerSeasons + slots       │
│  Output: StructuralFeatures (15), Type A/B/C     │
└───────────────────┬──────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  MODULE 2: Team Strength Engine                  │
│  Input:  PlayerSeasons + StructuralFeatures      │
│  Output: TeamDimensions{Attack,Creation,Def,GK}  │
└───────────────────┬──────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  MODULE 3: Team Identity Engine                  │
│  Input:  PlayerSeasons + HistoricalPrior         │
│  Output: TeamIdentity{possession,press,...}      │
└───────────────────┬──────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  MODULE 4: Match Orchestrator (per-match runtime)│
│  ├── State Machine                               │
│  ├── Tactical Profile Generator                  │
│  ├── Matchup Engine (M, T)                       │
│  ├── λ Calculator (Home/Form)                    │
│  ├── Segment Simulator (Dixon-Coles / Poisson)   │
│  └── Sampling + State Update Loop                │
│  Output: Final Score + Segment-by-segment log    │
└───────────────────┬──────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  MODULE 5: Player Performance & Event Generator  │
│  (بخش J/K — بعداً طراحی می‌شود)                 │
│  Input:  Final Score + Segment goal log          │
│  Output: Scorers, Assists, Ratings, Events       │
└─────────────────────────────────────────────────┘
```

---

## N.2 Data Flow + Dependency Graph

```text
PlayerSeason ──┬──→ Formation Engine ──→ StructuralFeatures
               │                              │
               ├──→ Team Dimensions ←─────────┤ (Type A/B modifiers)
               │         │
               └──→ Team Identity
                         │
              [+ HistoricalPrior, clamp formula]
                         │
                         ▼
              TeamSeason (runtime instance, formation-specific)
                         │
        ┌────────────────┴────────────────┐
        ▼ (Team A)                        ▼ (Team B)
   State Machine ←──── score, minute ────→ State Machine
        │                                          │
   Tactical Profile                          Tactical Profile
        │                                          │
        └──────────────┬───────────────────────────┘
                        ▼
                 Matchup Engine
                  (M_A→B, T_A→B, M_B→A, T_B→A)
                        │
                        ▼
                    λ_base → × Home Advantage → × Form → λ_final
                        │
                        ▼
              Segment Duration Scaling
                        │
                        ▼
        duration ≥ 15? → Dixon-Coles : Independent Poisson
                        │
                        ▼
                  Sample (x, y) for this segment
                        │
                        ▼
              goal happened? → Update Score → Loop back to State Machine
                        │
                        ▼ (no more segments)
                   FINAL SCORE
```

---

## N.3 Runtime Execution Order (Pseudocode)

```python
def simulate_match(team_a_season, team_b_season,
                   formation_a, formation_b,
                   is_tournament=False):

    # === Pre-computation (once per match) ===
    struct_features_a = formation_engine(team_a_season.roster, formation_a)
    struct_features_b = formation_engine(team_b_season.roster, formation_b)

    dims_a = compute_team_dimensions(team_a_season.roster, struct_features_a)
    dims_b = compute_team_dimensions(team_b_season.roster, struct_features_b)

    identity_a = compute_team_identity(team_a_season, struct_features_a)
    identity_b = compute_team_identity(team_b_season, struct_features_b)

    # === Runtime state ===
    score_a, score_b = 0, 0
    current_minute = 0
    segment_boundaries = [30, 60, 75, 90]
    goal_log = []

    for boundary in segment_boundaries:
        remaining_in_segment = boundary - current_minute

        while remaining_in_segment > 0:

            # 1. State Detection
            state_a = detect_state(score_a - score_b,
                                   current_minute,
                                   identity_a.risk_tolerance)
            state_b = detect_state(score_b - score_a,
                                   current_minute,
                                   identity_b.risk_tolerance)

            # 2. Tactical Profile
            tactical_a = build_tactical_profile(identity_a, state_a)
            tactical_b = build_tactical_profile(identity_b, state_b)

            # 3. Matchup Engine
            M_ab, T_ab = matchup_engine(dims_a, tactical_a, dims_b, tactical_b)
            M_ba, T_ba = matchup_engine(dims_b, tactical_b, dims_a, tactical_a)

            # 4. Lambda calculation
            lambda_a_90 = compute_lambda(
                M_ab, T_ab,
                home=True,
                form=get_form(team_a_season, is_tournament)
            )
            lambda_b_90 = compute_lambda(
                M_ba, T_ba,
                home=False,
                form=get_form(team_b_season, is_tournament)
            )

            # 5. Duration scaling
            lambda_a_seg = lambda_a_90 * remaining_in_segment / 90
            lambda_b_seg = lambda_b_90 * remaining_in_segment / 90

            # 6. Sample
            if remaining_in_segment >= 15:
                goals_a, goals_b, goal_minute = sample_dixon_coles(
                    lambda_a_seg, lambda_b_seg,
                    current_minute, remaining_in_segment
                )
            else:
                goals_a, goals_b, goal_minute = sample_independent_poisson(
                    lambda_a_seg, lambda_b_seg,
                    current_minute, remaining_in_segment
                )

            if goals_a == 0 and goals_b == 0:
                # هیچ گلی در این segment باقی‌مانده نیفتاد
                current_minute = boundary
                remaining_in_segment = 0
            else:
                # اولین گل را پیدا کن، segment را در آن نقطه بشکن
                score_a += goals_a
                score_b += goals_b
                goal_log.append({
                    "minute": goal_minute,
                    "score": (score_a, score_b)
                })
                current_minute = goal_minute
                remaining_in_segment = boundary - current_minute
                # حلقه دوباره از نو با state جدید اجرا می‌شود

    return {
        "final_score": (score_a, score_b),
        "goal_log": goal_log,
        "dims_a": dims_a,
        "dims_b": dims_b    # برای Module 5 لازم است
    }
```

**نکته‌ی پیاده‌سازی مهم:** تابع `sample_dixon_coles` باید علاوه بر تعداد گل، اولین لحظه‌ی گل را هم مشخص کند. این یعنی به‌جای sample کردن مستقیم از ماتریس (x,y)، یک لایه‌ی اضافه داریم که زمان اولین گل را از توزیع نمایی (Exponential — مکمل طبیعی Poisson) sample می‌کند، بعد مشخص می‌کند کدام تیم زده.

---

## N.4 Immutable vs Runtime State — تفکیک صریح

### IMMUTABLE — یک‌بار محاسبه، در طول کل بازی ثابت

```text
- PlayerSeason attributes
- TeamDimensions (Attack/Creation/Defense/GK)
  (چون formation در طول بازی عوض نمی‌شود در V1)
- TeamIdentity (possession_tendency, press_tendency, ...)
- HistoricalPrior
```

### RUNTIME — در طول بازی تغییر می‌کند

```text
- score_a, score_b
- current_minute
- state_a, state_b   (LEADING / LOSING / ...)
- tactical_a, tactical_b   (بعد از State Adjustment)
- M, T, λ   (هر segment دوباره محاسبه می‌شوند)
```

---

## N.5 Reproducibility + Random Seed

برای قابلیت تکرار (replay یک بازی برای دیباگ یا نمایش به کاربر):

```python
seed = hash(team_a_id, team_b_id, match_date, match_id)
random_generator = PRNG(seed)
```

تمام sample‌های تصادفی (Dixon-Coles sampling، goal timing) باید از همین یک generator با seed مشخص بیایند، نه از `Math.random()` سراسری.

اگر بخواهیم دقیقاً همان بازی را replay کنیم، فقط کافی است seed را نگه داریم.

---

## N.6 V1 — Minimal Complete Core

> **اصل:** V1 از نظر معماری کامل است، از نظر sophistication ساده.
> ساده‌سازی V1 در عمق مدل‌هاست، نه در حذف اجزای core architecture.

### اجزای معماری که در V1 حذف‌ناپذیرند

```text
✅ M + T جدا
   (Single-Path Dependency Rules قفل است؛
    ادغام T داخل M = نقض مستقیم anti-double-counting)

✅ Dixon-Coles با τ correction
   (جزو Probability Layer اصلی معماری است؛
    پیچیدگی پیاده‌سازی ندارد و
    low-score distribution را واقعی‌تر می‌کند)

✅ Sequential Temporal Segments
   (State Machine بدون چند segment معنا ندارد؛
    مسیر State → Tactical → M/T → λ → Sample → Goal → State Update
    باید حلقه‌وار و sequential باشد)

✅ State Machine
✅ λ Architecture کامل (M، T، Home Advantage، Form در Tournament)
✅ Segment Duration Scaling
✅ Segment Splitting روی Goal / Red Card
✅ Seed / Reproducibility
✅ Historical Prior (برای Tier 1 تیم‌های موجود در بازی)
✅ Basic Calibration (Level 1)
```

### ساده‌سازی‌های مجاز در V1

```text
⬇ Formation Engine: 6-8 Context Rule
  (نه 15 تای کامل — اضافه می‌شود در V2)

⬇ State Machine: state_intensity پیوسته نیست
  (چند حالت گسسته کافی است در V1)

⬇ Historical Prior: فقط برای تیم‌های Tier 1 لازم
  (نه همه‌ی تیم‌ها)

⬇ Player Attribution: ساده
  (وزن Attack ability برای گلزن، بدون assist chain واقعی)

⬇ No fatigue / substitution دقیق
⬇ No pair/line synergy
⬇ No era normalization
```

---

## N.7 V2 — Richer + More Precise

> **اصل:** V2 دقت و غنای مدل را بالا می‌برد، بدون تغییر در معماری core.

```text
✅ همه‌ی موارد V1 (معماری دست‌نخورده)

✅ Formation Engine کامل:
   15 Context Rule + Type A/B/C

✅ Historical Prior برای Tier 1 + Tier 2
   (30-50 تیم iconic + notable teams)

✅ State Machine:
   state_intensity پیوسته
   + State Adjustment دقیق‌تر

✅ Player Stats: backward allocation کامل‌تر
   (شوت‌ها، xG per player، assist chain ساده)

✅ Calibration Level 1+2
   (Parameter Calibration + Probability Calibration)

✅ Segment splitting با goal timing دقیق
   (Exponential distribution برای زمان اولین گل)
```

---

## N.8 V3 — Research-Grade / High-Fidelity

> **اصل:** V3 fidelity را به سطح research-grade می‌رساند.

```text
✅ همه‌ی موارد V2

✅ Historical Prior برای صدها تیم
   (نه فقط 30-50 تا)

✅ Era-aware normalization
   (attribute های 1989 در مقابل 2020
    به‌درستی مقایسه شوند — لایه‌ای جداگانه
    روی core engine، بدون تغییر در آن)

✅ Pair/Line Synergy effects
   (سینرژی بین بازیکنان مجاور،
    نه فقط aggregation مستقل —
    نیاز به دیتای بازیکن‌به‌بازیکن دارد)

✅ Structural Integrity دقیق:
   CB pairing، fullback exposure

✅ Fatigue / Substitution effects
   روی λ در دقایق پایانی

✅ Red Card به‌عنوان Major Event
   که Team Dimension را واقعاً کم می‌کند
   (تیم 10 نفره → recalculate dims)

✅ Full Calibration Level 1+2+3
   با دیتاست بزرگ (چند هزار بازی واقعی
    + fine-tuning دستی)

✅ Momentum / Morale
   به‌عنوان یک لایه‌ی نازک (نه غالب) روی λ
   (با احتیاط — ریسک overlap با Form/State)
```

---

## N.9 تعریف نهایی و قفل‌شده‌ی سه نسخه

```text
V1 = کامل از نظر معماری، ساده از نظر sophistication
V2 = دقیق‌تر و غنی‌تر (همان معماری، عمق بیشتر)
V3 = research-grade / high-fidelity
```

### چه چیزی هرگز در V1/V2 وارد نمی‌شود

```text
🚫 Pair/Line Synergy
   (دیتای لازم موجود نیست)

🚫 Fatigue/Substitution دقیق
   (پیچیدگی بالا، فایده‌ی کم در V1/V2)

🚫 Era normalization در core engine
   (باید به‌صورت لایه‌ی جداگانه بعداً اضافه شود)

🚫 Momentum/Morale جدا از Form
   (ریسک overlap مفهومی با Form/State)

🚫 Red Card با recalculate dims
   (در V1/V2 کارت قرمز segment را می‌شکند
    ولی dimension recalculation کامل به V3 موکول است)
```

---

## N.10 Segment-Breaking Events — تفکیک صریح

### Segment-Splitting Events (باعث Recalculation فوری)

```text
✓ گل (هر گل)
✓ اخراج / کارت قرمز
  (چون مستقیم روی Team Dimension اثر می‌گذارد)
```

### Non-Splitting Events (فقط در بخش J/K به‌عنوان «رویداد نمایشی»)

```text
✗ کارت زرد
✗ تعویض معمولی
  (مگر با یک قانون ساده در V2:
   تعویض میانه‌ی نیمه‌ی دوم می‌تواند
   یک ضریب کوچک fatigue بدهد)
✗ موقعیت از دست‌رفته / سیو گلر
```

---

## N.11 Final Roadmap

```text
[LOCKED] Section 1-6  — Core Mathematical Architecture
[LOCKED] Section L    — Historical Team Hybrid Model
[LOCKED] Section M    — Calibration Methodology
[LOCKED] Section N    — Implementation Architecture + V1/V2/V3
[LOCKED] Section J/K  — Player Performance + Match Events (contracts)
[LOCKED] Section O    — Data Contracts + Module Interfaces
[LOCKED] Section P    — Match Runtime Object
[LOCKED] Section Q    — Event Generator
[LOCKED] Section R    — Player Attribution

[NEXT]   Section S    — Full Simulation Engine
         Section T    — Calibration Implementation
         Production
```

---

## End of Section N

---

# Section J/K — Player Performance & Match Events (Contracts)

> **Status:** LOCKED
> **جایگاه در pipeline:** بعد از Sample، قبل از State Update

---

## J/K.1 اصل کلی

$$\boxed{\text{J/K observes and attributes the sampled outcome; it does not create a competing prediction path.}}$$

مرز اصلی:

```text
MODULES 0–7  →  pre-sample   →  می‌توانند λ را تغییر دهند
MODULE 8     →  THE BOUNDARY →  randomness وارد می‌شود
MODULES 9–11 →  post-sample  →  هرگز λ را تغییر نمی‌دهند
```

---

## J/K.2 ساختار Pipeline

```text
                    λ
                    │
                    ▼
             Probability Layer
                    │
                    ▼
              Sample Goals
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
    J: Goal Attribution   K: Event Generator
          │                   │
          ▼             ┌─────┴──────────────┐
    Scorer / Assist    Shots   Cards   Subs  Saves
```

Feedback به pipeline اصلی فقط از این دو:

```text
Goal     → Score update → State تغییر می‌کند
Red Card → Segment split → (V2) λ_modifier روی آینده
```

---

## J/K.3 مسیر قفل‌شده‌ی Shot Generation

$$\boxed{Goal\ Count \rightarrow Shot\ Count \rightarrow Player\ Attribution}$$

نه:

$$Shots \rightarrow Goal\ Count \rightarrow \lambda$$

---

## J/K.4 Red Card — تفکیک سه سطح

| نسخه | رفتار |
|---|---|
| V1 | split segment، λ تغییر نمی‌کند |
| V2 | split + `λ_team × R_card` با prior `R_card = 0.75` |
| V3 | full structural recalculation برای تیم 10 نفره |

---

## J/K.5 جدول کامل

| جزء | V1 | V2 | مسیر برگشتی به λ؟ |
|---|---|---|---|
| Goal attribution | ✓ | ✓ | ❌ |
| Scorer | ✓ | ✓ | ❌ |
| Assist | ساده | کامل‌تر | ❌ |
| Shots | مشتق از Goals | xG دقیق‌تر | ❌ |
| xG/player | ساده | richer | ❌ |
| Yellow Card | ✓ | ✓ | ❌ |
| Substitution | ✓ | ✓ | ❌ |
| Red Card | split فقط | split + λ modifier | فقط برای آینده |
| Recalculate Dims بعد Red | ❌ | ❌ | — |
| Full 10-player structural recalc | V3 | V3 | — |

---

# Section O — Engine State & Data Contracts

> **Status:** LOCKED

---

## O.1 اصل کلی

هر ماژول یک contract دارد با ۷ فیلد:

```text
INPUT             — چه می‌گیرد
OUTPUT            — چه تحویل می‌دهد
IMMUTABLE?        — آیا output در طول بازی ثابت است؟
RUNTIME?          — آیا per-segment دوباره محاسبه می‌شود؟
CAN_CHANGE_λ?     — آیا مستقیم یا غیرمستقیم روی λ اثر دارد؟
CAN_CHANGE_STATE? — آیا می‌تواند state بازی را تغییر دهد؟
RANDOMNESS?       — آیا output آن تصادفی است؟
```

قانون طلایی:

$$\boxed{\text{اگر CAN\_CHANGE\_λ = YES، ماژول نمی‌تواند post-sample باشد}}$$

$$\boxed{\text{اگر post-sample است، CAN\_CHANGE\_λ = NO}}$$

---

## O.2 Contracts همه‌ی ماژول‌ها

### MODULE 0 — PlayerSeason

```text
INPUT:         raw player data (از DB)
OUTPUT:        PlayerSeason {
                   id, name, season, role,
                   attack_ability, creation_ability,
                   defense_ability, gk_ability,
                   shot_tendency, press_tendency,
                   transition_tendency, pace, ...
               }
IMMUTABLE?          YES
RUNTIME?            NO
CAN_CHANGE_λ?       INDIRECT
CAN_CHANGE_STATE?   NO
RANDOMNESS?         NO
```

---

### MODULE 1 — Formation Engine

```text
INPUT:         List[PlayerSeason] (11 نفر)
               FormationTemplate
OUTPUT:        StructuralFeatures {
                   formation_type,
                   width_feature,
                   line_height_feature,
                   defensive_cover_feature,
                   press_structure_feature,
                   build_up_structure_feature,
                   transition_structure_feature,
                   cb_pairing_quality,
                   fullback_exposure, ...
               }
IMMUTABLE?          YES
RUNTIME?            NO
CAN_CHANGE_λ?       INDIRECT
CAN_CHANGE_STATE?   NO
RANDOMNESS?         NO
```

---

### MODULE 2 — Team Dimension Engine

```text
INPUT:         List[PlayerSeason] + StructuralFeatures
OUTPUT:        TeamDimensions {
                   attack, creation, defense, goalkeeping
               }
IMMUTABLE?          YES
RUNTIME?            NO
CAN_CHANGE_λ?       INDIRECT
CAN_CHANGE_STATE?   NO
RANDOMNESS?         NO
```

---

### MODULE 3 — Team Identity Engine

```text
INPUT:         List[PlayerSeason] + StructuralFeatures + HistoricalPrior
OUTPUT:        TeamIdentity {
                   possession_tendency, press_tendency,
                   transition_tendency, tempo,
                   risk_tolerance, compactness,
                   build_up_control_score, attack_pace_factor
               }
IMMUTABLE?          YES
RUNTIME?            NO
CAN_CHANGE_λ?       INDIRECT
CAN_CHANGE_STATE?   NO
RANDOMNESS?         NO
```

---

### MODULE 4 — TeamRuntimeState

```text
IMMUTABLE FIELDS (هرگز تغییر نمی‌کنند):
    team_id, dims, identity, formation, roster, is_home

MUTABLE FIELDS (فقط State Updater می‌نویسد):
    score, player_count, state (MatchState enum),
    form_factor, red_card_modifier

IMMUTABLE?          PARTIAL
RUNTIME?            YES
CAN_CHANGE_λ?       YES (از طریق state → TacticalProfile)
CAN_CHANGE_STATE?   YES
RANDOMNESS?         NO
```

---

### MODULE 5 — Tactical Profile Generator

```text
INPUT:         TeamIdentity + TeamRuntimeState.state
OUTPUT:        TacticalProfile {
                   press_final, line_final, width_final,
                   build_up_control_score,
                   defensive_cover_feature,
                   attack_pace_factor,
                   transition_tendency_final
               }
IMMUTABLE?          NO (per-segment)
RUNTIME?            YES
CAN_CHANGE_λ?       YES
CAN_CHANGE_STATE?   NO
RANDOMNESS?         NO
```

---

### MODULE 6 — Matchup Engine

```text
INPUT:         TeamDimensions (A,B) + TacticalProfile (A,B) + GlobalAnchors
OUTPUT:        MatchupResult {
                   M_a_to_b, M_b_to_a,
                   T_a_to_b, T_b_to_a
               }
IMMUTABLE?          NO (per-segment)
RUNTIME?            YES
CAN_CHANGE_λ?       YES
CAN_CHANGE_STATE?   NO
RANDOMNESS?         NO
```

---

### MODULE 7 — λ Calculator

```text
INPUT:         MatchupResult + TeamRuntimeState
               (home_flag, form_factor, red_card_modifier)
               + Constants {BASELINE, TRANSITION_WEIGHT, H_A, A_A, k_form}
OUTPUT:        LambdaPair {lambda_home_90, lambda_away_90}
IMMUTABLE?          NO (per-segment)
RUNTIME?            YES
CAN_CHANGE_λ?       YES
CAN_CHANGE_STATE?   NO
RANDOMNESS?         NO
```

---

### MODULE 8 — Probability Model + Sampler ← **THE BOUNDARY**

```text
INPUT:         LambdaPair + segment_duration + rng
OUTPUT:        SegmentOutcome {
                   goals_home, goals_away, goal_minute
               }
IMMUTABLE?          NO
RUNTIME?            YES
CAN_CHANGE_λ?       NO  ← ← ← مرز اصلی
CAN_CHANGE_STATE?   YES (از طریق goals)
RANDOMNESS?         YES ← تنها منبع اصلی randomness
```

---

### MODULE 9 — J: Goal Attribution

```text
INPUT:         SegmentOutcome + rosters + TacticalProfiles + rng
OUTPUT:        List[AttributedGoalEvent]
CAN_CHANGE_λ?       NO
CAN_CHANGE_STATE?   NO
RANDOMNESS?         YES
```

---

### MODULE 10 — K: Event Generator

```text
INPUT:         SegmentOutcome + LambdaPair (read-only)
               + TacticalProfiles + TeamRuntimeStates + rng
OUTPUT:        MatchEvents {shots, saves, yellow_cards, substitutions}
CAN_CHANGE_λ?       NO (می‌تواند بخواند، نمی‌تواند بنویسد)
CAN_CHANGE_STATE?   NO
RANDOMNESS?         YES
```

---

### MODULE 11 — State Updater

```text
INPUT:         SegmentOutcome + AttributedGoalEvents
               + RedCardEvent | null + TeamRuntimeStates
OUTPUT:        Updated TeamRuntimeStates
               {score, state, player_count, red_card_modifier, current_minute}
CAN_CHANGE_λ?       INDIRECT (از طریق state → segment بعدی)
CAN_CHANGE_STATE?   YES
RANDOMNESS?         NO
```

---

## O.3 جدول خلاصه

| # | Module | Runtime? | CAN_CHANGE_λ? | CAN_CHANGE_STATE? | RANDOMNESS? |
|---|---|---|---|---|---|
| 0 | PlayerSeason | NO | INDIRECT | NO | NO |
| 1 | Formation Engine | NO | INDIRECT | NO | NO |
| 2 | Team Dimension Engine | NO | INDIRECT | NO | NO |
| 3 | Team Identity Engine | NO | INDIRECT | NO | NO |
| 4 | TeamRuntimeState | PARTIAL | YES | YES | NO |
| 5 | Tactical Profile | YES | YES | NO | NO |
| 6 | Matchup Engine | YES | YES | NO | NO |
| 7 | λ Calculator | YES | YES | NO | NO |
| **8** | **Sampler ← مرز** | YES | **NO** | YES | **YES** |
| 9 | Goal Attribution (J) | YES | NO | NO | YES |
| 10 | Event Generator (K) | YES | NO | NO | YES |
| 11 | State Updater | YES | INDIRECT | YES | NO |

---

## O.4 قانون مرز — قفل نهایی

```text
MODULES 0–7   →  pre-sample   →  CAN_CHANGE_λ = YES مجاز
MODULE 8       →  THE BOUNDARY →  randomness وارد می‌شود
MODULES 9–11   →  post-sample  →  CAN_CHANGE_λ = NO، بدون استثنا
```

Modules 9 و 10 هیچ reference‌ای به λ Calculator یا Matchup Engine ندارند — فقط `LambdaPair` را به‌عنوان read-only input می‌خوانند (فقط K، فقط برای shot count).

---

# Section P — Match Runtime Object

> **Status:** LOCKED

---

## P.1 اصل کلی

$$\boxed{\text{MatchRuntime = State Container, not Prediction Engine}}$$

هیچ فرمول محاسباتی داخل object نیست. فقط نتایج ماژول‌های خارجی را نگه می‌دارد.

---

## P.2 Schema کامل MatchRuntime

```text
MatchRuntime {

    ── MATCH META (immutable) ──────────────────────────────
    match_id:         string
    seed:             int
    is_tournament:    bool
    home_team_id:     string
    away_team_id:     string

    ── RNG ─────────────────────────────────────────────────
    rng:              SeededRNG        # همه‌ی randomness از اینجا

    ── TEAM RUNTIME STATES (mutable) ───────────────────────
    home:             TeamRuntimeState
    away:             TeamRuntimeState

    ── SEGMENT STATE (mutable, per-segment) ────────────────
    current_minute:   int
    segment_id:       int              # 1=S1, 2=S2, 3=S3, 4=S4
    segment_start:    int
    segment_end:      int              # 30 / 60 / 75 / 90
    remaining:        int              # segment_end - current_minute

    ── COMPUTED CACHE (mutable, per-sub-segment) ───────────
    # نتیجه‌ی آخرین اجرای ماژول‌ها — فقط از طریق ماژول‌ها set می‌شوند
    tactical_home:    TacticalProfile | null
    tactical_away:    TacticalProfile | null
    matchup:          MatchupResult   | null
    lambda:           LambdaPair      | null

    ── EVENT LOG (append-only) ─────────────────────────────
    goals:            List[AttributedGoalEvent]
    cards:            List[CardEvent]
    substitutions:    List[SubstitutionEvent]
    shots:            List[ShotEvent]

    ── FINAL OUTPUT ────────────────────────────────────────
    final_score_home: int  | null
    final_score_away: int  | null
    is_finished:      bool
}
```

---

## P.3 TeamRuntimeState Schema

```text
TeamRuntimeState {

    ── IMMUTABLE ────────────────────────────────────────────
    team_id, dims, identity, formation, roster, is_home

    ── MUTABLE (فقط State Updater می‌نویسد) ─────────────────
    score:              int       # شروع: 0
    player_count:       int       # شروع: 11
    state:              MatchState
    form_factor:        float     # 1.0 در standalone
    red_card_modifier:  float     # 1.0 default، 0.75 در V2
}
```

**MatchState enum:**

```text
NORMAL    — پیش‌فرض
LEADING   — جلوافتاده، محافظه‌کارانه‌تر
LOSING    — عقب‌افتاده، تهاجمی‌تر
REACTIVE  — نزدیک پایان، نیاز فوری به گل
```

---

## P.4 Lifecycle یک Segment

```text
┌─ شروع sub-segment ────────────────────────────────────────┐
│                                                            │
│  1. READ state                                             │
│     home.state / away.state                               │
│                                                            │
│  2. COMPUTE TacticalProfile          [Module 5]           │
│     → MatchRuntime.tactical_home/away = result            │
│                                                            │
│  3. COMPUTE Matchup                  [Module 6]           │
│     → MatchRuntime.matchup = result                       │
│                                                            │
│  4. COMPUTE λ                        [Module 7]           │
│     → MatchRuntime.lambda = result                        │
│                                                            │
│  ─── MODULE 8: THE BOUNDARY ──────────────────────────── │
│                                                            │
│  5. SAMPLE                           [Module 8]           │
│     outcome = Sampler(lambda, remaining, rng)             │
│     → SegmentOutcome                                      │
│                                                            │
│  ─── POST-SAMPLE ─────────────────────────────────────── │
│                                                            │
│  6. ATTRIBUTE Goals                  [Module 9 — J]       │
│     → MatchRuntime.goals.append(...)                      │
│                                                            │
│  7. GENERATE Events                  [Module 10 — K]      │
│     lambda = read-only                                    │
│     → MatchRuntime.shots/cards/subs.append(...)           │
│                                                            │
│  8. UPDATE State                     [Module 11]          │
│     → home/away: score, state, player_count updated       │
│     → current_minute updated                              │
│                                                            │
│  9. BRANCH                                                │
│     no_goal → current_minute = segment_end → next segment │
│     goal    → current_minute = goal_minute → repeat       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## P.5 مالکیت فیلدها

| فیلد | مالک write | بقیه |
|---|---|---|
| `home/away.dims/identity/formation` | فقط initialization | read-only |
| `home/away.score` | فقط State Updater | read-only |
| `home/away.state` | فقط State Updater | read-only |
| `home/away.red_card_modifier` | فقط State Updater | read-only |
| `tactical_home/away` | فقط Tactical Profile Generator | read-only |
| `matchup` | فقط Matchup Engine | read-only |
| `lambda` | فقط λ Calculator | read-only |
| `goals/cards/shots/subs` | فقط J و K (append-only) | read-only |
| `current_minute` | فقط State Updater | read-only |
| `rng` | هیچ‌کس — فقط `.next()` | call-only |

---

## P.6 MatchResult — خروجی نهایی

```text
MatchResult {
    match_id:         string
    final_score:      (int, int)
    goal_log:         List[AttributedGoalEvent]
    event_log:        List[MatchEvent]
    seed:             int                 ← برای replay
    dims_home:        TeamDimensions      ← برای tournament chain
    dims_away:        TeamDimensions
}
```

---

# Section Q — Event Generator

> **Status:** LOCKED

---

## Q.1 Contract

```text
INPUT:
    outcome:       SegmentOutcome
    lambda:        LambdaPair         ← read-only
    tactical_home: TacticalProfile
    tactical_away: TacticalProfile
    state_home:    MatchState
    state_away:    MatchState
    duration:      int
    rng:           SeededRNG

OUTPUT:
    MatchEvents {shots_home, shots_away, saves, yellow_cards, substitutions}

CAN_CHANGE_λ?     NO
CAN_CHANGE_STATE? NO
CAN_CREATE_GOAL?  NO
RANDOMNESS?       YES
```

$$\boxed{Goals \leq Shots}$$

---

## Q.2 Shot Generation

$$\mu_{miss}(team) = \max\!\left(\frac{\lambda_{team,90}}{conversion\_prior} \times \frac{duration}{90} - goals_{team},\ 0\right)$$

$$MissedShots_{team} \sim Poisson(\mu_{miss})$$

$$Shots_{team} = goals_{team} + MissedShots_{team}$$

`conversion_prior ≈ 0.10` — calibration parameter، نه truth نهایی.

**نکته‌ی مهم:** `conversion_prior` فقط پارامتر توزیع شوت‌های از‌دست‌رفته است. در نتیجه ممکن است `5 شوت = 5 گل` اتفاق بیفتد — این درست است چون گل count از Probability Layer آمده.

**Enforcement:**

```text
assert Shots >= goals   # همیشه
if μ_miss < 0: MissedShots = 0   # defensive
```

---

## Q.3 Shot Quality / xG

**V1:**

$$xG_{per\_shot} = \frac{\lambda_{team,segment}}{Shots_{team}}$$

همه‌ی شوت‌ها xG یکسان دارند.

**V2:** هر شوت `shot_quality` می‌گیرد از role + tactical position + state:

$$\sum xG_i \approx \lambda_{segment} \quad \text{(internal consistency)}$$

---

## Q.4 Saves

$$OffTarget \sim Binomial(MissedShots,\ p_{off\_target})$$

$$p_{off\_target} \approx 0.40 \quad \text{(prior)}$$

$$Saves_{gk} = Shots_{opponent} - goals - OffTarget_{opponent}$$

$$Saves = \max(0,\ computed\_saves)$$

---

## Q.5 Yellow Cards

$$P(YC_{team}) = k_{yc} \times press_{team} \times tempo_{team} \times \frac{duration}{90}$$

$$k_{yc} \approx 0.15 \quad \text{(prior)}$$

$$YC_{team} \sim Bernoulli(P(YC_{team}))$$

اگر `YC=1`: بازیکن با weight معکوس `discipline_score` انتخاب می‌شود.

---

## Q.6 Substitutions

```text
تعویض فقط در S3 و S4
حداکثر 3 تعویض per team per match

P(sub | S3) = 0.55
P(sub | S4) = 0.70

if state == LOSING and S4: P(sub) × 1.3

sub_out: weighted random از غیر-GK، weight ∝ (1 - impact_score)
sub_in:  weighted random از bench
```

تعویض در V1/V2 هیچ تأثیری روی `TeamDimensions` ندارد.

---

## Q.7 Red Cards

$$P(RC_{team}) = k_{rc} \times \frac{press_{team} \times tempo_{team}}{2} \times \frac{duration}{90}$$

$$k_{rc} \approx 0.012 \quad \text{(prior)}$$

**V1:** split segment، λ تغییر نمی‌کند.

**V2:**

$$\lambda'_{team} = \lambda_{team} \times R_{card}, \quad R_{card} = 0.75 \quad \text{(prior)}$$

فقط روی تیم ۱۰ نفره اعمال می‌شود.

**Constraint:**

```text
red_card_minute ≠ goal_minute
player_count >= 7   (حداقل قانونی فوتبال)
```

---

## Q.8 Event Timing

**V1:** `event_minute ~ Uniform(current_minute, segment_end)`

**V2:** weighted distribution با peak در دقایق نزدیک ۴۵ و ۹۰.

**Ordering:**

```text
sort events by minute ascending
اولین splitting event → segment را می‌شکند
events بعد از آن minute → next sub-segment
```

---

## Q.9 Event Consistency Rules

```text
1.  Goals <= Shots                              ← همیشه
2.  Saves >= 0                                  ← همیشه
3.  Saves = Shots_opp - Goals - OffTarget       ← همیشه
4.  Q نمی‌تواند goal جدید بسازد                ← همیشه
5.  Q نمی‌تواند λ را بنویسد                    ← همیشه
6.  Red Card minute ≠ Goal minute               ← همیشه
7.  Event minutes ∈ [current_minute, seg_end)   ← همیشه
8.  Substitutions فقط در S3/S4                 ← V1/V2
9.  Max 3 substitutions per team per match      ← V1/V2
10. player_count >= 7                           ← همیشه
```

---

## Q.10 تفکیک V1 / V2 / V3

| Feature | V1 | V2 | V3 |
|---|---|---|---|
| Shot count | Goals + Poisson miss | همان | همان |
| xG per shot | یکسان (avg) | از shot quality | از position model |
| Save count | OffTarget Binomial | همان | همان |
| Yellow Card | Bernoulli ساده | + accumulation | + tactical intent |
| Red Card | split فقط | split + λ modifier | + dims recalc |
| Substitution | timing + count | + state-aware | + tactical formation |
| Event timing | Uniform | peaked near 45/90 | همان |
| Off-target rate | fixed prior | از tactical profile | از player + position |

---

# Section R — Player Attribution

> **Status:** LOCKED

---

## R.1 Contract

```text
INPUT:
    goal_events:    List[GoalEvent]    ← تعداد ثابت، تغییر نمی‌کند
    roster_home:    List[PlayerSeason]
    roster_away:    List[PlayerSeason]
    tactical_home:  TacticalProfile
    tactical_away:  TacticalProfile
    dims_home:      TeamDimensions
    dims_away:      TeamDimensions
    segment_state:  {state_home, state_away}
    rng:            SeededRNG

OUTPUT:
    List[AttributedGoalEvent] {
        minute, team, scorer, assist, xG_credit
    }

CAN_CREATE_GOAL?  NO
CAN_CHANGE_λ?     NO
CAN_CHANGE_STATE? NO
RANDOMNESS?       YES
```

$$\boxed{R \text{ فقط گل‌های موجود را به بازیکنان نسبت می‌دهد؛ هرگز گل جدید نمی‌سازد}}$$

---

## R.2 Scorer Pool

**V1:** `scorer_pool = roster.filter(role != GK)`

**V2:**

```text
if state == LEADING:
    scorer_pool = roster.filter(role in {FW, AM, CM})
else:
    scorer_pool = roster.filter(role != GK)
```

---

## R.3 Scorer Weight

$$w_{scorer}(p) = role\_attack\_weight(p.role) \times p.attack\_ability$$

```text
role_attack_weight:
FW  → 1.00
AM  → 0.75
WM  → 0.55
CM  → 0.40
FB  → 0.12
DM  → 0.15
CB  → 0.08
GK  → 0.00
```

**V2:**

$$w_{scorer}(p) = role\_attack\_weight \times attack\_ability \times positional\_bonus(p,\ tactical\_profile)$$

---

## R.4 Assist Pool و Weight

```text
assist_pool = scorer_pool.exclude(scorer)
```

$$w_{assist}(p) = role\_creation\_weight(p.role) \times p.creation\_ability$$

```text
role_creation_weight:
AM  → 1.00
WM  → 0.85
CM  → 0.80
FW  → 0.50
FB  → 0.35
DM  → 0.25
CB  → 0.08
```

$$P(assist\_exists) = 0.75 \quad \text{(prior V1)}$$

**V2:** از `possession_tendency` تیم می‌آید.

---

## R.5 xG Credit

**V1:** `xG_credit = xG_total / goals_count` (یکسان برای همه)

**V2:**

$$xG\_credit_i = \frac{xG_{shot\_quality_i}}{\sum_j xG_{shot\_quality_j}} \times xG_{total}$$

فقط برای آمار نمایشی — هیچ اثری روی λ ندارد.

---

## R.6 Multi-Goal Segments

```text
for each goal in segment_goals:
    scorer = weighted_random_sample(scorer_pool, weights, rng)
    assist = weighted_random_sample(
                 assist_pool.exclude(scorer), weights, rng
             ) if Bernoulli(0.75)
    attributed_goals.append(...)
```

هر sample مستقل است — یک بازیکن می‌تواند دو گل در یک segment بزند.

---

## R.7 Edge Cases

```text
1. Pool تک‌نفره:     scorer = آن بازیکن، assist = null
2. goals = 0:        R اجرا نمی‌شود
3. All weights = 0:  fallback = uniform random
4. Red Card active:  roster.filter(on_pitch == True)
```

---

## R.8 چیزی که R هرگز نمی‌کند

```text
🚫 گل جدید نمی‌سازد
🚫 تعداد گل را تغییر نمی‌دهد
🚫 λ را نمی‌خواند یا نمی‌نویسد
🚫 State را تغییر نمی‌دهد
🚫 MatchRuntime را مستقیم mutate نمی‌کند
   (فقط List[AttributedGoalEvent] برمی‌گرداند)
```

---

## R.9 تفکیک V1 / V2 / V3

| Feature | V1 | V2 | V3 |
|---|---|---|---|
| Scorer pool | همه‌ی outfield | + state filter | + fatigue filter |
| Scorer weight | role × ability | + positional bonus | + match form |
| Assist probability | fixed 0.75 | از possession tendency | از creation chain |
| xG credit | یکسان | از shot quality | از position model |
| On-pitch filter | NO | YES (Red Card) | YES + subs |

---

# Master Roadmap — وضعیت کامل پروژه

```text
[LOCKED] Sections 1–6   — Core Mathematical Architecture
[LOCKED] Section L      — Historical Team Hybrid Model
[LOCKED] Section M      — Calibration Methodology
[LOCKED] Section N      — Implementation Architecture + V1/V2/V3
[LOCKED] Section J/K    — Player Performance & Match Events (Contracts)
[LOCKED] Section O      — Data Contracts + Module Interfaces
[LOCKED] Section P      — Match Runtime Object
[LOCKED] Section Q      — Event Generator
[LOCKED] Section R      — Player Attribution

[NEXT]   Section S      — Full Simulation Engine
[AFTER]  Section T      — Calibration Implementation
[AFTER]  Production
```

---

## End of Checkpoint

**Architecture frozen through Section R.**

> **این موتور یک سیستم hybrid و causal برای شبیه‌سازی فوتبال تاریخی است که از PlayerSeason و Formation، Team Dimensions/Identity را می‌سازد؛ با Matchup Engine دو منبع M (organized attack) و T (transition threat) را استخراج می‌کند؛ آن‌ها را به λ تبدیل می‌کند؛ Home Advantage و Form را جداگانه اعمال می‌کند؛ سپس λ را با Dixon-Coles/Poisson به probability distribution و در نهایت به random game events تبدیل می‌کند، در حالی که state آینده می‌تواند از outcome فعلی تغییر کند بدون اینکه dependencyهای دوباره یا double-counting وارد مسیر λ شوند.**
