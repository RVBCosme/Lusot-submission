# `eval/rules.md` v0.7: one proposal for Rene

> **Draft, Oct 28, 2026 (Window 4), from the tracker's verified updates (Rene delegated the recommended action).** It gathers in one file every change now proposed for `eval/rules.md`, so Rene can approve them at once.
>
> - **When:** Rene approves the whole file before any Set A result is seen. The target is Oct 30, when MS2's split runs.
> - **Who applies it:** after his written OK, the log owner (Window 3, since MS1 closed) edits `eval/rules.md` to v0.7, updates its status line, and adds the change-log line at the end. Until then, v0.6 stands, and the harness and the other windows follow the defaults below (D7).
> - **Form:** each item gives the text to add or change, its source, and the default that applies until Rene answers. Section numbers are `eval/rules.md`'s. Quoted "current text" is v0.6's, exactly.
> - **MS2's items** point at MS2's calls by number. MS2's spec wasn't committed when this was written (`next-specs` was still at `28b3530` at 3:31 PM), and its C203 and C209 were being revised (`specs.md`, 3:27 PM). Recheck their wording once MS2's spec is committed.

## §2. Mapping labels to the scale

| # | Add or change | Source | Default |
|---|---|---|---|
| 2.1 | After the bullet `- **A single number** ("10"", "12"", "37 inches") takes its level from the level rule in §1.`, add: "A number written without a unit (such as "25") is unmapped." | MS6E-Q1, item 11 | unmapped |
| 2.2 | After the variants bullet, add: "Any phrase may end with `deep` or `level`, or with neither: the two words are interchangeable, as "above gutter deep" beside "above gutter level" shows. Real alerts write "half tire level"." | MS6E-Q1, item 12; MS6 spec C404 | interchangeable |
| 2.3 | After the range bullet, add: "A range may carry a unit on each number (13"-18"). Two measures not joined by a range word, such as "24 in (61 cm)", give one depth in two units: the label takes that level when both units give the same level, and is unmapped when they don't." | MS6E-Q1, item 13 (Pasig gives depths in centimetres and inches: the alert index) | as written |
| 2.4 | Replace `- **Statuses that are not depths**, such as "subsided", can't match a photo.` with: "- **Statuses that are not depths**, such as "subsided", can't match a photo. As a photo's own label, a status gives "no matching alert". Among a photo's other matching alerts, it is ignored." | MS6E-Q1, item 7 | as written |
| 2.5 | After the "Any other label is excluded" bullet, add: "A passability phrase that maps to no class leaves the photo out of the passability metric only, and is logged. A photo whose alert gives neither a depth nor a class is excluded as "unmapped label"." | MS6E-Q1, items 2 and 14; MS6 spec C404 | as written |

## §3. Matching a photo to an alert

| # | Add or change | Source | Default |
|---|---|---|---|
| 3.1 | Replace `- If a photo matches several alerts, use the one nearest in time. If two of them differ by more than one level, exclude the photo ("conflicting alerts").` with: "- If a photo matches several alerts, the log gives the nearest one's labels, and the others' level labels as written (MS2's C209). If any two of them differ by more than one level, the photo is excluded ("conflicting alerts"). An unmapped label among the others makes a conflict impossible to rule out, so it excludes the photo as "unmapped label". An empty one, from an alert that gave only a class, is ignored." | MS6E-Q1, item 8; MS6 spec C404 | as written |
| 3.2 | In the "Separate posts" bullet, the alert's time for a photo in a separate post: the time the alert's text gives, or else its post's time, in the wording of MS2's committed spec. | MS2-Q2 (MS2's C209, being revised) | MS2's default |

## §4. Flood events and splits

| # | Add or change | Source | Default |
|---|---|---|---|
| 4.1 | MS2-Q2's §4 items, in the wording of MS2's committed spec:<ul><li>the seed `20261030`, fixed in the code, so the line "Split seed: `TBD at split time`" gets that value now and only the date is filled at split time</li><li>the shares by whole events, with a cap: an event goes to sealed only while the sealed side would hold at most 45% of a set's rows (A-neg 40%), and the walk ends at 40% (A-neg a third); a single split (C204)</li><li>C203's event rule</li><li>Set B's split by car number: odd cars development, even cars final (C210)</li><li>the final-car run as two of Rene's commands, with the masks in plaintext in `set_b\sealed\` until the archive is tested (C214). This replaces "The generator and the G3 ground truth run on them as one unattended script, writing straight into the encrypted archive."</li></ul> | MS2-Q2 (MS2's C203, C204, C210, C214) | MS2's defaults, which MS2's tools follow as Claude's calls until Rene answers |
| 4.2 | **The split is stratified by passability.** After the split bullet, add: "The walk runs separately for two groups of events, with the same seed and the same shares: events with any NPLV or NPATV row (by §2's passability table), and the rest. In a group with 2 or more events, each side gets at least one." | Rene's data-roles instruction (§3, about 3:35 PM); MS2-Q2 (MS2's C204, as amended) | stratified |
| 4.3 | **Validation is event replay.** New bullet: "Development data has two uses. All of it tunes (MS3b's C310). Then, as validation, each development flood event is scored with C310's settings chosen on the other events, by replaying the saved model outputs, with no new Meta call. Reports show the replay figures beside the in-sample ones. If the replay's within-one agreement falls 3 or more photos below the in-sample figure, the cutoffs go back to their start values, marked untuned, and the tuning change log says why." | Rene's data-roles instruction (§3; guard 3); MS6 spec C425 | as written |
| 4.4 | Replace "It writes the sealed rows straight into the encrypted archive (M19), and agents only ever see development rows." with: "It writes the sealed rows into a write-once encrypted archive (M19), one per sealing step: Set A and A-neg, Set B's final cars, and Set D if it rains (MS2's C205). Agents only ever see development rows." | MS2-Q2 | MS2's default: one write-once archive per sealing step. The alternative is a single archive, written once after the last sealing input exists. |

## §5. Ground truth for Set B

| # | Add or change | Source | Default |
|---|---|---|---|
| 5.1 | MS2-Q2's §5 items, in the wording of MS2's committed spec: C211's crops (four per car photo, one per level band below the hub, half of them shrunk) and C212's truth (the scale from the dry wheel mask and the tire code's diameter). | MS2-Q2 (MS2's C211, C212) | MS2's defaults |

## §6. Reading rules

| # | Add or change | Source | Default |
|---|---|---|---|
| 6.1 | New bullet: "**In-between waterlines.** When the water sits between two marks, the reading takes the higher mark. Table 5 says so for wheels. Prompt v1 also applies it to people and to car bodies, and our own M8 labels follow the same convention." Rene answers wheels, people and car bodies separately, by Oct 30. One answer settles this item and MS3b-Q5 together. That the M8 sheet labels this way is pending MS2's sheet (Window 2's update B.4). | MS3b-Q5; the probe note §4; the tracker's update | the higher mark for all three |

## §7. Metrics

| # | Add or change | Source | Default |
|---|---|---|---|
| 7.1 | After the "No flood seen" bullet, add: "For exact and within-one agreement, "no flood seen" counts as one step below `below_gutter`: never exact, and within one level only of `below_gutter`. In the weighted kappa, which knows only the 9 levels, it counts as `below_gutter`." | MS6E-Q1, item 1 | as written |
| 7.2 | In the "Envelope coverage" row, after "`depthInMin` to `depthInMax`", add: ", over the wheels measured". | MS6E-Q1, item 4 | over measured wheels |
| 7.3 | In the "False flood rate" row, add: "Over every scored A-neg photo. A processing failure counts in n, never as a false flood, and is shown beside it." | MS6E-Q1, item 9 | as written |
| 7.4 | In the "Correct refusals" row, add: "A processing failure is not a refusal." | MS6 spec §4.2 (CLAUDE.md keeps the two apart) | as written |
| 7.5 | **The baseline row.** New bullet: "Every report shows two baselines, "always the most common level" and "always the most common passability class". Both come from the development rows, and are scored on Lusot's answered rows. Lusot should beat them on within-one agreement and on underestimation, and falling short on either is underfitting. Exact agreement is shown but not judged, because landmarks never read `gutter` (§6). The report also counts the NPLV and NPATV photos caught. Reports print numbers, not verdicts." | Rene's data-roles instruction (§4, underfitting guard 1); MS6 spec C424 | as written |
| 7.6 | New bullet: "In results by level, a level with fewer than 5 photos shows counts, not percentages." | Rene's data-roles instruction (§4, guard 1) | as written |
| 7.7 | In the "Landmark agreement" row, add: "Over the references our labels give a landmark, in photos Muse Spark answered. A labelled box that Muse Spark skipped counts as a disagreement. A label that matched no box is counted apart and left out." | MS6E-Q1, item 10; MS6 spec C415 | as written |

## §8. Release gate for inches

| # | Add or change | Source | Default |
|---|---|---|---|
| 8.1 | After the targets list, add: "**What "rise" means here.** Wherever this section says Set A underestimation rises, or doesn't rise, when geometry is added, a rise means that geometry raises either the underestimation rate or the number of underestimated photos." This covers the target `**No rise**`, rule 1's `**does not rise**`, rule 2's `**rises**` and the first guard's "doesn't rise". | MS6E-Q5 | (d): neither the rate nor the count may rise |
| 8.2 | After the targets, add: "Set B's figures are the shipped configuration's: SAM's waterline with the frozen rim-edge factor k. The figures without k, and with the known waterline, are reported but never gate. Without Set B, no inches show." | MS6E-Q1, item 3; MS6 spec C407 | as written |
| 8.3 | After the guards, add: "A rate with nothing to count can't show that a guard or a target is met, so it fails, and rule 2 applies when it is a guard." | MS6E-Q1, item 5 | as written |
| 8.4 | The self-check's 10 s condition: no text change. The rule stays as written, so the self-check is built only if a lower reasoning effort (MS3b's C312) brings photo to pin near 10 s. | MS3b-Q3, default (a) | (a), no change |

## §9. Exclusions

| # | Add or change | Source | Default |
|---|---|---|---|
| 9.1 | After "duplicate or repost", add: "(identical files, or difference hashes within 6 bits of each other, found by MS2's split)". | MS2-Q2 | MS2's default |
| 9.2 | After "the file can't be decoded", add: "(checked by MS2's split, before any run; a file that decoded but fails in the pipeline is a processing failure, not an exclusion)". | MS6 spec C404 | as written |
| 9.3 | New line: "A-neg photos are excluded only as duplicates or files that can't be decoded." | MS6E-Q1, item 6 | as written |
| 9.4 | After "A photo is **never** excluded because of Lusot's output.", add: "**Notes never change the ground truth.** No photo is relabeled after its prediction is seen. A new exclusion must be a written rule that tests facts recorded before the run, applies to every row, and is made before the sealed run with Rene's OK." | Rene's data-roles instruction (§4, overfitting guard 5) | as written |

## §10. Reproducibility (the sealed run)

| # | Add or change | Source | Default |
|---|---|---|---|
| 10.1 | In the "Freeze and record" bullet, after "the face-blur setting with its detector version (D12)", add: "; Muse Spark's reasoning effort; the SAM phrases sent, any backup phrase included; `store` and `max_side`; the annotation (drawing) version of the numbered image; the self-check setting; and MS3b's tuning version, tire codes, rim-edge factor k and geometry's default". | MS3b-Q4 (a); the tracker's update; MS6 spec §4.6 | added |
| 10.2 | After `- Run the sealed set **once**.`, add: "A run that stops partway, from a rejected key, a crash or a lost connection, resumes as the same run: photos with saved outputs are never sent again. A resume isn't the disclosed rerun." | MS6 spec C419 | as written |
| 10.3 | Also there: "A photo whose analysis failed because Meta's service failed (an HTTP error after the client's retries, or a timeout) is retried once before the export, and the report says how many were. A photo whose answer was invalid is never retried." | MS6E-Q6 | (a), retried once |
| 10.4 | In the `**After the freeze**` bullet, add: "The one disclosed rerun runs at a second, recorded freeze, and its results sit beside the first run's, so both sets of numbers stay in the repo." | MS6 spec C421 | as written |
| 10.5 | The one-command check: no change, unless Rene picks `uv run` (MS6E-Q4, option (b)). | MS6E-Q4 | (a), no change |

Two questions change nothing here:
- MS6E-Q3, the decrypted sealed copy, is a procedure question.
- MS6E-Q2, the M8 method, is settled by MS2's C208.

## The status line and the change-log line, once approved

- **Status line:** "DRAFT v0.6 (Oct 28, 2026)" becomes "v0.7 ([date]), approved by Rene", and the sentence about v0.6 is replaced by one naming this proposal.
- **Change-log line:**

| Date | Version | Change | Approved by |
|---|---|---|---|
| [date] | 0.7 | <ul><li>§2 and §3: label and matching readings, the alert time for separate posts</li><li>§4: the split, its seed, cap and stratification by passability, Set B's split by car, the final-car run, one archive per sealing step (MS2-Q2), and validation by event replay</li><li>§5: Set B's crops and truth (MS2-Q2)</li><li>§6: in-between waterlines (MS3b-Q5)</li><li>§7: metric denominators, the baseline row and the per-level counts rule</li><li>§8: what "rise" means, Set B's gate figures, and undefined guards and targets</li><li>§9: duplicates, files checked before the run, A-neg's exclusions, and notes that never change the ground truth</li><li>§10: the freeze list, resume, retry and the rerun</li></ul> | Rene, [date], in writing |
