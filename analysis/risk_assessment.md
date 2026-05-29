# Risk Assessment & Mitigation

---

## High-Risk Scenarios

### 1. Agent makes $50,000 mistake
- **Mitigation:** Maximum autonomous spend limit ($5k-10k), human approval for high-value transactions

### 2. Agent selects wrong supplier causing production shutdown
- **Mitigation:** Delivery time evaluation, reliability scoring, buffer time in stockout detection

### 3. Agent exhibits supplier bias
- **Mitigation:** Regular bias audits, diverse supplier scoring factors, fairness checks

### 4. Agent misses duplicate invoice
- **Mitigation:** Multiple duplicate detection strategies, invoice pattern matching

### 5. Edge case causes infinite loop or crash
- **Mitigation:** Timeout mechanisms, error handling, escalation workflows

---

## Medium-Risk Scenarios

### 1. Agent makes sub-optimal decisions (penny-wise, pound-foolish)
- **Mitigation:** Learning from outcomes, EV-style calculations including shutdown costs

### 2. Supplier out of stock not detected
- **Mitigation:** Availability checking before PO generation, failover logic

### 3. Budget drift over time
- **Mitigation:** Running budget tracking, alerts at 80% threshold
