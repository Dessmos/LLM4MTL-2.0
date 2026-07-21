"""Generate summary CSVs from etl_parser_chrf_results.csv."""
import csv
from collections import defaultdict

INPUT_CSV = 'etl_parser_chrf_results.csv'

# Read combined results
with open(INPUT_CSV, 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

stats = defaultdict(lambda: {
    'total': 0, 'valid': 0, 'problems': 0, 'chrf_scores': []
})

for row in rows:
    key = (row['LLM'], row['Strategy'])
    stats[key]['total'] += 1
    if row['Parsed'] == 'True':
        stats[key]['valid'] += 1
    pc = int(row['ProblemCount'])
    if pc > 0:
        stats[key]['problems'] += pc
    stats[key]['chrf_scores'].append(float(row['CHRF_Score']))

# ── 1. Parsed Rate Summary ──
with open('etl_parsed_rate_summary.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['LLM', 'Strategy', 'Parsed', 'Total', 'ParsedRate(%)', 'TotalProblems'])
    all_v = all_t = all_p = 0
    for (llm, strat), s in sorted(stats.items()):
        rate = s['valid'] / s['total'] * 100
        w.writerow([llm, strat, s['valid'], s['total'], round(rate, 1), s['problems']])
        all_v += s['valid']; all_t += s['total']; all_p += s['problems']
    w.writerow(['OVERALL', '', all_v, all_t, round(all_v/all_t*100, 1), all_p])
print('Written: etl_parsed_rate_summary.csv')

# ── 2. CHRF Summary ──
with open('etl_chrf_summary.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['LLM', 'Strategy', 'Count', 'Avg_CHRF', 'Min_CHRF', 'Max_CHRF'])
    all_scores = []
    for (llm, strat), s in sorted(stats.items()):
        sc = s['chrf_scores']
        avg = sum(sc) / len(sc)
        w.writerow([llm, strat, len(sc), round(avg, 2), round(min(sc), 2), round(max(sc), 2)])
        all_scores.extend(sc)
    w.writerow(['OVERALL', '', len(all_scores),
                round(sum(all_scores)/len(all_scores), 2),
                round(min(all_scores), 2), round(max(all_scores), 2)])
print('Written: etl_chrf_summary.csv')

# ── 3. Combined Summary (parsed rate + CHRF) ──
with open('etl_summary.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['LLM', 'Strategy', 'Parsed', 'Total', 'ParsedRate(%)',
                'TotalProblems', 'Avg_CHRF', 'Min_CHRF', 'Max_CHRF'])
    all_v = all_t = all_p = 0
    all_scores = []
    for (llm, strat), s in sorted(stats.items()):
        rate = s['valid'] / s['total'] * 100
        sc = s['chrf_scores']
        avg = sum(sc) / len(sc)
        w.writerow([llm, strat, s['valid'], s['total'], round(rate, 1),
                    s['problems'], round(avg, 2), round(min(sc), 2), round(max(sc), 2)])
        all_v += s['valid']; all_t += s['total']; all_p += s['problems']
        all_scores.extend(sc)
    w.writerow(['OVERALL', '', all_v, all_t, round(all_v/all_t*100, 1),
                all_p, round(sum(all_scores)/len(all_scores), 2),
                round(min(all_scores), 2), round(max(all_scores), 2)])
print('Written: etl_summary.csv')
