"""Financial literacy modules — structured lessons with objectives, examples, and exercises."""

LITERACY_MODULES = [
    {
        "id": "architect-not-engine",
        "title": "You Are the Architect, Not the Engine",
        "order": 1,
        "summary": "Learn the difference between trading hours for money and building a system that runs without you.",
        "uses_profile": False,
        "objectives": [
            "Define architect vs engine in your own business",
            "Spot when income is tied to your presence (the presence ceiling)",
            "Name one system you will build this month instead of working harder",
        ],
        "sections": [
            {
                "title": "The core idea",
                "content": (
                    "When you are self-employed, it is easy to become the **engine** — every dollar requires "
                    "your time. An **architect** designs rules, accounts, and habits so money moves correctly "
                    "even on tired days.\n\n"
                    "This app is the blueprint. You decide the rules; the tools enforce the math."
                ),
            },
            {
                "title": "Presence ceiling",
                "content": (
                    "If income drops to **zero** when you stop working for a week, you have a presence ceiling. "
                    "That is not failure — it is Stage 1 reality. The fix is not motivation; it is **systems**: "
                    "cash-flow splits, a Stability Fund, then productized income."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Maya earns **$6,000/mo** freelancing. She works 160 hours → **$37.50/hour**. "
            "She takes two weeks off unpaid → income **$3,000** that month. She is the engine.\n\n"
            "**Architect move:** Automate 15/65/20 on every deposit, fund 4 months of essentials ($12,000 if "
            "essentials are $3,000), then raise her rate or productize one offer so some revenue does not require daily hours."
        ),
        "exercise": {
            "title": "Do this now (5 minutes)",
            "steps": [
                "Write your average monthly gross income.",
                "Estimate: if you stopped working for 14 days, what would income be?",
                "Circle one task you repeat every week that could become a checklist, template, or automated rule.",
            ],
        },
        "reflection": [
            "Where am I still the engine instead of the architect?",
            "What one system would protect me on my worst motivation week?",
        ],
        "key_point": "Freedom grows when rules run the money — not when you try harder.",
    },
    {
        "id": "156520",
        "title": "The 15/65/20 Rule",
        "order": 2,
        "summary": "Learn to split every dollar into Future, Essentials, and Life — before you spend.",
        "uses_profile": True,
        "objectives": [
            "Calculate the three buckets from gross monthly income",
            "Explain why Essentials must stay near 65% of gross",
            "Assign a specific job to each Future dollar",
        ],
        "sections": [
            {
                "title": "The three buckets",
                "content": (
                    "**15% Future** — Stability Fund, debt above ~7–8% APR, investments, business assets.\n\n"
                    "**65% Essentials** — Rent, utilities, insurance, minimum debt payments, core business costs.\n\n"
                    "**20% Life** — Discretionary: dining, hobbies, non-urgent upgrades. Use the 72-hour pause here."
                ),
            },
            {
                "title": "Why pre-decide?",
                "content": (
                    "Without labels, money feels available and leaks to Life. Pre-deciding removes daily negotiation. "
                    "If Essentials are **above 65%** of gross, you are structurally fragile — cut Life or raise income "
                    "before chasing investments."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Gross income **$4,800/mo**.\n\n"
            "- Future (15%): **$720**\n"
            "- Essentials (65%): **$3,120**\n"
            "- Life (20%): **$960**\n\n"
            "If actual essentials are $3,400, you are **$280 over** the bucket — that overrun usually came from Life "
            "or unlabeled spending. Fix the label, not your willpower."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Use your profile income (shown below when available) or write your gross monthly income.",
                "Multiply by 0.15, 0.65, and 0.20 — write all three amounts.",
                "List where this month's Future $ will go (Stability Fund %, debt, etc.).",
            ],
        },
        "reflection": [
            "Which bucket leaked last month — Life or unlabeled Essentials?",
            "What is one bill you will reclassify as Essential vs Life?",
        ],
        "key_point": "Every dollar gets a job before it arrives.",
    },
    {
        "id": "stability-fund",
        "title": "Stability Fund (3–6 Months)",
        "order": 3,
        "summary": "Build a shock absorber using Essentials only — not total spending.",
        "uses_profile": True,
        "objectives": [
            "Calculate your Stability Fund target in dollars",
            "Track percent funded and months remaining at your Future allocation",
            "Explain why this fund comes before investing or arbitrage",
        ],
        "sections": [
            {
                "title": "What counts as Essentials",
                "content": (
                    "Use **monthly Essentials** from your intake — survival + non-negotiable business costs. "
                    "Do **not** include Life bucket spending in the target."
                ),
            },
            {
                "title": "Target range",
                "content": (
                    "**3 months** minimum if income is steady and low debt.\n"
                    "**4–6 months** if income is variable, you have dependents, or high-interest debt.\n\n"
                    "Fund from the **Future 15%** until 100%. This is retention before earning."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Essentials **$2,800/mo**, target **4 months** → **$11,200** Stability Fund.\n\n"
            "Future bucket **$600/mo** from 15/65/20 on $4,000 income → **~19 months** to fill from zero. "
            "Raise income or temporarily shift Life → Future to shorten that timeline."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Essentials × target months = your dollar target.",
                "Current balance ÷ target = percent funded.",
                "Set one automatic or calendar reminder to move Future money on payday.",
            ],
        },
        "reflection": [
            "What emergency would this fund prevent you from panic-deciding?",
            "What would you stop doing if the fund were full?",
        ],
        "key_point": "Cushion before leverage. No fund, no sovereignty.",
    },
    {
        "id": "stages",
        "title": "The Wealth Stages",
        "order": 4,
        "summary": "Learn the mandatory sequence: Stability → Skill Stacking → Assets → Sovereignty.",
        "uses_profile": True,
        "objectives": [
            "Name all four stages and their exit criteria",
            "Identify your current stage from your numbers",
            "Explain why skipping stages increases risk",
        ],
        "sections": [
            {
                "title": "Stage 1 — Stability",
                "content": "Exit when Stability Fund = **100%** of target (3–6 months Essentials). Focus: 15/65/20, debt snowball on high APR.",
            },
            {
                "title": "Stage 2 — Skill Stacking",
                "content": "Exit when **income per hour** rises **20%+** vs your baseline. Focus: pricing, offers, skills that multiply revenue without more hours.",
            },
            {
                "title": "Stage 3 — Asset Acquisition",
                "content": "Exit when you hold **≥1 asset** with positive spread (yield > cost of capital + friction). Focus: systems, IP, cash-flowing tools — not more hustle.",
            },
            {
                "title": "Stage 4 — Sovereignty",
                "content": "Passive + asset yield covers **100% of Essentials**. Focus: maintenance, legacy planning, optional advanced strategies.",
            },
        ],
        "worked_example": (
            "**Example:** Jordan is at **62%** Stability Fund funded → still **Stage 1**. "
            "Opening a high-velocity flip before the fund is full adds stress, not wealth. "
            "The app keeps advanced modules locked until the sequence says you are ready."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Check Command Center → Your Stage.",
                "Write the single next mechanical action shown there.",
                "List one tempting shortcut you will delay until the stage exit criteria are met.",
            ],
        },
        "reflection": [
            "Which stage am I trying to skip emotionally?",
            "What would finishing my current stage unlock?",
        ],
        "key_point": "Sequence is risk management — not bureaucracy.",
    },
    {
        "id": "self-trust",
        "title": "Self-Trust and Integrity",
        "order": 5,
        "summary": "Learn how keeping small promises to yourself builds economic trust.",
        "uses_profile": False,
        "objectives": [
            "Define Self-Trust vs credit bureau scores",
            "Set one measurable weekly commitment",
            "Use Kept/Missed check-ins honestly",
        ],
        "sections": [
            {
                "title": "Why self-trust matters",
                "content": (
                    "Lenders and partners trust **patterns**. The Integrity Engine tracks whether you keep "
                    "promises to yourself — pause rule, learning block, wake time. This is private and for **you**, "
                    "not a FICO replacement."
                ),
            },
            {
                "title": "How to build it",
                "content": (
                    "Pick **one** small commitment you can hit 80% of weeks. Weekly check-in: Kept or Missed — no excuses, "
                    "just data. Consistency beats intensity; restarting after a miss counts as strength."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Commitment: \"No Life-bucket purchase over $75 without starting a Fork Moment pause.\" "
            "Four Kept weeks → Self-Trust Index rises. One Miss without hiding it → still better than quitting tracking."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Open Your Integrity → add one commitment.",
                "Choose a check-in day (e.g. Sunday evening).",
                "Tell one accountability partner the rule (optional but powerful).",
            ],
        },
        "reflection": [
            "What promise have I broken to myself most often?",
            "What commitment is small enough to keep this week?",
        ],
        "key_point": "External trust starts with internal follow-through.",
    },
    {
        "id": "consumer-operator",
        "title": "Consumer vs Operator Mindset",
        "order": 6,
        "summary": "Learn to label emotional spending and use the 72-hour pause.",
        "uses_profile": False,
        "objectives": [
            "Distinguish consumer vs operator purchases",
            "Name your top three emotional spending triggers",
            "Practice the Fork Moment flow once",
        ],
        "sections": [
            {
                "title": "Definitions",
                "content": (
                    "**Consumer spend:** status, boredom, comfort, social pressure — often invisible until the statement arrives.\n\n"
                    "**Operator spend:** tools, skills, assets, health — purchases that increase capacity or cash flow."
                ),
            },
            {
                "title": "The 72-hour pause",
                "content": (
                    "Life-bucket non-essentials get a **72-hour lock**. Acknowledge the emotion (stress, boredom, etc.), "
                    "then decide as the architect. Essentials and Future are exempt — this targets impulse, not survival."
                ),
            },
        ],
        "worked_example": (
            "**Example:** $220 headphones after a hard week — **consumer** unless required for paid work. "
            "Start Fork Moment → label **comfort** → wait 72h → often the urge passes or you buy with intention."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Review last week's Life spending — mark each C (consumer) or O (operator).",
                "Start a practice Fork Moment on Command Center (even for a hypothetical item).",
                "Write: \"Are you trying to convince yourself?\" — answer honestly for one recent purchase.",
            ],
        },
        "reflection": [
            "Which emotion drives most of my unplanned spending?",
            "What operator purchase would actually move my stage forward?",
        ],
        "key_point": "Awareness before restriction — train the operator, don't punish the human.",
    },
    {
        "id": "credit-utilization",
        "title": "Credit Utilization — The Fast Lever",
        "order": 7,
        "summary": "Learn how utilization is calculated and how to lower it before applying for credit.",
        "uses_profile": True,
        "objectives": [
            "Calculate utilization on a single card and overall",
            "Set a target under 30% (10% before major applications)",
            "Order paydowns by utilization, not just balance",
        ],
        "sections": [
            {
                "title": "The formula",
                "content": (
                    "**Utilization %** = balance ÷ credit limit × 100.\n\n"
                    "Scores react to **overall** and **per-card** utilization. One maxed card hurts even if others are empty."
                ),
            },
            {
                "title": "Tactics",
                "content": (
                    "Pay **before statement close** so the reported balance is lower.\n"
                    "Pay highest utilization cards first.\n"
                    "Request limit increases only after 6+ on-time months — do not spend into the new limit."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Card A: $400 / $1,000 = **40%**. Card B: $200 / $5,000 = **4%**. "
            "Overall: $600 / $6,000 = **10%** — but Card A still drags scores. Pay A down to **$100** first."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "List each card: balance, limit, utilization %.",
                "Circle the highest utilization card — that is paydown #1.",
                "Set a calendar alert 3 days before each statement close.",
            ],
        },
        "reflection": [
            "Which card is hurting me most per utilization, not balance?",
            "What payment can I make this week?",
        ],
        "key_point": "Utilization is a speedometer — lower it before you ask for new credit.",
    },
    {
        "id": "credit-disputes",
        "title": "Cleaning Your Credit Report",
        "order": 8,
        "summary": "Learn the lawful dispute process — accuracy first, never lie to bureaus.",
        "uses_profile": False,
        "objectives": [
            "Pull free reports from the official source",
            "Separate inaccurate vs accurate negative items",
            "Draft a dispute timeline with document retention",
        ],
        "sections": [
            {
                "title": "Get your reports",
                "content": (
                    "Use **AnnualCreditReport.com** (official free source). Review all three bureaus. "
                    "Highlight items that are **wrong** (wrong balance, not yours, duplicate, outdated)."
                ),
            },
            {
                "title": "Dispute process",
                "content": (
                    "Dispute **inaccurate** items in writing with the bureau — include copies, not originals. "
                    "For **valid** collections, consider **pay-for-delete** in writing before paying. "
                    "Keep a log: date sent, response, outcome."
                ),
            },
        ],
        "worked_example": (
            "**Example:** A paid medical bill still shows \"open collection\" — inaccurate status. "
            "Dispute with proof of payment. Do **not** dispute a valid $800 card you still owe — pay or settle instead."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Schedule 30 minutes to pull one bureau report.",
                "Mark each negative: Accurate / Inaccurate / Unsure.",
                "Create a folder (digital or paper) for dispute letters and responses.",
            ],
        },
        "reflection": [
            "Which item on my report is actually inaccurate vs just painful?",
            "What proof do I already have in email or bank records?",
        ],
        "key_point": "Accuracy first — disputing honest debts is fraud and wastes time.",
    },
    {
        "id": "loan-readiness",
        "title": "Loan Readiness (DTI & Documentation)",
        "order": 9,
        "summary": "Learn what lenders measure and prepare documentation for acquisition debt only.",
        "uses_profile": True,
        "objectives": [
            "Calculate debt-to-income (DTI) ratio",
            "List standard self-employed documentation",
            "Reject ego debt — acquisition only",
        ],
        "sections": [
            {
                "title": "DTI",
                "content": (
                    "**DTI** = total monthly debt payments ÷ gross monthly income.\n\n"
                    "Many business lenders prefer **under 43%**. Lower is better. Use gross income from tax returns, not volatile month."
                ),
            },
            {
                "title": "Documentation pack",
                "content": (
                    "Prepare: 2 years tax returns, YTD profit & loss, 3–6 months bank statements, "
                    "debt schedule, and a **written use of funds** tied to an asset that cash-flows."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Gross **$8,000/mo**, debt payments **$2,400/mo** → DTI **30%**. "
            "Use of funds: equipment that increases billable output — not a luxury vehicle."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Add monthly minimum payments on all debts.",
                "Divide by gross monthly income → your DTI.",
                "Write one sentence: \"Loan would buy ___ which pays back via ___.\"",
            ],
        },
        "reflection": [
            "Is my DTI problem income or debt?",
            "Would this loan still make sense if revenue dropped 20%?",
        ],
        "key_point": "Acquisition debt for cash-flowing assets — never ego.",
    },
    {
        "id": "lifestyle-trap",
        "title": "The Lifestyle Trap (Feast or Famine)",
        "order": 10,
        "summary": "Learn why raising prices or landing big clients fails if Essentials creep with revenue.",
        "uses_profile": True,
        "objectives": [
            "Define lifestyle creep for variable income",
            "Calculate your Gap (income minus Essentials)",
            "Set a rule for the next revenue increase",
        ],
        "sections": [
            {
                "title": "Operator vs employee raise",
                "content": (
                    "W-2 workers often get gradual raises. **Self-employed operators** get spikes — a $10k month, then $4k. "
                    "The trap: upgrading rent, gear, or subscriptions in the good month, then bleeding in the slow month."
                ),
            },
            {
                "title": "Anchor Essentials",
                "content": (
                    "When gross revenue rises, **do not** raise Essentials bucket automatically. "
                    "Route the delta to Future (15%) until Stability Fund is full, then assets or tax reserves."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Revenue jumps **$5,000 → $7,500/mo**. Essentials stay **$3,200**. "
            "Gap widens by **$2,300** — architect move: **$345** to Future (15% of raise), not a new truck payment."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Income − Essentials = your Gap (write the number).",
                "Name the last purchase that was really lifestyle creep.",
                "Write: \"When revenue rises $500, Future gets $___ before Life upgrades.\"",
            ],
        },
        "reflection": [
            "What would my Essentials be if I cut status spending only?",
            "Am I building wealth or polishing a prison?",
        ],
        "key_point": "Raises fund systems first — not bigger bills.",
    },
    {
        "id": "productizing-knowledge",
        "title": "Productizing Knowledge",
        "order": 11,
        "summary": "Learn to turn client work into products that earn without your hourly presence.",
        "uses_profile": True,
        "objectives": [
            "Distinguish hourly work vs productized offers",
            "Draft one fixed-scope offer with a price",
            "Estimate revenue per hour if the product sells",
        ],
        "sections": [
            {
                "title": "The presence ceiling",
                "content": (
                    "If every dollar needs your calendar, income stops when you stop. **Productizing** means packaging "
                    "a repeated client outcome into a template, course, retainer scope, or automated deliverable."
                ),
            },
            {
                "title": "Start small",
                "content": (
                    "Pick the task you do most often. Fix the scope and price (not \"$150/hr\" but \"$1,200 website in 5 days\"). "
                    "That is Skill Stacking → Asset Acquisition bridge work."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Consultant bills **$125/hr**, 12 hrs/project = **$1,500**. "
            "Productized audit **$997** takes **4 hrs** if templated → **$249/hr** effective density."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "List your three most repeated client deliverables.",
                "Pick one; write fixed scope + fixed price.",
                "Calculate $/hour if you deliver it in half the time next month.",
            ],
        },
        "reflection": [
            "Which client work do I resent because it does not scale?",
            "What would I sell if I could not bill hourly anymore?",
        ],
        "key_point": "Products decouple revenue from your calendar.",
    },
    {
        "id": "operator-cash-flow",
        "title": "Operator Cash Flow (SE Tax + Profit First)",
        "order": 12,
        "summary": "Learn how business revenue becomes owner pay, tax reserves, and personal 15/65/20.",
        "uses_profile": True,
        "objectives": [
            "Separate business deposits from owner pay",
            "Explain SE tax vs W-2 withholding",
            "Map Profit First buckets to personal Future/Life",
        ],
        "sections": [
            {
                "title": "Two layers",
                "content": (
                    "**Business layer:** Revenue → Profit, Tax, Owner Pay, OpEx (Profit First).\n\n"
                    "**Personal layer:** Owner Pay → 15/65/20 (Future, Essentials, Life).\n\n"
                    "Never treat gross client deposits as spendable personal income."
                ),
            },
            {
                "title": "SE tax reality",
                "content": (
                    "Net profit triggers **self-employment tax** (~15.3% on net up to SS cap, plus income tax). "
                    "Your **Tax %** bucket exists because no employer withholds for you."
                ),
            },
        ],
        "worked_example": (
            "**Example:** **$10,000** business revenue → Tax **15%** ($1,500), Owner Pay **50%** ($5,000), OpEx **30%**, Profit **5%**. "
            "Owner Pay **$5,000** → Future **$750**, Essentials **$3,250**, Life **$1,000**."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Open intake Step 5 — confirm Profit/Tax/Owner Pay/OpEx %.",
                "On next deposit, split on paper before spending.",
                "Ask Advisor: \"How much should I set aside for taxes?\" with your numbers loaded.",
            ],
        },
        "reflection": [
            "Am I spending client money before allocating tax?",
            "What % owner pay do I actually need to cover Essentials?",
        ],
        "key_point": "Business buckets first — then personal 15/65/20.",
    },
    {
        "id": "seven-habits-operators",
        "title": "The 7 Habits for Self-Employed Operators",
        "order": 13,
        "summary": "Apply Stephen Covey's principles to variable income, client chaos, and building systems — not corporate HR.",
        "uses_profile": False,
        "objectives": [
            "Practice Habit 1 — proactive language and Circle of Influence",
            "Schedule Quadrant II work in Creation Hour (Habit 3)",
            "Connect Character Ethic to Integrity and reputation in your business",
            "Shift paradigm from employee to architect (Habit 2 + paradigm work)",
        ],
        "sections": [
            {
                "title": "Habit 1 — Be Proactive",
                "content": (
                    "Markets, clients, and algorithms are **Circle of Concern**. Your prices, outreach, "
                    "bookkeeping, Stability Fund transfers, and templates are **Circle of Influence**.\n\n"
                    "Reactive: \"Clients are slow this month — I can't save.\"\n"
                    "Proactive: \"I will send five follow-ups and cut one Life subscription today.\""
                ),
            },
            {
                "title": "Habit 2 — Begin with the End in Mind",
                "content": (
                    "Define sovereignty: *Essentials covered without daily grind; tax current; one productized offer.* "
                    "Every yes to a bad client or impulse buy is a vote against that end."
                ),
            },
            {
                "title": "Habit 3 — Put First Things First (Quadrant II)",
                "content": (
                    "- **Quadrant I** (urgent + important): client fires — necessary but exhausting.\n"
                    "- **Quadrant II** (not urgent + important): systems, learning, outreach — where wealth is built.\n"
                    "- **Quadrant III & IV:** interruptions and busywork — minimize.\n\n"
                    "Operators live in Quadrant I until they block **Quadrant II** — Creation Hour is your QII appointment."
                ),
            },
            {
                "title": "Character Ethic vs Personality Ethic",
                "content": (
                    "**Personality ethic:** look successful on social, hustle culture, fake urgency.\n"
                    "**Character ethic:** keep promises, fund tax, deliver work, pause before Life splurges.\n\n"
                    "Your Integrity Score tracks character — not performance for strangers."
                ),
            },
            {
                "title": "Paradigm Shift — Employee to Architect",
                "content": (
                    "Old lens: \"I need a paycheck this week.\"\n"
                    "New lens: \"I need a machine that funds Essentials even when I rest.\"\n\n"
                    "That shift is why this app enforces stages, 15/65/20, and Fork Moments."
                ),
            },
            {
                "title": "Habit 7 — Sharpen the Saw",
                "content": (
                    "You are the production asset. Sleep, skill practice, and recovery are **OpEx on yourself** — "
                    "not laziness. Burned-out operators underprice and overspend."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Sam blocks **7–9 AM** daily (Quadrant II): one hour productizing a client checklist, "
            "30 min outreach. Reactive Sam checked email from bed and stayed in Quadrant I all day. "
            "After 6 weeks, Sam launches a **$497** fixed offer — proactive, not lucky."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Write one proactive sentence for this week's money goal (\"I will…\").",
                "Block one recurring Creation Hour on your calendar — label it Quadrant II.",
                "Add one Integrity commitment that proves character (not image).",
                "Write 3 sentences: your \"end in mind\" sovereignty picture.",
            ],
        },
        "reflection": [
            "Where am I blaming the market instead of adjusting my offer?",
            "What Quadrant II task have I avoided for 30+ days?",
            "What paradigm shift would make my biggest money problem obvious?",
        ],
        "key_point": "Principles first — then profit. Covey's habits are the operating system; 15/65/20 is the finance layer.",
    },
    {
        "id": "esbi-operators",
        "title": "Cashflow Quadrant (ESBI) for Operators",
        "order": 14,
        "summary": "Learn Rich Dad's E-S-B-I model — where you earn today vs where you're building toward.",
        "uses_profile": True,
        "objectives": [
            "Name the four quadrants and left vs right side economics",
            "Identify your primary quadrant and income mix",
            "Choose one S→B or B→I move aligned with your Wealth Stage",
        ],
        "sections": [
            {
                "title": "The four quadrants",
                "content": (
                    "**E — Employee:** paycheck for time.\n"
                    "**S — Self-employed:** you are the business; stop working → income stops.\n"
                    "**B — Business owner:** you own a system that runs without daily you.\n"
                    "**I — Investor:** assets generate cash flow.\n\n"
                    "**Left (E+S)** trades time. **Right (B+I)** uses systems and capital."
                ),
            },
            {
                "title": "Operators usually start at S",
                "content": (
                    "Freelancers, contractors, and solopreneurs are **S** even with high income. "
                    "The goal is not to shame S — it is to **fund Stability**, then **productize into B**, "
                    "then allocate Future bucket toward **I**."
                ),
            },
            {
                "title": "Mapped to your Wealth Stages",
                "content": (
                    "- **Stability / Skill Stacking:** strengthen S, begin B moves (templates, fixed offers).\n"
                    "- **Asset Acquisition:** B systems + first I assets (positive spread).\n"
                    "- **Sovereignty:** I income covers essentials."
                ),
            },
        ],
        "worked_example": (
            "**Example:** Jordan is **S** — $8k/mo consulting, 100% hourly. Target **B** → launches "
            "**$2,500** fixed-scope audit product; 40% of revenue from product within 6 months. "
            "Still S-heavy but **B income mix** begins. At **Asset Acquisition**, Jordan adds a cash-flowing tool subscription (**I path**)."
        ),
        "exercise": {
            "title": "Do this now",
            "steps": [
                "Confirm primary quadrant in intake (Step 1).",
                "Estimate income mix % from E, S, B, I (rough is fine).",
                "Read Command Center ESBI badge — note your target quadrant.",
                "Write one action this month that shifts mix 5% toward the right side.",
            ],
        },
        "reflection": [
            "Am I pretending to be B while still billing only hours?",
            "What asset or system could earn once while I sleep?",
        ],
        "key_point": "Quadrant is how income is structured — not your job title. Move right with systems.",
    },
]


def get_modules() -> list[dict]:
    return sorted(LITERACY_MODULES, key=lambda m: m["order"])


def get_module(module_id: str) -> dict | None:
    for m in LITERACY_MODULES:
        if m["id"] == module_id:
            return m
    return None
