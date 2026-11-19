"""Concurrency test of the admit() algorithm (token bucket at 70% of limit + ledger cap) on Redis.
Stand-in for the Firestore ledger: tests the algorithm and atomicity, NOT Firestore contention."""
import subprocess, sys, time, threading, json
PORT="6399"
def rc(*a): return subprocess.run(["redis-cli","-p",PORT,*a],capture_output=True,text=True).stdout.strip()
LUA="""
local limit=tonumber(ARGV[1]); local cap=tonumber(ARGV[2]); local n=tonumber(ARGV[3])
local used=tonumber(redis.call('GET',KEYS[1]) or '0')
local led=tonumber(redis.call('GET',KEYS[2]) or '0')
if used+n>limit then return 0 end
if led+n>cap then return -1 end
redis.call('INCRBY',KEYS[1],n); redis.call('INCRBY',KEYS[2],n); return 1
"""
sha=rc("SCRIPT","LOAD",LUA)
rc("FLUSHALL")
LIMIT=int(0.7*1000)   # 1000 calls/min live limit -> admit at 70%
CAP=5000
W=200; PER=20          # 200 concurrent workers, 20 requests each = 4000 asks
res={"admit":0,"deny_rate":0,"deny_cap":0}; lock=threading.Lock()
def worker():
    for _ in range(PER):
        r=rc("EVALSHA",sha,"2","bucket:min","ledger:day",str(LIMIT),str(CAP),"1")
        k={"1":"admit","0":"deny_rate","-1":"deny_cap"}[r]
        with lock: res[k]+=1
t0=time.time(); ts=[threading.Thread(target=worker) for _ in range(W)]
[t.start() for t in ts]; [t.join() for t in ts]
led=int(rc("GET","ledger:day")); used=int(rc("GET","bucket:min"))
out={"asks":W*PER,**res,"ledger":led,"bucket":used,"secs":round(time.time()-t0,1)}
out["lost_increments"]=res["admit"]-led
out["over_limit"]=used>LIMIT
print(json.dumps(out))
sys.exit(0 if out["lost_increments"]==0 and not out["over_limit"] and res["admit"]==LIMIT else 1)
