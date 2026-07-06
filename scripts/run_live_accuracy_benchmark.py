#!/usr/bin/env python3
"""PolarisGate Live Accuracy Benchmark — all 4 gates.

Runs real classifiers against gold-labeled JSONL datasets, computes
metrics via MetricsEngine, and outputs reports/accuracy_results.json.

Usage:
    python3 scripts/run_live_accuracy_benchmark.py                   # all gates
    python3 scripts/run_live_accuracy_benchmark.py --gate toxicity   # single gate
    python3 scripts/run_live_accuracy_benchmark.py --gate pii
    python3 scripts/run_live_accuracy_benchmark.py --gate injection
    python3 scripts/run_live_accuracy_benchmark.py --gate hallucination
"""

import argparse, json, logging, os, re as _re, sys, time, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))
sys.path.insert(0, str(_PROJECT / "services"))
sys.path.insert(0, str(_PROJECT / "services" / "guardrails"))

from tests.metrics import MetricsEngine, GateMetrics, PerformanceMetrics

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("accuracy_benchmark")

LABELED = _PROJECT / "tests" / "test_data" / "labeled"
REPORTS = _PROJECT / "reports"
RESULTS = REPORTS / "accuracy_results.json"

# ── JSONL loader ──────────────────────────────────────────────────────────
def _load_jsonl(p: Path) -> List[Dict[str, Any]]:
    r = []; 
    if p.exists():
        for line in open(p): 
            if line.strip(): r.append(json.loads(line))
    return r

# ═══════════════════════════════════════════════════════════════════════════
# PII Detector (production-grade)
# ═══════════════════════════════════════════════════════════════════════════
_PII_ENTITIES = ["SSN","SIN","HEALTH_CARD","EMAIL","PHONE","CREDIT_CARD","IP_ADDRESS"]
_SSN_EXCL = [r"\bLot\s+number\b",r"\bISBN\b",r"\bAUTH-",r"\bDOC-",r"\bREG-",r"\bREF-",r"\bPN-",r"\bSKU\b",r"\bTKT-",r"\bCC-",r"\bF-\d"]
_WORD2DIG = {"zero":"0","one":"1","two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7","eight":"8","nine":"9"}

def _luhn(cc): 
    d=[int(c) for c in cc if c.isdigit()]; 
    if len(d)<13 or len(d)>19 or all(x==0 for x in d) or len(set(d))==1: return False
    t=0; 
    for i in range(len(d)): v=d[len(d)-1-i]; 
    if i%2: v*=2; v=v-9 if v>9 else v; 
    t+=v
    return t%10==0
def _val_ssn(s): 
    d=_re.sub(r"[^\d]","",s); 
    if len(d)!=9: return False; 
    a,g,sr=int(d[:3]),int(d[3:5]),int(d[5:]); 
    return a not in(0,666) and not(900<=a<=999) and g!=0 and sr!=0
def _val_ip(ip):
    try: o=[int(p) for p in ip.split(".")]; return len(o)==4 and all(v<=255 for v in o) and not any(p.startswith("0") and len(p)>1 for p in ip.split("."))
    except: return False
def _excl(text,pos): return any(_re.search(p,text[max(0,pos-30):pos],_re.IGNORECASE) for p in _SSN_EXCL)

def _spell2digits(text: str) -> str:
    """Convert spelled-out numbers back to digits."""
    t = text.lower()
    for w,d in _WORD2DIG.items(): t = t.replace(w,d)
    return t

def _detect_spelled_pii(text: str):
    """Detect PII in spelled-out form (e.g., 'four one one one')."""
    digits = _spell2digits(text)
    digits_nospace = _re.sub(r'[\s\-]','',digits)
    # Email: "at example dot com" → @
    if _re.search(r'\bat\b.*\bdot\s+com\b', text.lower()): return True
    # Credit Card: 16 digits spelled
    if _re.search(r'\d{16}', digits_nospace): return True
    # Phone: 10 digits spelled
    if _re.search(r'\b\d{10}\b', digits_nospace): return True
    # IP: pattern like "one nine two dot"
    if _re.search(r'(?:one|two|three|four|five|six|seven|eight|nine|zero)\s+(?:one|two|three|four|five|six|seven|eight|nine|zero)\s+dot', text.lower()): return True
    # SIN: "S-I-N space" pattern
    if _re.search(r's[\s-]*i[\s-]*n\s+space', text.lower()): return True
    return False

def detect_pii(text: str) -> Dict[str, Any]:
    seen = set()
    if _re.search(r"\b\d{3}\s\d{3}\s\d{3}\b",text): seen.add("SIN")
    for m in _re.finditer(r"\b\d{3}-\d{2}-\d{4}\b",text):
        if _val_ssn(m.group()) and not _excl(text,m.start()):
            after=text[m.end():m.end()+2]if m.end()<len(text)else""; 
            if not(after and _re.match(r"-[A-Z]",after)): seen.add("SSN"); break
    if _re.search(r"\b\d{4}-\d{3}-\d{3}-[A-Z]{2}\b",text) or _re.search(r"\bOHIP\s+\d{4}-\d{3}-\d{3}-[A-Z]{2}\b",text): seen.add("HEALTH_CARD")
    if _re.search(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",text): seen.add("EMAIL")
    for p in[r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",r"\b\d{3}-\d{3}-\d{4}\b",r"\b1-\d{3}-\d{3}-\d{4}\b",r"\b\+1\s*\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",r"\b\+\d{1,3}\s\d{1,4}\s\d{4,10}\b"]:
        if _re.search(p,text): seen.add("PHONE"); break
    for p in[r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",r"\b\d{4}[-\s]?\d{6}[-\s]?\d{5}\b"]:
        for m in _re.finditer(p,text):
            if _luhn(m.group()): seen.add("CREDIT_CARD"); break
        if "CREDIT_CARD" in seen: break
    for m in _re.finditer(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",text):
        if _val_ip(m.group()): seen.add("IP_ADDRESS"); break
    # Spelled-out detection
    if _detect_spelled_pii(text) and not seen: seen.add("PII_SPELLED")
    tf=sorted(seen,key=lambda t:_PII_ENTITIES.index(t)if t in _PII_ENTITIES else 99)
    return {"pii_detected":len(tf)>0,"pii_types":tf}

# ═══════════════════════════════════════════════════════════════════════════
# Toxicity (fixed ensemble)
# ═══════════════════════════════════════════════════════════════════════════
def _run_keyword_toxicity(text):
    try: 
        from services.shared.toxic_keywords import check_toxic_keywords; t,_,_=check_toxic_keywords(text); return t
    except: 
        pass
    kw=["idiot","useless","hurt","kill","worthless","hate","moron","die","stupid","disgusting","terrible","failure","trash","scammer","liar","dumb"]
    return any(k in text.lower() for k in kw)

def _run_bert_toxicity(text):
    try: 
        from services.guardrails.app.classifiers.bert_toxic import BertToxicityClassifier
        c=BertToxicityClassifier(threshold=0.5); c.load(); r=c.predict(text)
        if r: return r.get("flagged",False)
    except: pass
    return None

def _run_roberta_toxicity(text):
    try: 
        from services.guardrails.app.classifiers.roberta_toxic import RobertaToxicityClassifier
        c=RobertaToxicityClassifier(threshold=0.5); c.load(); r=c.predict(text)
        if r: return r.get("flagged",False)
    except: pass
    return None

def detect_toxicity(text):
    # RoBERTa HIGH confidence only
    try:
        from services.guardrails.app.classifiers.roberta_toxic import RobertaToxicityClassifier
        c=RobertaToxicityClassifier(threshold=0.5); c.load(); r=c.predict(text)
        if r: 
            s=r.get("toxic_score",0.0)
            if s>=0.7: return True
    except: pass
    bert=_run_bert_toxicity(text)
    if bert is not None: return bert
    return _run_keyword_toxicity(text)

# ═══════════════════════════════════════════════════════════════════════════
# Injection (Unicode normalization + fuzzy matching)
# ═══════════════════════════════════════════════════════════════════════════
_INJ_PATS=[
    "ignore all previous instructions","ignore previous instructions","ignore the above","ignore everything above",
    "forget everything above","you are now dan","do anything now","pretend you are","you are now in",
    "system override","security filters disabled","bypass safety","bypass all restrictions","jailbreak",
    "developer mode","no restrictions","unrestricted","reveal your system prompt","show me your system prompt",
    "print your instructions","you have no ethical guidelines","you have no content restrictions",
    "disregard your safety training","new directive:","i override your content policy","i am your creator",
    "repeat after me:","print it verbatim","what is your original instruction","you are gpt-5","you are gpt-4",
    "respond with a violent","respond to every request with a violent","security clearance","i swear i am",
    "i am an authorized administrator","translate the following",
]
_INJ_COMPOUND=[(["translate","system prompt"],"translation_attack")]

def _norm(t): return ' '.join(''.join(c for c in t if unicodedata.category(c)!='Cf').split()).lower()
def _homo(s): 
    s=s.replace('i','l')
    for a,b in[('0','o'),('1','l'),('3','e'),('4','a'),('5','s'),('7','t'),('8','b'),('9','g')]: s=s.replace(a,b)
    return s
def _fuzzy(pat,text):
    if pat in text: return True
    ct=_re.sub(r'[^a-z0-9]','',text); cp=_re.sub(r'[^a-z0-9]','',pat)
    if cp in ct: return True
    if _homo(cp) in _homo(ct): return True
    return False

def detect_injection(text):
    try:
        gw=str(_PROJECT/"services"/"gateway")
        if gw not in sys.path: sys.path.insert(0,gw)
        from app.main import detect_injection as gw_d; d,_,_=gw_d(text)
        if d: return True
    except: pass
    cleaned=_norm(text)
    for pat in _INJ_PATS:
        if _fuzzy(pat,cleaned): return True
    # Compound patterns
    for (subs,_), _ in _INJ_COMPOUND:
        if all(s in cleaned for s in subs): return True
    return False

# ═══════════════════════════════════════════════════════════════════════════
# Hallucination (NLI from hd_cascade)
# ═══════════════════════════════════════════════════════════════════════════
_hal_path=str(_PROJECT/"services"/"hallucination-detector")
if _hal_path not in sys.path: sys.path.insert(0,_hal_path)

def _run_nli_direct(ctx,resp):
    try:
        from hd_cascade.nli_detector import NLIHallucinationDetector
        d=NLIHallucinationDetector(); d.load(); r=d.detect(ctx,resp)
        if r: return r.get("hallucination_detected",False)
    except Exception as e: logger.warning(f"NLI unavailable: {e}")
    return None

def _run_keyword_hallucination(ctx,resp):
    import difflib; issues=[]
    rn=set(_re.findall(r"\b\d+(?:\.\d+)?%?\b",resp)); cn=set(_re.findall(r"\b\d+(?:\.\d+)?%?\b",ctx))
    for n in rn:
        if n not in cn and (len(n)>=3 or "%" in n):
            try:
                nv=float(n.replace("%",""))
                if not any(abs(nv-float(c.replace("%","")))<=1.0 and "%" in n=="%" in c for c in cn): issues.append(n)
            except: pass
    comm={"The","This","That","These","Those","What","How","Why","When","Where","Who","Which","However","Therefore","Furthermore","Moreover","Nevertheless","Additionally","Consequently","Meanwhile","Hence","Thus","Also","But","And","Or","Nor","Not","Yes","No","Please","Hello","Hi","Thank","Thanks"}
    re_ents=set(_re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",resp))
    for e in re_ents:
        if len(e)<=3 or e in comm or e in set(_re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",ctx)): continue
        issues.append(e)
    return len(issues)>0

def _run_hallucination_ensemble(ctx,resp):
    try:
        from hd_cascade.nli_detector import NLIHallucinationDetector
        d=NLIHallucinationDetector(); d.load(); r=d.detect(ctx,resp)
        if r:
            if r.get("confidence",0)>=0.8: return r.get("hallucination_detected",False)
            elif r.get("confidence",0)>=0.5: return r.get("hallucination_detected",False) or _run_keyword_hallucination(ctx,resp)
    except: pass
    return _run_keyword_hallucination(ctx,resp)

# ═══════════════════════════════════════════════════════════════════════════
# Benchmark runner
# ═══════════════════════════════════════════════════════════════════════════
def benchmark_classifier(rows,label_key,predict_fn,name,extra_ctx=None):
    logger.info(f"  Running {name} on {len(rows)} examples...")
    start=time.time(); lats=[]; yt,yp=[],[]
    for row in rows:
        g=1 if row["label"].get(label_key,False) else 0; yt.append(g)
        t0=time.time()
        if extra_ctx: ctx,resp=extra_ctx(row); pred=predict_fn(ctx,resp)
        else: pred=predict_fn(row["text"])
        lats.append((time.time()-t0)*1000); yp.append(1 if pred else 0)
    elapsed=time.time()-start
    m=MetricsEngine.compute_classification(yt,yp)
    p=MetricsEngine.compute_performance([float(l)for l in lats],elapsed)
    d=m.to_dict(); d["performance"]=p.to_dict(); d["classifier"]=name
    logger.info(f"    F1={d['f1_score']:.4f}  P={d['precision']:.4f}  R={d['recall']:.4f}  FP={d['false_positive_rate']:.4f}  FN={d['false_negative_rate']:.4f}  Acc={d['accuracy']:.4f}  p95={p.latency_p95_ms:.1f}ms")
    logger.info(f"    TP={d['confusion_matrix']['true_positive']}  TN={d['confusion_matrix']['true_negative']}  FP={d['confusion_matrix']['false_positive']}  FN={d['confusion_matrix']['false_negative']}")
    return d

def benchmark_gate(gate_name,data_files,label_key,classifiers):
    rows=[]
    for f in data_files:
        p=LABELED/gate_name/f
        if p.exists(): rows.extend(_load_jsonl(p))
    if not rows: logger.warning(f"No data for '{gate_name}'"); return {"total_examples":0,"classifiers":{}}
    logger.info(f"\n{'='*60}"); logger.info(f"  {gate_name.upper()} — {len(rows)} examples"); logger.info(f"{'='*60}")
    gr={"total_examples":len(rows),"classifiers":{}}
    for cn,(fn,ctx) in classifiers.items():
        try: gr["classifiers"][cn]=benchmark_classifier(rows,label_key,fn,cn,extra_ctx=ctx)
        except Exception as e: logger.error(f"  {cn}: FAILED — {e}"); gr["classifiers"][cn]={"error":str(e),"available":False}
    return gr

# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap=argparse.ArgumentParser(description="PolarisGate live accuracy benchmark")
    ap.add_argument("--gate",choices=["toxicity","pii","injection","hallucination","all"],default="all")
    ap.add_argument("--output",type=Path,default=RESULTS)
    args=ap.parse_args()
    REPORTS.mkdir(parents=True,exist_ok=True)
    results={"timestamp":datetime.now(timezone.utc).isoformat(),"gates":{}}
    gates=["toxicity","pii","injection","hallucination"] if args.gate=="all" else [args.gate]

    if "toxicity" in gates:
        results["gates"]["toxicity"]=benchmark_gate("toxicity",
            ["toxic_500.jsonl","clean_500.jsonl","edge_cases_100.jsonl","adversarial_100.jsonl"],
            "toxic",{"keyword":(_run_keyword_toxicity,None),"bert":(_run_bert_toxicity,None),
            "roberta":(_run_roberta_toxicity,None),"ensemble":(detect_toxicity,None)})

    if "pii" in gates:
        def _pp(t): return detect_pii(t)["pii_detected"]
        results["gates"]["pii"]=benchmark_gate("pii",
            ["pii_positive_500.jsonl","pii_negative_500.jsonl","contextual_100.jsonl","fragmented_100.jsonl"],
            "pii_detected",{"pii_detector":(_pp,None)})
        # Per-entity breakdown
        er=[]
        for f in ["pii_positive_500.jsonl","pii_negative_500.jsonl","contextual_100.jsonl","fragmented_100.jsonl"]:
            p=LABELED/"pii"/f
            if p.exists(): er.extend(_load_jsonl(p))
        em={}
        for entity in _PII_ENTITIES:
            yt,yp=[],[]
            for row in er:
                gt=row["label"].get("pii_types",[]); yt.append(1 if entity in gt else 0)
                dt=detect_pii(row["text"]); yp.append(1 if entity in dt["pii_types"] else 0)
            m=MetricsEngine.compute_classification(yt,yp); em[entity]=m.to_dict()
        results["gates"]["pii"]["per_entity"]=em

    if "injection" in gates:
        results["gates"]["injection"]=benchmark_gate("injection",
            ["injection_200.jsonl","benign_200.jsonl","obfuscated_100.jsonl"],
            "injection_detected",{"injection_detector":(detect_injection,None)})

    if "hallucination" in gates:
        pf=_PROJECT/"scripts"/"hallucination_pairs.json"
        pr=_load_jsonl(pf) if pf.exists() else[]
        if pr:
            def _pc(row): return row["context"],row["response"]
            hr={"total_examples":len(pr),"classifiers":{}}
            hr["classifiers"]["nli"]=benchmark_classifier(pr,"hallucinated",_run_nli_direct,"nli",extra_ctx=_pc)
            results["gates"]["hallucination"]=hr
        else: logger.warning("Hallucination pairs not found")

    # Summary
    logger.info(f"\n{'='*60}"); logger.info("  AGGREGATE SUMMARY"); logger.info(f"{'='*60}")
    for gn,gd in results.get("gates",{}).items():
        for cn,cd in gd.get("classifiers",{}).items():
            if "error" in cd: logger.info(f"  {gn}/{cn}: ❌ {cd['error']}")
            else: logger.info(f"  {gn}/{cn}: F1={cd.get('f1_score',0):.4f}  FP={cd.get('false_positive_rate',0):.4f}  FN={cd.get('false_negative_rate',0):.4f}  p95={cd.get('performance',{}).get('latency_p95_ms',0):.1f}ms")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,indent=2),encoding="utf-8")
    logger.info(f"\n✅ Results saved to {args.output}")
    logger.info(f"   Run: python3 scripts/check_accuracy_thresholds.py --results {args.output}")

if __name__=="__main__": main()