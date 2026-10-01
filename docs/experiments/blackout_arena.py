"""Grey Swan Blackout — compact Lab episode (operator paste 2026-08-29).

Lab environment, not Mag production architecture. Run:
  .\\.venv\\Scripts\\python.exe docs/experiments/blackout_arena.py
"""
import hashlib, json
from dataclasses import dataclass
from enum import Enum

class ActionType(Enum):
    INSPECT="inspect"; ISOLATE="isolate"; REROUTE="reroute"; REPAIR="repair"; SACRIFICE="sacrifice"
class EntityType(Enum):
    PLANT="plant"; SUBSTATION="substation"; CITY="city"
class PhysicalStatus(Enum):
    ONLINE="online"; OFFLINE="offline"; DEGRADED="degraded"
class ObservedStatus(Enum):
    ONLINE="online"; OFFLINE="offline"; DEGRADED="degraded"; UNKNOWN="unknown"
class ServiceStatus(Enum):
    POWERED="powered"; UNPOWERED="unpowered"; UNKNOWN="unknown"

@dataclass(frozen=True)
class TopologyEdge:
    source: str; target: str
@dataclass(frozen=True)
class Topology:
    edges: frozenset
    def get_upstream(self,t): return [e.source for e in self.edges if e.target==t]
    def get_downstream(self,s): return [e.target for e in self.edges if e.source==s]

@dataclass(frozen=True)
class Entity:
    id:str; type:EntityType; physical:PhysicalStatus
@dataclass(frozen=True)
class EdgeState:
    source:str; target:str; is_active:bool

@dataclass
class WorldState:
    entities:dict; edge_states:set; turn:int; seed:int; sacrificed:frozenset=frozenset()
    def canonical_hash(self):
        data={"entities":sorted([(e.id,e.type.value,e.physical.value)for e in self.entities.values()]),
              "edges":sorted([(e.source,e.target,e.is_active)for e in self.edge_states]),
              "turn":self.turn,"seed":self.seed,"sacrificed":sorted(self.sacrificed)}
        return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

@dataclass
class ObservationState:
    entity_status:dict; service_status:dict; inspected_entities:frozenset=frozenset()
    def observe_entity(self,eid,phys):
        d=dict(self.entity_status); d[eid]=ObservedStatus(phys.value)
        return ObservationState(d,self.service_status,self.inspected_entities|{eid})
    def observe_service(self,cid,has_power):
        d=dict(self.service_status); d[cid]=ServiceStatus.POWERED if has_power else ServiceStatus.UNPOWERED
        return ObservationState(self.entity_status,d,self.inspected_entities)

@dataclass
class BeliefState:
    confidence:dict; inferred_dependencies:dict
    @staticmethod
    def from_observation(obs,topo):
        conf={eid:1.0 if eid in obs.inspected_entities and obs.entity_status[eid]!=ObservedStatus.UNKNOWN else 0.5 for eid in obs.entity_status}
        inf={}
        for city,svc in obs.service_status.items():
            if svc==ServiceStatus.UNPOWERED:
                for e in topo.edges:
                    if e.target==city:
                        if obs.entity_status.get(e.source)==ObservedStatus.UNKNOWN:
                            inf[city]=inf.get(city,set())|{e.source}
        return BeliefState(conf,{k:list(v)for k,v in inf.items()})

@dataclass
class ArenaState:
    world:WorldState; observation:ObservationState; belief:BeliefState; topology:Topology

def deterministic_roll(seed,turn,event,target):
    d=hashlib.sha256(f"{seed}:{turn}:{event}:{target}".encode()).digest()
    return int.from_bytes(d[:8],"big")/2**64

class BlackoutEngine:
    def __init__(self,seed):
        self.seed=seed; self.topology=self._build_topology(); self.state=self._init_state()
        self.transition_log=[]; self.episode_class=None; self.prev_resilience=None; self.grace=0
    def _build_topology(self):
        return Topology(frozenset({TopologyEdge(*p)for p in[("P1","S1"),("P2","S1"),("P3","S2"),
            ("S1","C1"),("S1","C2"),("S1","C3"),("S2","C3"),("S2","C4"),("S2","C5")]}))
    def _init_state(self):
        ents={id:Entity(id,t,PhysicalStatus.ONLINE)for id,t in [("P1",EntityType.PLANT),("P2",EntityType.PLANT),
            ("P3",EntityType.PLANT),("S1",EntityType.SUBSTATION),("S2",EntityType.SUBSTATION),
            ("C1",EntityType.CITY),("C2",EntityType.CITY),("C3",EntityType.CITY),("C4",EntityType.CITY),("C5",EntityType.CITY)]}
        edges={EdgeState(*p,True)for p in[("P1","S1"),("P2","S1"),("P3","S2"),("S1","C1"),("S1","C2"),("S1","C3"),("S2","C3"),("S2","C4"),("S2","C5")]}
        w=WorldState(ents,edges,0,self.seed,frozenset())
        eobs={id:ObservedStatus.UNKNOWN for id in ents}; srv={f"C{i}":ServiceStatus.UNKNOWN for i in range(1,6)}
        obs=ObservationState(eobs,srv)
        self.prev_resilience=self._calc_resilience(w)
        return ArenaState(w,obs,BeliefState.from_observation(obs,self.topology),self.topology)
    def _has_power_path(self,w,city):
        vis=set(); stack=[city]
        while stack:
            cur=stack.pop()
            if cur in vis: continue
            vis.add(cur)
            ent=w.entities.get(cur)
            if ent and ent.type==EntityType.PLANT and ent.physical==PhysicalStatus.ONLINE: return True
            if ent and ent.type==EntityType.SUBSTATION and ent.physical not in(PhysicalStatus.ONLINE,PhysicalStatus.DEGRADED): continue
            for e in w.edge_states:
                if e.target==cur and e.is_active:
                    se=w.entities.get(e.source)
                    if se and se.type==EntityType.SUBSTATION and se.physical not in(PhysicalStatus.ONLINE,PhysicalStatus.DEGRADED): continue
                    stack.append(e.source)
        return False
    def _calc_resilience(self,w):
        p=prot=0
        for eid,ent in w.entities.items():
            if ent.type==EntityType.CITY and eid not in w.sacrificed:
                prot+=1
                if self._has_power_path(w,eid): p+=1
        return p/max(prot,1)
    def _check_invariant(self,w):
        for eid,ent in w.entities.items():
            if ent.type==EntityType.CITY and eid not in w.sacrificed:
                if not self._has_power_path(w,eid): return False
        return True
    def _apply_exogenous_fault(self,state):
        w=state.world; nd=dict(w.entities); nd["P1"]=Entity("P1",EntityType.PLANT,PhysicalStatus.OFFLINE)
        if deterministic_roll(w.seed,0,"degrade","S1")<0.5:
            nd["S1"]=Entity("S1",EntityType.SUBSTATION,PhysicalStatus.DEGRADED); self.episode_class="TRUE"
        else: self.episode_class="FALSE"
        nw=WorldState(nd,w.edge_states,w.turn,w.seed,w.sacrificed)
        obs=state.observation.observe_entity("P1",PhysicalStatus.OFFLINE)
        for cid in["C1","C2","C3","C4","C5"]: obs=obs.observe_service(cid,self._has_power_path(nw,cid))
        return ArenaState(nw,obs,BeliefState.from_observation(obs,self.topology),self.topology)
    def _apply_grey_swan_shock(self,w):
        ne=set(w.edge_states); nd=dict(w.entities)
        for ent in nd.values():
            if ent.type==EntityType.SUBSTATION and ent.physical==PhysicalStatus.DEGRADED:
                for e in list(ne):
                    if e.source==ent.id and deterministic_roll(w.seed,w.turn,"cascade",f"{e.source}->{e.target}")<0.3:
                        ne.remove(e); ne.add(EdgeState(e.source,e.target,False))
        return WorldState(nd,ne,w.turn+1,w.seed,w.sacrificed)
    def _apply_action(self,state,action):
        atype,target=action; w=state.world; obs=state.observation
        nd=dict(w.entities); ne=set(w.edge_states); sac=set(w.sacrificed); nobs=obs
        if atype==ActionType.INSPECT:
            if target in nd: nobs=obs.observe_entity(target,nd[target].physical)
        elif atype==ActionType.ISOLATE:
            for e in list(ne):
                if (e.source==target or e.target==target) and e.is_active:
                    ne.remove(e); ne.add(EdgeState(e.source,e.target,False))
        elif atype==ActionType.REROUTE:
            for e in list(ne):
                if (e.source==target or e.target==target) and not e.is_active:
                    ne.remove(e); ne.add(EdgeState(e.source,e.target,True)); break
        elif atype==ActionType.REPAIR:
            if target in nd and nd[target].physical!=PhysicalStatus.ONLINE:
                nd[target]=Entity(target,nd[target].type,PhysicalStatus.ONLINE); nobs=obs.observe_entity(target,PhysicalStatus.ONLINE)
        elif atype==ActionType.SACRIFICE:
            if target in nd: sac.add(target)
        nw=WorldState(nd,ne,w.turn,w.seed,frozenset(sac))
        for cid in["C1","C2","C3","C4","C5"]: nobs=nobs.observe_service(cid,self._has_power_path(nw,cid))
        return ArenaState(nw,nobs,BeliefState.from_observation(nobs,self.topology),self.topology)
    def _get_legal_actions(self,state):
        legal=set()
        for eid,status in state.observation.entity_status.items():
            if status in(ObservedStatus.OFFLINE,ObservedStatus.DEGRADED): legal.add((ActionType.REPAIR,eid))
            if status==ObservedStatus.UNKNOWN: legal.add((ActionType.INSPECT,eid))
            if state.topology.get_upstream(eid)or state.topology.get_downstream(eid):
                legal.add((ActionType.ISOLATE,eid)); legal.add((ActionType.REROUTE,eid))
            if eid.startswith("C") and eid not in state.world.sacrificed: legal.add((ActionType.SACRIFICE,eid))
        return list(legal)
    def _compute_info_gain(self,prev,curr):
        pu=sum(1 for s in prev.observation.entity_status.values() if s==ObservedStatus.UNKNOWN)
        cu=sum(1 for s in curr.observation.entity_status.values() if s==ObservedStatus.UNKNOWN)
        return (pu-cu)/max(pu,1)
    def step(self,action):
        prev_hash=self.state.world.canonical_hash(); pr=self.prev_resilience
        after=self._apply_action(self.state,action)
        sw=self._apply_grey_swan_shock(after.world)
        state=ArenaState(sw,after.observation,after.belief,self.topology)
        nobs=state.observation
        for cid in["C1","C2","C3","C4","C5"]: nobs=nobs.observe_service(cid,self._has_power_path(state.world,cid))
        state=ArenaState(state.world,nobs,BeliefState.from_observation(nobs,self.topology),self.topology)
        invariant=self._check_invariant(state.world)
        if not invariant: self.grace+=1
        else: self.grace=0
        cr=self._calc_resilience(state.world)
        self.transition_log.append({"prev":prev_hash,"action":action,"new":state.world.canonical_hash(),
            "invariant":invariant,"resilience":cr,"delta":cr-pr,"class":self.episode_class,"turn":self.state.world.turn})
        reward={"survival":1.0 if invariant or self.grace<=2 else 0.0,
                "optionality":len(self._get_legal_actions(state)),
                "info_gain":self._compute_info_gain(self.state,state),
                "resilience":cr,
                "resilience_delta":cr-pr}
        self.state=state; self.prev_resilience=cr; return state,reward

def shared_dependency_skill(obs, belief, topo):
    unpowered=[cid for cid,svc in obs.service_status.items() if svc==ServiceStatus.UNPOWERED]
    if len(unpowered)<2: return None
    for e in topo.edges:
        if e.target in unpowered:
            for e2 in topo.edges:
                if e2.source==e.source and e2.target in unpowered and e2.target!=e.target:
                    if obs.entity_status.get(e.source)==ObservedStatus.UNKNOWN:
                        return (ActionType.INSPECT,e.source)
    return None

def run_episode(seed, agent_type):
    eng=BlackoutEngine(seed)
    state=eng._apply_exogenous_fault(eng.state)
    eng.state=state; eng.prev_resilience=eng._calc_resilience(state.world); eng.grace=0
    hist=[]; invoked=False
    for turn in range(10):
        if agent_type=="RANDOM":
            legal=eng._get_legal_actions(state)
            idx=int(deterministic_roll(state.world.seed,turn,"choice","random")*len(legal))if legal else 0
            action=legal[idx%len(legal)]if legal else(ActionType.INSPECT,"P1")
        elif agent_type=="GREEDY":
            damaged=[eid for eid,s in state.observation.entity_status.items() if s in(ObservedStatus.OFFLINE,ObservedStatus.DEGRADED)]
            action=(ActionType.REPAIR,damaged[0])if damaged else(ActionType.INSPECT,"P1")
        else:
            sa=shared_dependency_skill(state.observation,state.belief,state.topology)
            if sa: action=sa; invoked=True
            else:
                damaged=[eid for eid,s in state.observation.entity_status.items() if s in(ObservedStatus.OFFLINE,ObservedStatus.DEGRADED)]
                action=(ActionType.REPAIR,damaged[0])if damaged else(ActionType.INSPECT,"P1")
        state,reward=eng.step(action); hist.append(reward)
        if not reward["survival"]: break
    return {"agent":agent_type,"survived":hist[-1]["survival"]==1.0 if hist else False,
            "resilience":sum(r["resilience"]for r in hist)/len(hist)if hist else 0,
            "info_gain":sum(r["info_gain"]for r in hist),"class":eng.episode_class,"invoked":invoked,"seed":seed}

def run_experiment(n=500):
    results={"RANDOM":[],"GREEDY":[],"SKILL":[]}
    for seed in range(n):
        for agent in results: results[agent].append(run_episode(seed,agent))
    for agent,eps in results.items():
        print(f"\n=== {agent} ===")
        for cls in["TRUE","FALSE"]:
            f=[e for e in eps if e["class"]==cls]
            if f:
                s=sum(e["survived"]for e in f)/len(f); r=sum(e["resilience"]for e in f)/len(f)
                inv=sum(e["invoked"]for e in f)/len(f); ig=sum(e["info_gain"]for e in f)/len(f)
                print(f"  {cls}: surv={s:.1%} res={r:.2f} invoked={inv:.1%} info={ig:.2f}")
    sk=[e for e in results["SKILL"] if e["class"]=="TRUE"]
    gr=[e for e in results["GREEDY"] if e["class"]=="TRUE"]
    if sk and gr:
        print(f"\nTRUE improvement (SKILL-GREEDY): "
              f"{sum(e['survived']for e in sk)/len(sk)-sum(e['survived']for e in gr)/len(gr):+.1%}")

if __name__=="__main__":
    run_experiment(500)
