# MS8 submission checklist (draft)

> **Claude's draft, Oct 29, 2026, for MS8** ([spec](../../superpowers/specs/2026-10-29-ms8-submit-design.md)). It lists every requirement and deadline known for the submission, each with its source. Items that only the participant guide, the Discord or the kickoff stream could confirm are marked **Rene confirms**, since those need his login. Rene ticks the boxes on Nov 4. Plan text is paraphrased and cited by section, never copied (C4).

## Sources

| Key | Source |
|---|---|
| **OR** | The Official Rules and Event Waiver ("Hackathon Terms & Conditions"), dated Oct 25, 2026. They are in the raw server HTML of the [event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon), fetched with curl at 11:57 PM, Oct 28 (Manila), and searched there. Summaries and the page's `.md` copy miss this section. A rechecked fetch at 12:49 AM, Oct 29 (Manila) matched the Oct 28 extract by SHA-256. Quoted section names below are the rules' own. Unquoted ones say where in the rules a point sits. "Apply Now", "Participant Tracks" and "Project Themes" are event-page sections outside the rules. |
| **KD** | The event page's "Key Dates" list, in the same fetch |
| **PD** | The portal's page data in the same HTML: `hackathonSubmissionDueDate` (2026-11-05 02:00, UTC) and `submissionDueDateGracePeriodHours` (6) |
| **Plan** | The build plan (outside every repo), cited by section and table and paraphrased |
| **Design** | [The build design](../../superpowers/specs/2026-10-26-lusot-build-design.md) |
| **Guide**, **Discord**, **Kickoff** | The participant guide, the Discord #rules and #faqs posts, and the kickoff stream. Everything known from them comes through the plan, so each such item is marked **Rene confirms**. |

Manila time is UTC+8. US daylight saving time ends on Nov 1, 2026, so from then on ET is UTC−5 and Manila is 13 hours ahead.

## 1. Deadlines

| Manila time | What | Source |
|---|---|---|
| Oct 31 | MS8-Q5 answered, so MS5's M17 kit can add the filming consent (N8) | Spec §8 |
| Nov 2 | The submission repository created, empty and private, and its URL given to MS5's final build (MS8-Q2, N8). Created Nov 1 (MS8-Q2: (a)); the URL still goes into MS5's final build | Spec §8 |
| Weekdays from Nov 2, 11:00 PM to midnight | Office hours in Discord #office-hours | Plan §2, Table 1; design §4. **Rene confirms.** |
| Nov 3, 1:00 PM to Nov 4, 1:00 PM (all of Nov 3, ET) | The last full day for submission questions; technical troubleshooting ends | Plan §2, Table 1 (from the guide). **Rene confirms.** Ask MS8-Q3's question by then, through the channel the guide gives for rules questions, since office hours take API questions. |
| Nov 3 | R7 decided (MS8-Q1, which also answers MS7-Q8); MS8-Q3, MS8-Q4, MS8-Q8 and MS8-Q9 answered (all answered Nov 1: spec §8); checklist O6 checked, before any push | Design §7; spec §8 |
| Nov 4, 2:00 PM | Under MS8-Q4's default, the latest time the sealed report can reach `main` for a 9:00 PM submission. A report by 11:00 PM still allows a complete entry by Nov 5, 6:00 AM, but **any move past 10:00 PM needs Rene's OK on the day, even under D7** (CLAUDE.md's target). | Spec §8 |
| Nov 3 | The video recorded a day early, with a backup recording of the live flow | Plan §19 (demo and judging practices) |
| Nov 4 | English captions written and their timing checked (M30); the bonus entry (M33); MS8-Q6 and MS8-Q7 answered | Plan §24, Table 27; spec §8 |
| Nov 4, 10:00 PM | **Our target: submitted** (12 hours before the cutoff) | Plan §2; design §4; CLAUDE.md |
| Nov 4 to 5 | The X post, with its link added on the platform (M26) | Plan §24, Table 27 |
| Nov 5, 10:00 AM | **Hard cutoff.** KD: "Nov 4: Project submissions due by 9:00 PM ET". PD stores Nov 5, 02:00 UTC, the same moment. Late entries aren't considered (plan §2, Table 1: **Rene confirms**). | KD; PD |
| (none) | PD also holds a 6-hour grace field. Its meaning isn't stated, so it is never relied on (C916). | PD |
| Nov 5 to 9 | Judging. KD gives "Nov 4 – Nov 8" with no time zone, on an event that runs on ET; the plan gives Nov 5 to 9 in Manila. The live demo stays up throughout (MS9). | KD; plan §2, Table 1 |
| Until about 1:00 PM, Nov 9 | X engagement counts until the end of Nov 8, ET (M26) | Plan §18 and §24 (from the guide). **Rene confirms.** |
| Nov 10, 1:00 AM | Closing ceremony: live finals and winners announced. KD gives "Nov 9"; the time (Nov 9, 12:00 PM ET) and the top 5 per track come from the plan. | KD; plan §2, Table 1. **Rene confirms** the time. |
| On or about Nov 10 | Bonus prizes announced, including any public-vote prize | OR, "Bonus Prizes" |
| Nov 16 or 17 | The community vote's winner, announced on Discord. This differs from OR's "on or about November 10". | Plan §2, Table 1. **Rene confirms.** |
| Any time | "Dates may be subject to change at Meta's sole discretion." Changes are posted on the event page, which Claude rechecks on Nov 3 and Nov 4 (C916). | KD |

## 2. Requirements in the Official Rules

| # | Requirement | Where (OR section) | How MS8 meets it |
|---|---|---|---|
| R1 | Submit the project on Cerebral Valley's portal, at the submission page the rules name (the event page's `/hackathon/submit` path) | "Event Overview" | Rene submits (M24) |
| R2 | Submit by Nov 4, 9:00 PM ET | KD | Target Nov 4, 10:00 PM Manila (§1) |
| R3 | A project enters one track only | Track rules, before "Indie Developer track" | Indie Developer track |
| R4 | The representative submits the project and identifies every other team member in the submission. Indie teams have up to 4 people, and solo entries are allowed. | "Indie Developer track" | Solo: Rene submits and lists no one else (M5) |
| R5 | The representative warrants that every team member has read and accepts the rules | Track rules | Solo; Rene read them on Oct 27 (M4) |
| R6 | Eligibility: at least 18 and of the age of majority; not in a sanctioned or barred country; not an employee, contractor or intern of Meta or Cerebral Valley, not government-affiliated, and not in such a person's immediate family or household | "Age Restrictions and Eligibility Requirements"; "Apply Now" | Rene's own standing (M4) |
| R7 | The submission is the participant's original work, solely owned, and violates no one's intellectual property, contract or privacy rights | "Hackathon Submission" | Credits and licences in the README; consent for every person shown (C904) |
| R8 | Third-party technical assistance is allowed, provided the components remain the participant's own work and he owns all rights to them | "Hackathon Submission" | The README keeps MS1's line: Rene built Lusot solo, with Claude Code as a coding assistant (C912) |
| R9 | Open source is allowed if its licences are followed and the submission enhances or builds upon it | "Hackathon Submission" | README credits; MS7's licence check (M22, with R52's SAM License question) |
| R10 | The entrant keeps ownership and grants the organizers a perpetual, irrevocable, worldwide, royalty-free, non-exclusive licence to use the submission for any purpose, marketing included | "Hackathon Submission" | Music, photos and consents must allow that use (C904; C18) |
| R11 | Materials shared with the event aren't confidential, and the organizers get a licence to them | "Release of Information" | Nothing private in the repository, video or write-up (C903, C906) |
| R12 | The organizers may record and reuse participants' name, likeness, voice, image, chat messages, screen shares and submissions | "Image, Video and Audio Recording Consent" | Applies to the live final round and the video |
| R13 | The criteria and weights, in the rules' order: Impact (30%), Use of Meta AI Tooling (25%), Technical Depth & Execution (20%), and Demo (25%). Demo covers a working demo, whether the product holds up live, and the quality of the demo video. | "Hackathon Judging Criteria" | The write-up's order (MS8-Q6); the live demo (C919, MS9) |
| R14 | Impact includes whether the project fits one of the problem statements. The themes are "Build for Your World" and "Push the Frontier". | "Hackathon Judging Criteria"; "Project Themes" | The write-up names "Build for Your World" (plan §1) |
| R15 | Participants build with Meta AI products | "Event Overview" | `sam-3.1`, `muse-spark-1.3` and `muse-voice-transcribe-1.0`, through the Meta Model API |
| R16 | The $150 of Meta Model API credits are "valid for a 10-day development window" | "Event Overview" | Judging traffic may bill the card (design §4); MS9 watches billing |
| R17 | Bonus prizes of up to $50,000 in all, in categories that "may include" a community vote award and a most viral project award, announced on or about Nov 10 | "Bonus Prizes" | M26 and M33; M27 in MS9 |
| R18 | Prizes only after eligibility checks and compliance with the rules | Prizes; "Verification of Potential Winners" | None needed before submitting |
| R19 | Before payment: the signed waiver and Official Rules, and a W-8BEN for a non-US winner | "General Payout Details", item 3 | After a win (MS10) |
| R20 | Professional conduct in every virtual space, shared repositories included | "Code of Conduct and Right to Refuse Participation" | The README and commits stay professional |
| R21 | The organizers may change or cancel the hackathon, and may modify these terms, with significant changes communicated to registered participants | Opening paragraphs; "Modifications" | Event-page rechecks (C916) |
| R22 | Winners pay any fees and taxes on a prize | "Fees and Taxes" | After a win |
| R23 | The Indie track is "Judged on creativity, technical ambition, and whether it works" | The event page's "Participant Tracks", outside the rules | The write-up and the video lead with those three |
| R24 | Participants review the Credit Terms before claiming their credits | "Event Overview" | Claimed Oct 27 (M3). Rene confirms he read them; Claude didn't open the PDF on Facebook's file server. |

The public rules don't mention a repository, a video length or the X post. Those come from the guide (§3).

## 3. Rene confirms: rules known only through the plan

Each of these comes from the participant guide, the Discord or the kickoff stream, as the plan summarizes them. Rene checks each one against the source itself.

| # | Claim | From | Why it matters |
|---|---|---|---|
| G1 | **New work only:** all the work a project presents comes from the event, nothing is built before kickoff, and the demo shows only event work. A project is disqualified if judges can't tell its new work apart. | Plan §2 (guide, #rules) | MS8-Q3; the video's opening line (C909) |
| G2 | **What to submit:** a public repository and a 3-minute demo video, entered by one representative who lists the whole team. The judges look at the video, the code and the running product. Partly public: the team listing is R4, and the live product and the video sit in R13's Demo criterion. | Plan §2 (guide) | M24 |
| G3 | **The video's limit:** "3 minutes" (is 3:00 the ceiling?), and any rule on its host or visibility | Plan §2, §18 | C911 |
| G4 | **Projects to avoid** include "simple image analyzers" | Plan §1, §2 (guide) | The pitch rule (CLAUDE.md) |
| G5 | **Judging stages:** a pass or fail check (fits a problem statement; uses the Meta Model API or Meta's open-weight models), then scores of 0 to 10 by weight, then the top 5 per track in a live final where judges watch the videos live. Partly public: KD names the "live finals", and OR lists five prizes per track. | Plan §1 (guide) | The video plays live (C908) |
| G6 | **Most Viral:** post the demo video on X and add the post's link on the platform. Engagement counts until Nov 8, end of day ET. Prize $20,000. Are any tags or mentions required? | Plan §18; §24, M26 (guide) | M26; MS8-Q7 |
| G7 | **Best agentic use case:** prize $5,000; entrants call out bonus tracks when they submit. Not in the Official Rules or on the event page (Nov 1): Rene enters it only if the form offers the field, and no public text names it or its amount | Plan §24, M33 (kickoff) | M33 |
| G8 | **Community Vote:** prize $10,000, one vote per verified account, winner on Nov 16 or 17 | Plan §2, Table 1; §24, M27 | MS9 |
| G9 | **Only approved participants may take part in making the project,** and no new approvals are given | Plan §1, §2 (Discord FAQ) | No one else builds, labels, films, edits or submits. Testers and viewers only react (C906). |
| G10 | The last full day for submission questions is Nov 3, and office hours from Nov 2 run 11:00 PM to midnight Manila | Plan §2, Table 1 | MS8-Q3's question |
| G11 | The closing ceremony is Nov 9, 12:00 PM ET (Nov 10, 1:00 AM Manila) | Plan §2, Table 1 | M25 |
| G12 | Late entries aren't considered | Plan §2, Table 1 | §1 |

**Not in any source we have** (Rene reads them on the form or asks the organizers):

| # | Question | Why it matters |
|---|---|---|
| O1 | The form's fields and length limits: track, team, theme, repository, video, live URL, APK, description, bonus categories, the X link. Can an entry be edited until the deadline? | C914, C918, and the plan's order of steps |
| O2 | May planning notes from before kickoff (no code) stay in the repository? | MS8-Q3 |
| O3 | Does the guide say anything about AI coding assistants beyond OR's rule on technical assistance (R8)? | The README's "How it was built" line |
| O4 | May the repository or the live product change after the deadline? | C921 |
| O5 | Does the X rule need the submitted video itself, or may a shorter cut be posted? | MS8-Q7 |
| O6 | Does a `Claude-Session` link in the commit history ask for sign-in when opened in a private window? A signed-out curl only meets Cloudflare's bot challenge, so it can't tell. | MS8-Q1: the links stay only if they are gated |

## 4. Our own commitments (plan §18's checklist)

These are the plan's, not the rules'. Each is checked by Nov 4.

- [ ] The rules read: the participant guide, plus the Discord's #rules and #faqs (M4, done Oct 27), and rechecked against §3 above
- [ ] A public repository made after kickoff (MS8-Q1, MS8-Q2). Its README starts with a judge path that takes a minute: the live app, a sample run, the video, and the one command (C913).
- [ ] The live web URL, and a downloadable Android APK (C917)
- [ ] The 3-minute video following Table 19: it opens with the built-during-the-event line and carries English captions throughout (M23, M30; C905, C908, C909)
- [ ] The write-up in criteria order (MS8-Q6)
- [ ] The app's Tested page (the plan's accuracy page) carries the evaluation: how often Lusot read shallower than the label, how often its class and its level agreed, how many photos it answered, Set B's error, every sample size, and the release gate's verdict on inches (MS5's C616; MS6)
- [ ] The privacy policy page live; the 18+ check and the consent notice working (MS5's U8; M21)
- [ ] Notes from the five-person test with the change it led to (M17), and, if they came, a stakeholder's one-line quote and their group's pledge in writing (M28; not required, C13)
- [ ] Submitted on the platform with the public repository and the video link, as a solo entry (M24)
- [ ] The demo posted on X, with the post's link added on the platform (M26)
- [ ] Every weakness register row (W1 to W28) Done or explained in the README (C912)

## 5. What goes where in the form

Filled in once Rene has seen the form (O1).

| Field (expected) | Value | Ready when |
|---|---|---|
| Project name | Lusot | now |
| Track | Indie Developer | now |
| Team | Rene Vincent Cosme, solo | now |
| Theme | Build for Your World | now |
| Repository | the URL in the README outline's clone line | named Nov 1 (MS8-Q2: (a), Rene); in the form once it's public (C902) |
| Video | `[video link]` | once Rene uploads it (C911) |
| Live URL | `[live URL]` | MS5 |
| APK | `[GitHub Release link]`, SHA-256 `[…]` | once Rene publishes the release (C917) |
| Description | From the [write-up outline](write-up-outline.md): the tagline, the summary and the full text, cut to the form's limits | Nov 4 |
| Bonus categories | Best agentic use case (M33), pointing to Ask Lusot's tool calls, and the self-check if it shipped, only if the form offers that field (G7); otherwise the bonus categories the form lists | Nov 4 |
| X post | `[X post link]` (M26) | after Rene posts it |

## 6. Go or no-go, just before Rene submits

- [ ] Rene approved the README, the video, the write-up and the X post's text
- [ ] The copy rules hold in all four (spec S5), and the safety line appears word for word at the README's top, on the video's closing card, at the write-up's end and in the X post
- [ ] Every number matches `summary.json` or a cited source (S4)
- [ ] Checklist O6 was checked before the first push, and the `Claude-Session` lines were kept or dropped to match (MS8-Q1)
- [ ] The export's whole-history scan is clean, or every hit is allow-listed with a reason Rene has read (S7), and nothing unscanned was ever pushed to the repository (C902)
- [ ] The app's count of unreviewed lines is 0: `LUSOT_RELEASE=1 npm run copy:review -w app` (S11)
- [ ] The repository is public, its CI has passed, and a fresh clone runs the one command with exit 0 (S3, S8)
- [ ] The licence file is in place (M22)
- [ ] The APK release and its SHA-256 match the build that MS7 scanned
- [ ] The demo-ready check passed within the past hour (C919)
- [ ] The event page was rechecked today (C916)
- [ ] The video is at most 3:00, captioned throughout, and credited, and its frame check is clean (S6)

## 7. Right after submitting

- [ ] Rene reports the platform's confirmation and its time; Claude logs it (S1)
- [ ] The X link is on the platform, if it was added after the entry (M26)
- [ ] Nothing more is pushed to the submission repository (C921)
- [ ] MS9 starts: the demo stays live through the finals (Nov 10, 1:00 AM Manila time), and the alarms, Meta billing and the AWS budget are watched (M25)
