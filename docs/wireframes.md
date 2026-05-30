# Betsy — Wireframes

Two design directions explored. The first is a standalone dashboard for Jenny.
The second (current direction) follows enterprise AI tool patterns — AI as a layer on top of familiar data surfaces.

---

## Version 1 — Standalone Dashboard (4 screens)
*Pattern: dedicated app with sidebar navigation*

### Screen 1 — Home
```
┌─────────────────────────────────────────────────────────────┐
│  🤖 Betsy                              Last checked: 2m ago  │
│  "I'm keeping an eye on things."                            │
├──────────────┬──────────────┬──────────────────────────────-┤
│  ⚠️  1        │  ✅  3        │  🚨  0                        │
│  Need your   │  Handled     │  Critical                     │
│  approval    │  automatically│  alerts                      │
│  [Review →]  │              │                               │
├──────────────┴──────────────┴───────────────────────────────┤
│  RECENT ACTIVITY                                            │
│  ─────────────────────────────────────────────────────────  │
│  ✅ Ordered 500x Steel Bolts M8 from FastParts Co.  3h ago  │
│  ✅ Ordered 200x Hydraulic Seals from QuickShip     6h ago  │
│  ⚠️  Price spike on Copper Wire — waiting for you   8h ago  │
└─────────────────────────────────────────────────────────────┘
```

### Screen 2 — Pending Approvals (HITL core)
```
┌─────────────────────────────────────────────────────────────┐
│  ← Back       YOUR APPROVAL NEEDED        1 item            │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ⚠️  Copper Wire — price looks unusual                │  │
│  │                                                       │  │
│  │  What's happening                                     │  │
│  │  The usual price is €4.20/m. Today all suppliers     │  │
│  │  are quoting €6.80–€7.10/m — 60% higher than normal.│  │
│  │                                                       │  │
│  │  What I'd normally do                                 │  │
│  │  Order 300m from BulkSupply Co. for €2,040 total.   │  │
│  │                                                       │  │
│  │  Why I'm asking you instead                          │  │
│  │  This kind of jump usually means a market issue or  │  │
│  │  a data error. You know better than I do.           │  │
│  │                                                       │  │
│  │  Betsy's confidence: ████░░░░  55%                  │  │
│  │                                                       │  │
│  │  [  ✅ Yes, go ahead  ]    [  ❌ No, skip this  ]   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Screen 3 — Agent Log
```
┌─────────────────────────────────────────────────────────────┐
│  ← Back       WHAT BETSY DID                 Last 7 days    │
├─────────────────────────────────────────────────────────────┤
│  Today                                                      │
│  ─────────────────────────────────────────────────────────  │
│  ✅  10:14   Ordered Steel Bolts M8                        │
│              500 units · FastParts Co. · €90               │
│              "Stock was running low (2 days left)."  [+]   │
│                                                             │
│  ⚠️  08:30   Flagged for your review — Copper Wire         │
│              Price 60% above normal · Waiting on you  [+]  │
│                                                             │
│  Yesterday                                                  │
│  ─────────────────────────────────────────────────────────  │
│  ✅  16:02   Ordered Hydraulic Seals                       │
│  🔴  14:55   Flagged duplicate invoice — INV-2024-0291     │
└─────────────────────────────────────────────────────────────┘
```

### Screen 4 — Supplier Scoreboard
```
┌─────────────────────────────────────────────────────────────┐
│  ← Back       SUPPLIERS                                     │
├─────────────────────────────────────────────────────────────┤
│  SUPPLIER            TRACK RECORD    SPEED     LAST ORDER   │
│  ─────────────────────────────────────────────────────────  │
│  FastParts Co.       ●●●●○  Good     2 days    3h ago       │
│  QuickShip Express   ●●●●●  Great    1 day     Yesterday    │
│  BulkSupply Co.      ●●●○○  OK       5 days    2 weeks ago  │
│  PrecisionParts      ●●●●○  Good     3 days    ⚠️ Invoice!   │
│  ValueFirst          ●●○○○  Slow     7 days    1 month ago  │
└─────────────────────────────────────────────────────────────┘
```

---

## Version 2 — Enterprise AI Layer (current direction)
*Pattern: AI as a layer on top of familiar data surfaces*
*References: Salesforce Einstein, Microsoft Copilot, Tableau Pulse, Glean*

Key patterns used:
- **AI command bar** — ⌘K prompt at the top for natural language input
- **AI narrative** — auto-generated plain English summary of current state
- **AI-scored tables** — data tables with one ✦-marked AI column
- **Inline approvals** — HITL cards embedded in the same surface, not a separate app

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ✦ Betsy           [⌘K  Ask Betsy something...]          ● Active      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ ✦ AI SUMMARY                                        2 min ago    │ │
│  │                                                                   │ │
│  │ "Steel Bolts and Hydraulic Seals were both critically low.        │ │
│  │  I ordered both automatically. Copper Wire pricing is 60%        │ │
│  │  above normal — I flagged it for you rather than ordering."      │ │
│  │                                                                   │ │
│  │ [✋ Review Copper Wire]   [📋 View full log]                     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Quick actions:  [⚡ Restock critical]  [🔍 Check invoices]  [📊 Report]│
│                                                                         │
│  INVENTORY                                            ✦ AI Risk column │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Item                 Stock     Days left   ✦ Risk      Action   │ │
│  │  ───────────────────────────────────────────────────────────────  │ │
│  │  Steel Bolts M8       240 pcs   2 days      ● Critical  Ordered  │ │
│  │  Hydraulic Seals      15 pcs    1 day       ● Critical  Ordered  │ │
│  │  Copper Wire          890 m     7 days      ◐ Watch     Flagged  │ │
│  │  Aluminium Sheet      3200 pcs  26 days     ○ Good      —        │ │
│  │  O-Ring Seals         5500 pcs  45 days     ○ Good      —        │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  SUPPLIERS                                         ✦ Betsy Score column │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Supplier             ✦ Score      Speed    Last used   Status   │ │
│  │  ───────────────────────────────────────────────────────────────  │ │
│  │  QuickShip Express    ●●●●●        1 day    Today       ✓ Good   │ │
│  │  FastParts Co.        ●●●●○        2 days   Today       ✓ Good   │ │
│  │  PrecisionParts       ●●●●○        3 days   2w ago      ⚠ Invoice│ │
│  │  BulkSupply Co.       ●●●○○        5 days   2w ago      ✓ Good   │ │
│  │  ValueFirst           ●●○○○        7 days   1m ago      ✓ OK     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  NEEDS YOUR OK  (1 pending)                                             │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  ⚠ Copper Wire · BulkSupply Co. · 300m · €2,040                 │ │
│  │  Price is 60% above the 30-day average. Confidence: ●●○○○       │ │
│  │  "All suppliers are quoting unusually high. Could be a market    │ │
│  │   spike — you know better than I do."                            │ │
│  │  [✅ Yes, go ahead]    [❌ Skip this]                             │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Design Principles Applied

| Principle | How Betsy applies it |
|---|---|
| AI is a layer, not a separate app | Betsy sits on top of inventory/supplier data, doesn't replace it |
| Outputs short and actionable | Narrative is 2–3 sentences, every section has a button |
| Clear "generated by AI" signal | ✦ mark on all AI-produced columns and cards |
| Familiar work surfaces | Tables look like any procurement table — one column is AI |
| Confidence visible | ●●●○○ dots on every AI-generated recommendation |

---

*Referenced by: dashboard/betsy.html (implementation), docs/user_requirements.md*
