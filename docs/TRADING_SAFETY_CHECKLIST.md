# Trading Safety Checklist

## 1. Purpose

This checklist defines the operational verification steps required to ensure that the trading platform is functioning safely.

The checklist should be used:

- before enabling live trading
- after system deployment
- during daily operational reviews
- after incidents or unexpected trading behavior

The objective is to detect problems early and prevent unsafe trading activity.

---

# 2. Daily Pre-Trading Checks

These checks should be performed **before automated trading is allowed to run**.

### 2.1 System Health

Verify that the API service is running correctly.

Check:

- API process running
- database connectivity
- scheduler thread active
- no crash loops in logs

Key logs:


auto-pick-scheduler started
scheduler tick executed


---

### 2.2 Scheduler Status

Confirm that the internal scheduler is running.

Verify:

- scheduler thread exists
- ticks occur at expected interval
- advisory lock is functioning

Expected behavior:


_scheduler_loop running
_auto_pick_tick_once_with_lock executed


---

### 2.3 Kill Switch Status

Verify that the trading kill switch is set correctly.

Check:


trading_enabled:{tenant_id}


Possible states:

| State | Meaning |
|------|------|
| false | trading disabled |
| true | trading allowed |

During maintenance or uncertainty, trading must remain disabled.

---

### 2.4 Broker Connectivity

Confirm broker connections are operational.

Check:

- Binance API connectivity
- IBKR bridge availability
- credential validity
- account permissions

Verify using status endpoints:


get_binance_account_status
get_ibkr_account_status


---

### 2.5 Balance Synchronization

Confirm internal balance assumptions match broker state.

Check:

- account balances
- available margin
- recent fills
- no unexpected open orders

If discrepancies exist, trading should remain disabled.

---

### 2.6 Open Positions Review

Inspect current open positions.

Verify:

- expected positions only
- no duplicate positions
- no unexpected exposure
- no orphan positions

Cross-check:


internal Position table
broker positions


---

# 3. Daily Operational Monitoring

These checks should be performed periodically while trading is active.

---

### 3.1 Scheduler Execution

Confirm that scheduler ticks continue executing.

Monitor logs for:


auto-pick tick completed
market monitor tick
exit tick
learning tick


Unexpected absence of ticks may indicate scheduler failure.

---

### 3.2 Signal Flow

Monitor signal ingestion.

Verify:

- signals move through lifecycle
- CREATED → EXECUTING → OPENED transitions occur correctly
- no signals stuck indefinitely

Signals stuck in EXECUTING may indicate processing failures.

---

### 3.3 Exposure Monitoring

Review exposure levels.

Verify:

- open quantity per symbol
- open notional per exchange
- total open positions

Ensure exposure remains within configured limits.

Relevant controls:


MAX_OPEN_QTY_PER_SYMBOL
MAX_OPEN_NOTIONAL_PER_EXCHANGE


---

### 3.4 Duplicate Execution Monitoring

Watch for signs of duplicate trading activity.

Potential indicators:

- repeated orders for same symbol and time
- multiple positions opened from same signal
- unexpected exposure spikes

Investigate immediately if detected.

---

### 3.5 Broker Execution Logs

Monitor broker execution logs.

Verify:

- order responses received
- no repeated retries
- no broker rejection loops
- expected fill confirmations

Important signals:


order submitted
order accepted
order rejected


---

# 4. Post-Deployment Safety Checks

These checks must occur after deploying a new version.

---

### 4.1 Scheduler Restart

Confirm the scheduler restarted correctly.

Check logs:


auto-pick-scheduler started


Verify that ticks resume normally.

---

### 4.2 Idempotency Behavior

Test that idempotency protections are working.

Verify:

- duplicate requests with same `X-Idempotency-Key` return same response
- no duplicate broker orders occur.

---

### 4.3 Execution Guards

Verify execution protections remain active.

Confirm:

- dry_run enforcement
- real-trading guard behavior
- allowlist restrictions
- exit plan requirements

---

### 4.4 Database Integrity

Check database consistency.

Verify:

- no duplicate signals
- no duplicate positions
- valid lifecycle states
- no orphan records

---

# 5. Incident Response Checks

If unexpected behavior occurs, perform the following steps.

---

### 5.1 Disable Trading

Immediately disable trading:


trading_enabled:{tenant_id} = false


This prevents further execution.

---

### 5.2 Identify Root Cause

Review logs for:

- scheduler events
- signal processing
- broker execution responses
- retry loops

---

### 5.3 Inspect Signal and Position State

Verify whether:

- duplicate signals exist
- multiple positions were opened
- exposure limits were exceeded

---

### 5.4 Compare Internal and Broker State

Check for mismatches between:

- internal positions
- broker positions
- order history
- balance state

Resolve discrepancies before resuming trading.

---

# 6. Weekly Operational Review

Perform deeper checks once per week.

---

### 6.1 Strategy Behavior

Review strategy performance.

Check:

- signal success rate
- score distribution
- trade outcomes

Unexpected shifts may indicate strategy drift.

---

### 6.2 Liquidity Conditions

Evaluate how liquidity classification behaves.

Verify:

- spread levels
- slippage levels
- candidate rejection rates

Ensure the classifier remains appropriate for current market conditions.

---

### 6.3 Exposure Patterns

Review long-term exposure trends.

Confirm:

- no persistent overexposure
- no runaway position growth
- healthy turnover of trades.

---

# 7. Safety Principles

Operational safety depends on strict adherence to these principles:

1. Never enable trading when system health is uncertain.
2. Never ignore duplicate execution signals.
3. Always reconcile internal state with broker state.
4. Prefer disabling trading over risking uncontrolled execution.
5. Treat unexpected behavior as a critical incident.

---

# 8. Final Note

Automated trading systems can fail silently if not monitored carefully.

Regular use of this checklist significantly reduces operational risk and helps ensure that the trading system behaves as expected.

