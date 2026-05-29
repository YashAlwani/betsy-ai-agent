# Constraints

---

## Technical Constraints
- **Time:** 5-week school project timeline (iterative implementation required)
- **Complexity:** Must be demonstrable/testable within academic context (likely simulated integrations)
- **Infrastructure:** No access to real procurement systems (requires mock data and APIs)
- **Scale:** Small manufacturing company context (10-50 SKUs, 5-10 suppliers realistic scope)
- **Integration:** Email, inventory systems, supplier APIs must be mocked or stubbed

---

## Functional Constraints
- **Autonomy boundaries:** Agent cannot operate completely unsupervised (human approval workflow required)
- **Financial limits:** Maximum autonomous spend amount must be defined
- **Supplier limitations:** Pre-approved supplier list (agent doesn't find new suppliers autonomously)
- **Scope boundaries:** Focus on material procurement, not services/contracts/capital equipment

---

## Performance Constraints
- **Success metrics:** Must prevent 2+ stockouts, catch 1+ invoice error, achieve 95%+ approval rate
- **Response time:** Stockout detection must occur with enough lead time for delivery
- **Learning speed:** Agent must show improvement within demonstration timeframe (5-10 decisions)

---

## Safety Constraints
- **No catastrophic decisions:** Safeguards must prevent scenarios like ordering 1000x quantity, selecting unapproved suppliers, exceeding budget by orders of magnitude
- **Reversibility:** Bad decisions must be identifiable and correctable
- **Escalation:** Edge cases beyond agent capability must escalate to human
- **Transparency:** All decisions must be explainable to stakeholders

---

## Ethical Constraints
- **Fairness:** No bias toward/against suppliers based on non-business factors
- **Privacy:** Business data must be handled appropriately (in real deployment)
- **Accountability:** Clear audit trail for every autonomous decision
- **Human oversight:** Humans remain accountable for agent actions

---

## Educational Constraints
- **Documentation required:** Decision log must track research, choices, failures, pivots
- **Demonstration required:** Must show working system with realistic scenarios
- **Learning objective:** Understanding autonomous agent architecture, not just implementation
- **Reflection required:** Ethics section on safeguards and what could go wrong
