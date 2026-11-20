import hashlib,json,itertools
import numpy as np

def apriori(baskets,min_support=.15,min_confidence=.6):
    n=len(baskets);items=sorted(set().union(*baskets));counts={};previous=set()
    for k in range(1,4):
        current=set()
        for combo in itertools.combinations(items,k):
            key=frozenset(combo)
            if k>1 and not all(frozenset(sub)in previous for sub in itertools.combinations(combo,k-1)):continue
            count=sum(key<=basket for basket in baskets)
            if count/n>=min_support:counts[key]=count;current.add(key)
        previous=current
        if not current:break
    rules=[]
    for itemset,count in counts.items():
        if len(itemset)<2:continue
        for rhs in sorted(itemset):
            lhs=itemset-{rhs};confidence=count/counts[lhs];lift=confidence/(counts[frozenset([rhs])]/n)
            if confidence>=min_confidence and lift>1:rules.append({'if_subjects':sorted(lhs),'then_subject':rhs,'support':round(count/n,4),'confidence':round(confidence,4),'lift':round(lift,4)})
    return sorted(rules,key=lambda r:(-r['lift'],-r['confidence'],r['then_subject']))
def recommend(baskets,subjects):
    source=[set(x)for x in baskets];rng=np.random.default_rng(38);indices=rng.permutation(len(source));tr=indices[:72];te=indices[72:];rules=apriori([source[i]for i in tr]);hit=0;covered=0;cases=[]
    for i in te:
        basket=sorted(source[i]);hidden=basket[int(rng.integers(0,len(basket)))];visible=set(basket)-{hidden};guesses={r['then_subject']for r in rules if set(r['if_subjects'])<=visible and r['then_subject']not in visible};hit+=hidden in guesses;covered+=bool(guesses);cases.append({'basket_index':int(i),'visible':sorted(visible),'hidden':hidden,'recommended':sorted(guesses),'hit':hidden in guesses})
    current=set(subjects);suggested=[r for r in rules if set(r['if_subjects'])<=current and r['then_subject']not in current]
    return {'algorithm':'Apriori train-only itemset support + association rules','seed':38,'train_rows':len(tr),'holdout_rows':len(te),'train_indices':tr.tolist(),'holdout_indices':te.tolist(),'source_checksum':hashlib.sha256(json.dumps([sorted(x)for x in source],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),'min_support':.15,'min_confidence':.6,'min_lift':1,'rules':rules,'suggestions':suggested,'input_subjects':sorted(current),'holdout_hidden_item_recall':round(hit/len(te),4),'holdout_recommendation_coverage':round(covered/len(te),4),'holdout_cases':cases}
