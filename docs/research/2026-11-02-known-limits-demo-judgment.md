# Known limits (Rene's demo judgment, Nov 2)

On Nov 2, 2026, Rene judged 11 demo-sample candidates. Each one gave the same answer in 3 of 3 runs on the deployed code (main `97b6967`, tuning-v2). He approved 8 (OL002, OL063, OL083, OL001, CN01, CN02, CN05, CN07) and rejected 3 (OL013, OL014, OL068). His notes, quoted exactly, are below. Each is followed by what Lusot did in run 1, the run whose outlined photo he judged, and why.

Each "why" is one of three kinds:
- **A rule:** a decision recorded in [`eval/rules.md`](../../eval/rules.md) v0.10. Rene chose to keep v0.10 for submission on Nov 2.
- **Perception:** what the models saw or answered. SAM 3.1 draws the outlines; Muse Spark 1.3 names where the water reaches.
- **The gutter gap:** no landmark reads `gutter` (rules.md §6, kept by Rene on Oct 28).

"P3" means person 3 on the numbered photo; "B" marks a vehicle body and "W" a wheel.

## OL002 (approved; Lusot: tire, 3 of 3)

> "Sure that it is tire level, but P5 and P6 (and even P4 and P7) should be also considered like the P3"

- **What Lusot did:** P3 decided the level: an adult answered at mid-thigh, which reads tire. P2 and P5 were answered at the knee, and were dropped because their outlines don't touch the water outline. P4 and P7 were answered as not clearly adults, and P6's waterline as not visible, so none of these three gave a reading.
- **Why:**
  - Perception: Muse Spark put P5 at the knee where Rene sees the thigh, and could not see P6's waterline.
  - Rules: the water-contact check drops a person whose outline doesn't meet the water (C302), and only adults set a level (D13).
  - Counted as answered, P2 and P5 (knee) sit one level below P3 (tire). Refusing takes a gap of more than one level, so the deepest believable reading, tire, would still win; they would add no support for it either.

## OL001 (approved; Lusot: waist, 3 of 3)

> "P3 and P5 also can be marked as waist level."

- **What Lusot did:** P4 decided the level at the waist. P3 and P5 were answered as not clearly adults, with their waterlines not visible, so neither gave a reading. P6, also at the waist, was too small in the photo to decide (C92). P1 was answered at the waist but not as an adult. P2 was at the waist but was taken as walking while others stood still, so it was dropped as wading.
- **Why:** perception (P3's and P5's age and waterline), and the rules that only a standing adult of readable size sets the level (D13, C57, C92).

## OL063 (approved; Lusot: below gutter, 3 of 3)

> "below gutter to gutter level."

- **What Lusot did:** an SUV's wheel (W5), with the water at the tyre only, decided the level: below gutter. A tricycle and a motorcycle were dropped as vehicle types Lusot doesn't read (C45), and one vehicle was dropped as moving.
- **Why:** the gutter gap. A tyre-only waterline reads `below_gutter`, and no landmark reads `gutter`, so water between the two levels can only read below gutter (or the next landmark up). The rules accept this; it is reported, not hidden.

## OL013 (rejected; Lusot: can't tell, 3 of 3)

> "Below Gutter to Gutter Level compared to the far bike."

- **What Lusot did:** no numbered reference. SAM outlined 5 wheels but no vehicle, so no wheel could be linked to a vehicle (`wheel_unlinked`), and no person was found.
- **Why:** perception. The outlines missed the bike's body, so its wheels had nothing to belong to. Even with the bike read, the gutter gap would allow below gutter at best.

## OL014 (rejected; Lusot: can't tell, 3 of 3)

> "P1 visible person riding a bicycle, and it shows gutter level."

- **What Lusot did:** P1 was the only reference. Muse Spark answered P1's waterline as not visible, in runs 1 and 3. In run 2 it answered mid-shin, but P1's outline didn't touch the water. The bicycle was not outlined as a vehicle.
- **Why:** perception (the waterline on a rider, and the missing bicycle outline), and the water-contact rule (C302). The gutter gap also applies.

## OL068 (rejected; Lusot: can't tell, 3 of 3)

> "gutter level flood but passable."

- **What Lusot did:** one vehicle was outlined, of a type Muse Spark couldn't name, and it was answered as moving, so it was dropped (W1). No other reference was found.
- **Why:** rules. A moving vehicle is never read, because the bow wave around it raises the water at its wheels (W1); only sedans and SUVs give wheel readings (C45). The gutter gap also applies. "Passable" matches what a gutter reading would give: gutter is PATV.

## What was tested, and not changed

On Nov 2 the tracker and Window 4 checked whether rule changes would fix these, by replaying every saved run with the change made in memory only, at no cost. Two changes were tested: keeping moving vehicles, and reading motorcycle and tricycle wheels like car wheels.
- **Gain:** 7 more exact readings on the open-licensed pool, and one more demo photo correct 3 of 3.
- **Cost:** one new passability over-read.
- **Unchanged:** most of the misses above, which come from perception, not from rules.

Rene chose to keep rules v0.10 (option A).

The same replay then tested his OL002 and OL001 notes. It counted the people that the water-contact check had dropped, using Muse Spark's own answers.
- **Under-reads:** 3 new ones on the agreed relabel set (OL005, OL115 and OL116 read half knee where the label is knee), each also a passability under-read.
- **Over-reads:** one new passability over-read (OL118).
- **OL002:** still read tire 3 of 3, as expected.
- **Why the rule stays:** an under-read is the error Lusot must never add. Counting people answered as not clearly adults changed no labelled reading, so that rule stays too (D13).
- **OL001:** P3's and P5's waterlines were answered as not visible, so no rule change could count them.
