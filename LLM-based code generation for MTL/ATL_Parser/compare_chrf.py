#!/usr/bin/env python3
"""Compare old vs new CHRF scores."""
import csv

new_scores = {}
with open('atl_chrf_similarity.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        key = (row['LLM'], row['Strategy'], row['File'])
        new_scores[key] = float(row['CHRF_Score'])

# Old scores from previous run
old_raw = """claude-sonnet-4,few_shot,AmaltheaToAscet_All,93.4942
claude-sonnet-4,few_shot,BibTeX2DocBook_All,43.3731
claude-sonnet-4,few_shot,CPL2SPL_All,56.8618
claude-sonnet-4,few_shot,DSL2KM3_All,39.8098
claude-sonnet-4,few_shot,FamiliesToPersons_All,87.7646
claude-sonnet-4,few_shot,Grafcet2PetriNet_All,30.9401
claude-sonnet-4,few_shot,IEEE1471_2_MoDAF_All,57.8742
claude-sonnet-4,few_shot,Make2Ant_All,51.2139
claude-sonnet-4,few_shot,NetworkToGraph_All,98.9943
claude-sonnet-4,few_shot,PetriNet2Grafcet_All,27.6622
claude-sonnet-4,few_shot,XML2DSL_All,43.5833
claude-sonnet-4,few_shots_AND_grammar,AmaltheaToAscet_All,79.0311
claude-sonnet-4,few_shots_AND_grammar,BibTeX2DocBook_All,45.0504
claude-sonnet-4,few_shots_AND_grammar,CPL2SPL_All,52.7711
claude-sonnet-4,few_shots_AND_grammar,DSL2KM3_All,36.0829
claude-sonnet-4,few_shots_AND_grammar,FamiliesToPersons_All,87.7746
claude-sonnet-4,few_shots_AND_grammar,Grafcet2PetriNet_All,28.0666
claude-sonnet-4,few_shots_AND_grammar,IEEE1471_2_MoDAF_All,57.2674
claude-sonnet-4,few_shots_AND_grammar,Make2Ant_All,39.772
claude-sonnet-4,few_shots_AND_grammar,NetworkToGraph_All,96.1684
claude-sonnet-4,few_shots_AND_grammar,PetriNet2Grafcet_All,32.711
claude-sonnet-4,few_shots_AND_grammar,XML2DSL_All,38.5415
claude-sonnet-4,grammar,AmaltheaToAscet_All,76.8144
claude-sonnet-4,grammar,BibTeX2DocBook_All,37.0865
claude-sonnet-4,grammar,CPL2SPL_All,61.1759
claude-sonnet-4,grammar,DSL2KM3_All,36.2896
claude-sonnet-4,grammar,FamiliesToPersons_All,87.6138
claude-sonnet-4,grammar,Grafcet2PetriNet_All,32.6853
claude-sonnet-4,grammar,IEEE1471_2_MoDAF_All,37.3895
claude-sonnet-4,grammar,Make2Ant_All,45.4279
claude-sonnet-4,grammar,NetworkToGraph_All,96.1226
claude-sonnet-4,grammar,PetriNet2Grafcet_All,33.9987
claude-sonnet-4,grammar,XML2DSL_All,43.0938
claude-sonnet-4,only_prompt,AmaltheaToAscet_All,93.4942
claude-sonnet-4,only_prompt,BibTeX2DocBook_All,30.2662
claude-sonnet-4,only_prompt,CPL2SPL_All,45.0443
claude-sonnet-4,only_prompt,DSL2KM3_All,34.9498
claude-sonnet-4,only_prompt,FamiliesToPersons_All,82.4897
claude-sonnet-4,only_prompt,Grafcet2PetriNet_All,33.0708
claude-sonnet-4,only_prompt,IEEE1471_2_MoDAF_All,43.1321
claude-sonnet-4,only_prompt,Make2Ant_All,45.018
claude-sonnet-4,only_prompt,NetworkToGraph_All,59.654
claude-sonnet-4,only_prompt,PetriNet2Grafcet_All,34.1115
claude-sonnet-4,only_prompt,XML2DSL_All,39.3937
gemini-2-5-pro,few_shot,AmaltheaToAscet_All,80.3213
gemini-2-5-pro,few_shot,BibTeX2DocBook_All,36.363
gemini-2-5-pro,few_shot,CPL2SPL_All,72.6828
gemini-2-5-pro,few_shot,DSL2KM3_All,32.0503
gemini-2-5-pro,few_shot,FamiliesToPersons_All,84.9608
gemini-2-5-pro,few_shot,Grafcet2PetriNet_All,26.7445
gemini-2-5-pro,few_shot,IEEE1471_2_MoDAF_All,57.1986
gemini-2-5-pro,few_shot,Make2Ant_All,45.9944
gemini-2-5-pro,few_shot,NetworkToGraph_All,93.3363
gemini-2-5-pro,few_shot,PetriNet2Grafcet_All,32.3565
gemini-2-5-pro,few_shot,XML2DSL_All,41.0192
gemini-2-5-pro,few_shots_AND_grammar,AmaltheaToAscet_All,91.3412
gemini-2-5-pro,few_shots_AND_grammar,BibTeX2DocBook_All,31.0139
gemini-2-5-pro,few_shots_AND_grammar,CPL2SPL_All,66.6425
gemini-2-5-pro,few_shots_AND_grammar,DSL2KM3_All,40.3266
gemini-2-5-pro,few_shots_AND_grammar,FamiliesToPersons_All,88.909
gemini-2-5-pro,few_shots_AND_grammar,Grafcet2PetriNet_All,22.6027
gemini-2-5-pro,few_shots_AND_grammar,IEEE1471_2_MoDAF_All,53.5314
gemini-2-5-pro,few_shots_AND_grammar,Make2Ant_All,45.7968
gemini-2-5-pro,few_shots_AND_grammar,NetworkToGraph_All,75.1891
gemini-2-5-pro,few_shots_AND_grammar,PetriNet2Grafcet_All,32.2923
gemini-2-5-pro,few_shots_AND_grammar,XML2DSL_All,42.4025
gemini-2-5-pro,grammar,AmaltheaToAscet_All,76.4016
gemini-2-5-pro,grammar,BibTeX2DocBook_All,38.4295
gemini-2-5-pro,grammar,CPL2SPL_All,66.7212
gemini-2-5-pro,grammar,DSL2KM3_All,35.7195
gemini-2-5-pro,grammar,FamiliesToPersons_All,89.7332
gemini-2-5-pro,grammar,Grafcet2PetriNet_All,25.2219
gemini-2-5-pro,grammar,IEEE1471_2_MoDAF_All,55.229
gemini-2-5-pro,grammar,Make2Ant_All,45.7771
gemini-2-5-pro,grammar,NetworkToGraph_All,69.352
gemini-2-5-pro,grammar,PetriNet2Grafcet_All,32.6131
gemini-2-5-pro,grammar,XML2DSL_All,49.0089
gemini-2-5-pro,only_prompt,AmaltheaToAscet_All,73.2672
gemini-2-5-pro,only_prompt,BibTeX2DocBook_All,39.7112
gemini-2-5-pro,only_prompt,CPL2SPL_All,71.1906
gemini-2-5-pro,only_prompt,DSL2KM3_All,32.1861
gemini-2-5-pro,only_prompt,FamiliesToPersons_All,87.857
gemini-2-5-pro,only_prompt,Grafcet2PetriNet_All,32.0892
gemini-2-5-pro,only_prompt,IEEE1471_2_MoDAF_All,59.0818
gemini-2-5-pro,only_prompt,Make2Ant_All,46.9162
gemini-2-5-pro,only_prompt,NetworkToGraph_All,69.352
gemini-2-5-pro,only_prompt,PetriNet2Grafcet_All,32.3565
gemini-2-5-pro,only_prompt,XML2DSL_All,42.3933
gpt-5,few_shot,AmaltheaToAscet_All,91.3412
gpt-5,few_shot,BibTeX2DocBook_All,46.2803
gpt-5,few_shot,CPL2SPL_All,58.6681
gpt-5,few_shot,DSL2KM3_All,48.6172
gpt-5,few_shot,FamiliesToPersons_All,86.2317
gpt-5,few_shot,Grafcet2PetriNet_All,39.5546
gpt-5,few_shot,IEEE1471_2_MoDAF_All,61.5077
gpt-5,few_shot,Make2Ant_All,55.3902
gpt-5,few_shot,NetworkToGraph_All,99.048
gpt-5,few_shot,PetriNet2Grafcet_All,46.7957
gpt-5,few_shot,XML2DSL_All,49.7996
gpt-5,few_shots_AND_grammar,AmaltheaToAscet_All,96.8278
gpt-5,few_shots_AND_grammar,BibTeX2DocBook_All,45.7939
gpt-5,few_shots_AND_grammar,CPL2SPL_All,58.9062
gpt-5,few_shots_AND_grammar,DSL2KM3_All,51.414
gpt-5,few_shots_AND_grammar,FamiliesToPersons_All,87.624
gpt-5,few_shots_AND_grammar,Grafcet2PetriNet_All,50.0113
gpt-5,few_shots_AND_grammar,IEEE1471_2_MoDAF_All,64.8226
gpt-5,few_shots_AND_grammar,Make2Ant_All,55.5798
gpt-5,few_shots_AND_grammar,NetworkToGraph_All,99.048
gpt-5,few_shots_AND_grammar,PetriNet2Grafcet_All,49.2132
gpt-5,few_shots_AND_grammar,XML2DSL_All,51.8732
gpt-5,grammar,AmaltheaToAscet_All,82.5518
gpt-5,grammar,BibTeX2DocBook_All,49.8713
gpt-5,grammar,CPL2SPL_All,57.8939
gpt-5,grammar,DSL2KM3_All,49.751
gpt-5,grammar,FamiliesToPersons_All,87.7889
gpt-5,grammar,Grafcet2PetriNet_All,44.6487
gpt-5,grammar,IEEE1471_2_MoDAF_All,57.8477
gpt-5,grammar,Make2Ant_All,50.6859
gpt-5,grammar,NetworkToGraph_All,85.8903
gpt-5,grammar,PetriNet2Grafcet_All,39.4438
gpt-5,grammar,XML2DSL_All,52.5862
gpt-5,only_prompt,AmaltheaToAscet_All,72.8484
gpt-5,only_prompt,BibTeX2DocBook_All,47.4207
gpt-5,only_prompt,CPL2SPL_All,62.2075
gpt-5,only_prompt,DSL2KM3_All,45.7013
gpt-5,only_prompt,FamiliesToPersons_All,84.8356
gpt-5,only_prompt,Grafcet2PetriNet_All,35.0938
gpt-5,only_prompt,IEEE1471_2_MoDAF_All,59.4329
gpt-5,only_prompt,Make2Ant_All,52.4378
gpt-5,only_prompt,NetworkToGraph_All,85.8903
gpt-5,only_prompt,PetriNet2Grafcet_All,37.9399
gpt-5,only_prompt,XML2DSL_All,49.4569"""

old_scores = {}
for line in old_raw.strip().split('\n'):
    parts = line.split(',')
    key = (parts[0], parts[1], parts[2])
    old_scores[key] = float(parts[3])

diffs = []
for key in sorted(new_scores.keys()):
    if key in old_scores:
        old = old_scores[key]
        new = new_scores[key]
        diff = new - old
        diffs.append((abs(diff), diff, key, old, new))

diffs.sort(reverse=True)

print("Top 25 files with largest CHRF score difference (new - old):")
print(f"{'LLM':<20} {'Strategy':<25} {'File':<25} {'Old':>8} {'New':>8} {'Diff':>8}")
print("-" * 96)
for absd, diff, key, old, new in diffs[:25]:
    print(f"{key[0]:<20} {key[1]:<25} {key[2]:<25} {old:>8.2f} {new:>8.2f} {diff:>+8.2f}")

print()
print(f"Average absolute difference: {sum(d[0] for d in diffs)/len(diffs):.2f}")
print(f"Files with diff > 5: {sum(1 for d in diffs if d[0] > 5)}")
print(f"Files with diff > 10: {sum(1 for d in diffs if d[0] > 10)}")
print(f"Files with diff > 20: {sum(1 for d in diffs if d[0] > 20)}")
