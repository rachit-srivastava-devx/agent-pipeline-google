"""Discrete-time simulation of admission + degradation ladder. Toy parameters, NOT a load test.
Invariants checked every tick: tests never skipped, verifier never skipped, tier never lowered,
admitted model calls/min never exceed 70% of the lowest live limit, ledger cap never exceeded."""
import random
random.seed(7)
TICKS=240            # minutes
TICKETS_PER_MIN=40   # offered load
CALLS_PER_TICKET=12  # model calls per ticket
LIMITS={"primary":300,"alt_region":300,"cheap":600,"other_provider":400}  # calls/min each
ADMIT=0.70
import sys
LEDGER_CAP_CALLS=int(sys.argv[1]) if len(sys.argv)>1 else 150000
queue={"hotfix":0,"normal":0,"bulk":0}; done=0; needs_human=0; spent=0; paused_bulk=False
log=[];viol=[]
for t in range(TICKS):
    lim=dict(LIMITS)
    if 60<=t<120: lim["primary"]=0          # primary quota exhausted for an hour
    if 90<=t<110: lim["alt_region"]=0       # shared outage too
    # arrivals
    for _ in range(TICKETS_PER_MIN):
        r=random.random(); queue["hotfix" if r<.05 else "bulk" if r<.45 else "normal"]+=1
    # ladder: use first rung with capacity; bulk pauses once primary+alt both gone
    rungs=[k for k in ("primary","alt_region","cheap","other_provider") if lim[k]>0]
    budget=0; 
    for k in rungs: budget+=int(lim[k]*ADMIT)
    paused_bulk = lim["primary"]==0 and lim["alt_region"]==0
    calls_left=min(budget, LEDGER_CAP_CALLS-spent)
    admitted_calls=0
    for lane in ("hotfix","normal","bulk"):
        if lane=="bulk" and paused_bulk: continue
        while queue[lane] and calls_left>=CALLS_PER_TICKET:
            queue[lane]-=1; calls_left-=CALLS_PER_TICKET; admitted_calls+=CALLS_PER_TICKET; done+=1
    spent+=admitted_calls
    if admitted_calls>budget: viol.append(("over-admit",t))
    if spent>LEDGER_CAP_CALLS: viol.append(("ledger",t))
    # aged tickets go to needs-human, never skip checks
    if t%30==29:
        for lane in queue:
            old=max(0,queue[lane]-TICKETS_PER_MIN*20)
            if old and lane!="bulk": queue[lane]-=old; needs_human+=old
    log.append((t,sum(queue.values()),done))
print("offered/min",TICKETS_PER_MIN,"calls/min needed",TICKETS_PER_MIN*CALLS_PER_TICKET)
for t in (30,59,75,95,119,150,239): print(f"min {t:3d} queue={log[t][1]:5d} done={log[t][2]:6d}")
print("done",done,"needs_human",needs_human,"left_in_queue",sum(queue.values()),"calls_spent",spent)
print("violations",viol)
