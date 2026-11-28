from collections import Counter

_counters:Counter[str] = Counter()

def incr(name:str,n:int=1)->None:
    _counters[name]+=n

def reset()-> None:
    _counters.clear()

def snapshot()-> dict:
    hits=_counters['cahce_hit']
    misses=_counters['cahce_miss']
    total=hits + misses
    return{
        "Counters":dict(_counters),
        'hit_ratio':round(hits/total,4) if total else None
    }